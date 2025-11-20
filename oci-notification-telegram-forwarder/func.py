import io
import json
import logging

from fdk import response

import os
import utils

import time

from sub_func import send_telegram_message


async def handler(ctx, data: io.BytesIO = None):
    logger = utils.getLogger()
    logging.getLogger('httpx').setLevel(logging.WARNING)

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

        instance_action_type = event_data['additionalDetails']['instanceActionType']

        logger.info(f"resource_id: {resource_id}")

    except (Exception, ValueError) as ex:
        logger.info('error parsing json payload: ' + str(ex))

    response_message = ""

    try:
        message_to_send = f"""[OCI Compute Instance] 다음 자원에 액션이 발생했습니다.
- Resource ID: {resource_id}        
- Resource Name: {resource_name}
- Action Type: {instance_action_type}
"""

        await send_telegram_message(message_to_send, None)

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
