import io
import json
import logging

from fdk import response

import os
import oci
from sub_func import run_pipeline

def handler(ctx, data: io.BytesIO = None):
    logging.getLogger().info("Inside raw-data-to-run-pipeline-python function")

    signer = oci.auth.signers.get_resource_principals_signer()
    data_science_client = oci.data_science.DataScienceClient(config={}, signer=signer)

    try:
        body = json.loads(data.getvalue())

        bucket_name = body["data"]["additionalDetails"]["bucketName"]
        resource_name = body["data"]["resourceName"]

        compartment_id = os.environ['ODSC_COMPARTMENT_ID']
        project_id = os.environ['ODSC_PROJECT_ID']
        pipeline_id = os.environ['ODSC_PIPELINE_ID']
        display_name = "run by function"

        datasciencepipelinerun_id = run_pipeline(data_science_client, compartment_id, project_id, pipeline_id, resource_name)

    except (Exception, ValueError) as ex:
        logging.getLogger().info('Failed: ' + str(ex))

    return response.Response(
        ctx,
        response_data=json.dumps({"resourceName": resource_name}),
        headers={"Content-Type": "application/json"}
    )

