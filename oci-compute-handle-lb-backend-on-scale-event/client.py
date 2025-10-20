from func import handler
from fdk import context

from io import BytesIO
import json
import logging
import os
import yaml

import pprint

ctx = None
ctx = context.InvokeContext(app_id="None", app_name="None", fn_id="None", fn_name="None", call_id="None")

my_json = {
    "eventType": "com.oraclecloud.computemanagement.updateinstancepool.begin", 
    "eventTime": "2025-08-17T23:44:26Z", 
    "data": {
        "compartmentId": "ocid1.compartment.oc1..aaaaaa.....", 
        "compartmentName": "oci-hol-xx", 
        "resourceName": "apache-ins-pool", 
        "resourceId": "ocid1.instancepool.oc1.ap-chuncheon-1.aaaaa.....", 
    }, 
    "eventID": "68c177fc-e35d-428a-9d5b-a960a0b65c8c", 
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
handler(ctx, data)