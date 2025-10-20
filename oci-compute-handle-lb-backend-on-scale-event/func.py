import io
import json
import logging

from fdk import response

import os
import utils

import oci
import time

from sub_func import sync_backend_set_with_instances


def handler(ctx, data: io.BytesIO = None):
    logger = utils.getLogger()
    logger.info("START")
    start = time.time()

    try:
        body = json.loads(data.getvalue())
        event_data = body['data']

        logger.info(f"body: {body}")

        event_type = body['eventType']
        event_id = body['eventID']
        event_time = body['eventTime']  
        
        utils.setLoggerPrefix(event_id)
        logger = utils.getLogger()   

        logger.info(f"event_type: {event_type}")
        logger.info(f"event_time: {event_time}")

        compartment_id = event_data['compartmentId']
        resource_name = event_data['resourceName']
        resource_id = event_data['resourceId']

        logger.info(f"resource_id: {resource_id}")

    except (Exception, ValueError) as ex:
        logger.info('error parsing json payload: ' + str(ex))

    response_message = ""

    try:
        instance_pool_id = resource_id
        logger.info(f"instance_pool_id: {instance_pool_id}")

        sync_backend_set_with_instances(compartment_id, instance_pool_id)

    except oci.exceptions.ServiceError as ex:
        logger.error(f"{str(ex)}")
        response_message = ex.message
    except Exception as ex:
        logger.error(f"{type(ex)}")
        logger.error(f"{str(ex)}")
        response_message = str(ex)

    end = time.time()
    elapsed = end - start
    logger.info(f"Elapsed time: {elapsed:.3f} seconds")
    logger.info("END")

    return response.Response(
        ctx, response_data=json.dumps(
            {"message": "{0}".format(response_message)}),
        headers={"Content-Type": "application/json"}
    )    
