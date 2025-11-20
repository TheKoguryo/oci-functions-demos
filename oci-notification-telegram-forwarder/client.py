from func import handler
from fdk import context

from io import BytesIO
import json
import logging
import os
import yaml

import asyncio

ctx = None
ctx = context.InvokeContext(app_id="None", app_name="None", fn_id="None", fn_name="None", call_id="None")

my_json = {
    'eventType': 'com.oraclecloud.computeapi.instanceaction.begin', 
    'cloudEventsVersion': '0.1', 
    'eventTypeVersion': '2.0', 
    'source': 'computeApi', 
    'eventTime': '2025-11-20T02:40:09Z', 
    'contentType': 'application/json', 
    'data': {
        'compartmentId': 'ocid1.compartment.oc1..xxxxx', 
        'compartmentName': 'Sandbox', 
        'resourceName': 'my-instance', 
        'resourceId': 'ocid1.instance.oc1.ap-chuncheon-1.xxxxx', 
        'availabilityDomain': 'AD1', 
        'freeformTags': {}, 
        'definedTags': {}, 
        'Oracle-Tags': {}, 
        'additionalDetails': {}
    }, 
    'eventID': 'b0ab9701-5ac1-42e9-86a3-1edfdae6f218', 
    'extensions': {
        'compartmentId': 'ocid1.compartment.oc1..xxxxx'
    }
}

my_string = json.dumps(my_json)
data = BytesIO(my_string.encode('utf-8'))

# YAML 파일 읽기
with open('func.yaml', 'r') as file:
    func_yaml = yaml.safe_load(file)
    
func_config = func_yaml['config']
logging.info(func_config)

for key, value in func_config.items():
    os.environ[key] = str(value)

# 함수 호출
##handler(ctx, data)
asyncio.run(handler(ctx, data))