import os

import utils
from utils import get_env_variable
from utils import model_to_details
import time
import datetime
import pytz
utc=pytz.UTC

import oci
import inspect
import pprint
import requests

PROFILE = "DEFAULT"
MAX_RETRIES=30
RETRY_INTERVAL_SECONDS=5
WAIT_SECONDS=60


if os.getenv("OCI_RESOURCE_PRINCIPAL_VERSION") is not None:
    signer = oci.auth.signers.get_resource_principals_signer()

    compute_client = oci.core.ComputeClient(config={}, signer=signer, retry_strategy=oci.retry.NoneRetryStrategy())
    network_client = oci.core.VirtualNetworkClient(config={}, signer=signer, retry_strategy=oci.retry.NoneRetryStrategy())
    load_balancer_client = oci.load_balancer.LoadBalancerClient(config={}, signer=signer, retry_strategy=oci.retry.NoneRetryStrategy())
    work_requests_client = oci.work_requests.WorkRequestClient(config={}, signer=signer, retry_strategy=oci.retry.NoneRetryStrategy())
    compute_management_client = oci.core.ComputeManagementClient(config={}, signer=signer, retry_strategy=oci.retry.NoneRetryStrategy())
else:
    config = oci.config.from_file(profile_name=PROFILE)

    compute_client = oci.core.ComputeClient(config)
    network_client = oci.core.VirtualNetworkClient(config)
    load_balancer_client = oci.load_balancer.LoadBalancerClient(config)
    work_requests_client = oci.work_requests.WorkRequestClient(config)
    compute_management_client = oci.core.ComputeManagementClient(config)
    

def sync_backend_set_with_instances(compartment_id, instance_pool_id):
    logger = utils.getLogger()
    logger.info(f"function {inspect.currentframe().f_code.co_name}()...")

    resources, instances_to_be_deleted = get_changes_in_pool(compartment_id, instance_pool_id)

    #logger.info(f"instances_to_be_deleted : {instances_to_be_deleted}")
    logger.info(f"instances_to_be_deleted length : {len(instances_to_be_deleted)}")

    ## DRAIN
    if len(instances_to_be_deleted) != 0 :
        # drain
        _drain_backends(instances_to_be_deleted)
        _wait_until_work_request_complete(compartment_id, instance_pool_id)

    logger.info(f"resources : {resources}")
    logger.info(f"resources length : {len(resources)}")

    LOAD_BALANCER_ID = get_env_variable("LOAD_BALANCER_ID")
    BACKEND_SET_NAME = get_env_variable("BACKEND_SET_NAME")

    backends = load_balancer_client.list_backends(
        load_balancer_id=LOAD_BALANCER_ID,
        backend_set_name=BACKEND_SET_NAME).data

    logger.debug(f"backends : {backends}")
    logger.debug(f"backends length : {len(backends)}")

    ## DELETE
    backend_names_to_delete = []

    for backend in backends:
        exist = False
        for resource in resources:
            if resource['private_ip'] == backend.ip_address:
                exist = True
                break
        if exist is False:
            backend_names_to_delete.append(backend.name)

    logger.info(f"backend_names_to_delete {backend_names_to_delete}")
    if len(backend_names_to_delete) > 0:
        _delete_backends(backend_names_to_delete)

    ## CREATE
    resources_to_create = []

    for resource in resources:
        exist = False

        if resource['private_ip'] != None:
            for backend in backends:
                if resource['private_ip'] == backend.ip_address:
                    exist = True
                    break
        else:
            count = 0

            while count < MAX_RETRIES:
                count += 1

                try:
                    private_ip = _get_private_ip(resource['compartment_id'], resource['resource_id'])
                    resource['private_ip'] = private_ip

                    break
                except Exception as e:
                    time.sleep(1)
                    continue

            if resource['private_ip'] is None:
                logger.error(f"Could not resolve private_ip for {resource['resource_id']} after {MAX_RETRIES} attempts; skipping")
            
        if exist is False:
            resources_to_create.append(resource)

    logger.info(f"resources_to_create {resources_to_create}")
    if len(resources_to_create) > 0:
        _create_backends(resources_to_create)


def get_changes_in_pool(compartment_id, instance_pool_id):
    logger = utils.getLogger()
    logger.info(f"function {inspect.currentframe().f_code.co_name}()...")

    target_instance_count = _get_target_instance_count(compartment_id, instance_pool_id)
    original_instances    = _get_current_instances(compartment_id, instance_pool_id)

    scaled_instance_count = target_instance_count - len(original_instances)

    count = 0

    while count < MAX_RETRIES:
        count += 1

        logger.info(f"attempt ({count}/{MAX_RETRIES})")

        resource_ids_running = []

        instances_in_pool = compute_management_client.list_instance_pool_instances(
            compartment_id=compartment_id,
            instance_pool_id=instance_pool_id,
            limit=100,
            sort_by="TIMECREATED",
            sort_order="DESC").data        

        for instance in instances_in_pool:
            #logger.info(f"compartment_id.id: {instance.compartment_id}")
            #logger.info(f"instance.display_name: {instance.display_name}")
            #logger.info(f"instance.id: {instance.id}")
            #logger.info(f"instance.state: {instance.state}")
            #logger.info(f"instance: {instance}")

            if instance.state.upper() in ('TERMINATING', 'TERMINATED'):
                continue

            resource_ids_running.append(instance.id)

        logger.info(f"resources_running length : {len(resource_ids_running)}")

        if len(resource_ids_running) == target_instance_count:
            break
        #if len(resource_ids_running) != len(original_instances):
        #    break

        if scaled_instance_count < 0:
            time.sleep(RETRY_INTERVAL_SECONDS/2)
        else:
            time.sleep(RETRY_INTERVAL_SECONDS)

    instances_to_retain = []
    instances_to_be_deleted = []

    for resource in original_instances:
        if resource['resource_id'] in resource_ids_running:
            instances_to_retain.append(resource)
        else:
            instances_to_be_deleted.append(resource)

    for resource_id in resource_ids_running:
        exist = False

        for resource in original_instances:
            if resource_id == resource['resource_id']:
                exist = True
                break

        if exist is False:
            new_resource = {
                "compartment_id": compartment_id,
                "resource_id": resource_id,
                "private_ip" : None
            }

            instances_to_retain.append(new_resource)

    logger.info(f"instances_to_retain: {instances_to_retain}")
    logger.info(f"instances_to_be_deleted: {instances_to_be_deleted}")

    return instances_to_retain, instances_to_be_deleted


def _get_target_instance_count(compartment_id, instance_pool_id):
    logger = utils.getLogger()
    logger.info(f"function {inspect.currentframe().f_code.co_name}()...")

    instance_pool = compute_management_client.get_instance_pool(
        instance_pool_id=instance_pool_id).data

    target_instance_count = instance_pool.size

    logger.info(f"target_instance_count: {instance_pool.size}")

    return target_instance_count


def _get_current_instances(compartment_id, instance_pool_id):
    logger = utils.getLogger()
    logger.info(f"function {inspect.currentframe().f_code.co_name}()...")

    instances_in_pool = compute_management_client.list_instance_pool_instances(
        compartment_id=compartment_id,
        instance_pool_id=instance_pool_id,
        limit=100,
        sort_by="TIMECREATED",
        sort_order="DESC").data

    resources = []

    for instance in instances_in_pool:
        if instance.state.upper() in ('TERMINATING', 'TERMINATED'):
            continue

        private_ip = _get_private_ip(instance.compartment_id, instance.id)

        resource = {
            "compartment_id": instance.compartment_id,
            "resource_id": instance.id,
            "private_ip" : private_ip
        }

        resources.append(resource)

    logger.info(f"current_instance_count: {len(resources)}")

    return resources


def _get_private_ip(compartment_id, instance_id):
    logger = utils.getLogger()
    logger.debug(f"function {inspect.currentframe().f_code.co_name}()...")

    logger.debug(f"compartment_id: {compartment_id}")
    logger.debug(f"instance_id: {instance_id}")

    list_vnic_attachments_response = compute_client.list_vnic_attachments(
        compartment_id=compartment_id,
        instance_id=instance_id)

    logger.debug(f"{list_vnic_attachments_response.data}")

    vnic_id = None

    if len(list_vnic_attachments_response.data) == 1:
        vnic_id = list_vnic_attachments_response.data[0].vnic_id
    elif len(list_vnic_attachments_response.data) > 1:
        for vnic_attachment in list_vnic_attachments_response.data:
            get_vnic_response = network_client.get_vnic(vnic_id=vnic_attachment.vnic_id)
            if get_vnic_response.data.is_primary is True:
                vnic_id = vnic_attachment.vnic_id
                break
    else:
        raise Exception("VnicNotFoundError")

    logger.debug(f"{vnic_id}")

    private_ip = None
    try:
        get_vnic_response = network_client.get_vnic(vnic_id=vnic_id)

        private_ip = get_vnic_response.data.private_ip
        #private_ip = get_vnic_response.data.public_ip
    except oci.exceptions.ServiceError as e:
        logger.error(f"Error: {e}")
        raise
    except Exception as e:
        logger.error(f"Error: {e}")
        raise

    return private_ip


def _drain_backends(target_backends_to_drain):
    logger = utils.getLogger()
    logger.info(f"function {inspect.currentframe().f_code.co_name}()...")

    LOAD_BALANCER_ID = get_env_variable("LOAD_BALANCER_ID")
    BACKEND_SET_NAME = get_env_variable("BACKEND_SET_NAME")

    HEALTH_CHECK_PORT = get_env_variable("HEALTH_CHECK_PORT", int)

    target_backend_names = []

    for backend in target_backends_to_drain:
        target_backend_names.append(f"{backend['private_ip']}:{HEALTH_CHECK_PORT}")

    backends = load_balancer_client.list_backends(
        load_balancer_id=LOAD_BALANCER_ID,
        backend_set_name=BACKEND_SET_NAME).data
      
    backend_details_array = []

    for backend in backends:
        backend_name = f"{backend.ip_address}:{backend.port}"

        if backend_name not in target_backend_names:
            backend_details = model_to_details(
                backend,
                oci.load_balancer.models.BackendDetails,
                exclude_fields=["name"]
            )
            backend_details_array.append(backend_details)
        else:
            updated_backend_details = oci.load_balancer.models.BackendDetails(
                                        ip_address=backend.ip_address,
                                        port=backend.port,
                                        weight=1,
                                        backup=False,
                                        drain=True,
                                        offline=False)

            backend_details_array.append(updated_backend_details)

    _update_backend_set_common(backend_details_array)


def _wait_until_work_request_complete(compartment_id, instance_pool_id):
    logger = utils.getLogger()
    logger.info(f"function {inspect.currentframe().f_code.co_name}()...")

    work_request_in_process = None

    work_requests = work_requests_client.list_work_requests(
        compartment_id=compartment_id,
        resource_id=instance_pool_id,
        limit=100).data    
    
    for work_request in work_requests:
        if work_request.operation_type == "TerminateInstancesInPool" and work_request.status != "SUCCEEDED":
            work_request_in_process = work_request
            break

    if work_request_in_process is not None:
        logger.info(f"work_request - {work_request_in_process.id} {work_request_in_process.status}")

        work_request = oci.wait_until(
            work_requests_client,
            work_requests_client.get_work_request(work_request.id),
            evaluate_response=lambda r: r.data.status in ['SUCCEEDED', 'FAILED'],
            max_wait_seconds=120,
            succeed_on_not_found=False
        )


def _delete_backends(backend_names):
    logger = utils.getLogger()
    logger.info(f"function {inspect.currentframe().f_code.co_name}()...")

    logger.info(f"backend_names: {backend_names}")

    LOAD_BALANCER_ID = get_env_variable("LOAD_BALANCER_ID")
    BACKEND_SET_NAME = get_env_variable("BACKEND_SET_NAME") 

    backends = load_balancer_client.list_backends(
        load_balancer_id=LOAD_BALANCER_ID,
        backend_set_name=BACKEND_SET_NAME).data
      
    backend_details_array = []

    for backend in backends:
        backend_name = f"{backend.ip_address}:{backend.port}"

        if backend_name not in backend_names:
            backend_details = model_to_details(
                backend,
                oci.load_balancer.models.BackendDetails,
                exclude_fields=["name"]
            )
            backend_details_array.append(backend_details)

    _update_backend_set_common(backend_details_array) 


def _create_backends(resources):    
    logger = utils.getLogger()
    logger.info(f"function {inspect.currentframe().f_code.co_name}()...")

    logger.info(f"resources: {resources}")

    HEALTH_CHECK_PROTOCOL = get_env_variable("HEALTH_CHECK_PROTOCOL")
    HEALTH_CHECK_PORT = get_env_variable("HEALTH_CHECK_PORT", int)
    HEALTH_CHECK_INTERVAL = get_env_variable("HEALTH_CHECK_INTERVAL_MS", int) / 1000
    HEALTH_CHECK_TIMEOUT = get_env_variable("HEALTH_CHECK_TIMEOUT_MS", int) / 1000
    HEALTH_CHECK_STATUS_CODE = get_env_variable("HEALTH_CHECK_STATUS_CODE", int)
    HEALTH_CHECK_MAX_RETRIES = get_env_variable("HEALTH_CHECK_MAX_RETRIES", int)
    HEALTH_CHECK_URL_PATH = get_env_variable("HEALTH_CHECK_URL_PATH")

    LOAD_BALANCER_ID = get_env_variable("LOAD_BALANCER_ID")
    BACKEND_SET_NAME = get_env_variable("BACKEND_SET_NAME")

    count = 0
    resources_needing_health_check = resources

    while count < HEALTH_CHECK_MAX_RETRIES:
        count += 1

        logger.info(f"health check attempt ({count}/{HEALTH_CHECK_MAX_RETRIES})")

        passed_health_check_resources = []
        failed_health_check_resources = []

        for resource in resources_needing_health_check:
            private_ip = resource['private_ip']

            url = f"{HEALTH_CHECK_PROTOCOL}://{private_ip}:{HEALTH_CHECK_PORT}{HEALTH_CHECK_URL_PATH}"

            try:
                logger.info(f"{private_ip} health check ({count}/{HEALTH_CHECK_MAX_RETRIES}) - {url}")
                response = requests.get(url, timeout=HEALTH_CHECK_TIMEOUT, allow_redirects=False)
            
                if response.status_code == HEALTH_CHECK_STATUS_CODE:
                    logger.info(f"{private_ip} [OK] {url} {response.status_code}")
                    passed_health_check_resources.append(resource)
                else:
                    logger.info(f"{private_ip} [CONNECT_FAILED] {url} {response.status_code}")
                    failed_health_check_resources.append(resource)

            except requests.RequestException as e:
                #logger.info(f"{private_ip} [CONNECT_FAILED] {url} \n {str(e)}")
                failed_health_check_resources.append(resource)

        if len(passed_health_check_resources) > 0:
            _update_backend_set(passed_health_check_resources)
            logger.info(f"{private_ip} [PASSED]({len(resources) - len(failed_health_check_resources)}/{len(resources)})")

        if len(resources_needing_health_check) == 0:
            break

        if len(passed_health_check_resources) == 0:
            logger.info(f"{private_ip} sleep for {HEALTH_CHECK_INTERVAL}s")
            time.sleep(HEALTH_CHECK_INTERVAL)

        resources_needing_health_check = failed_health_check_resources


def _update_backend_set_common(backend_details_array):
    logger = utils.getLogger()
    logger.info(f"function {inspect.currentframe().f_code.co_name}()...")

    LOAD_BALANCER_ID = get_env_variable("LOAD_BALANCER_ID")
    BACKEND_SET_NAME = get_env_variable("BACKEND_SET_NAME")

    backend_set = load_balancer_client.get_backend_set(
        load_balancer_id=LOAD_BALANCER_ID,
        backend_set_name=BACKEND_SET_NAME).data   

    health_checker_details = model_to_details(
        backend_set.health_checker,
        oci.load_balancer.models.HealthCheckerDetails,
        exclude_fields=[]
    )

    result = load_balancer_client.update_backend_set(
        update_backend_set_details=oci.load_balancer.models.UpdateBackendSetDetails(
            policy=backend_set.policy,
            backends=backend_details_array,
            health_checker=health_checker_details
        ),
        load_balancer_id=LOAD_BALANCER_ID,
        backend_set_name=BACKEND_SET_NAME)

    work_request_id = result.headers['opc-work-request-id']
    logger.info(f"UpdateBackedSet is requested - {work_request_id}")

    get_work_request_response = load_balancer_client.get_work_request(work_request_id)
    wait_until_succeeded_response = oci.wait_until(
        load_balancer_client, 
        get_work_request_response, 
        'lifecycle_state', 
        'SUCCEEDED', 
        max_wait_seconds=60)

    logger.info(f"UpdateBackedSet is succeeded")


def _update_backend_set(passed_health_check_resources): 
    logger = utils.getLogger()
    logger.info(f"function {inspect.currentframe().f_code.co_name}()...")

    LOAD_BALANCER_ID = get_env_variable("LOAD_BALANCER_ID")
    BACKEND_SET_NAME = get_env_variable("BACKEND_SET_NAME")

    HEALTH_CHECK_PORT = get_env_variable("HEALTH_CHECK_PORT", int)

    backends = load_balancer_client.list_backends(
        load_balancer_id=LOAD_BALANCER_ID,
        backend_set_name=BACKEND_SET_NAME).data
      
    backend_details_array = []

    for backend in backends:
        backend_details = model_to_details(
            backend,
            oci.load_balancer.models.BackendDetails,
            exclude_fields=["name"]
        )
        backend_details_array.append(backend_details)

    for resource in passed_health_check_resources:
        logger.info(f"passed_health_check_resource: {resource['private_ip']}")

        new_backend_details = oci.load_balancer.models.BackendDetails(
                                ip_address=resource['private_ip'],
                                port=HEALTH_CHECK_PORT)

        backend_details_array.append(new_backend_details)

    _update_backend_set_common(backend_details_array)
