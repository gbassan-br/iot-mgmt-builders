import json
import boto3
import os
import time

# loading boto3 clients 
dynamodb = boto3.client('dynamodb')

#loading env variables
TableName = os.environ['TABLE_NAME']


# transform python dict to dynamodb Map
def dict_to_item(raw):
    if isinstance(raw, dict):
        return {
            'M': {
                k: dict_to_item(v)
                for k, v in raw.items()
            }
        }
    elif isinstance(raw, list):
        return {
            'L': [dict_to_item(v) for v in raw]
        }
    elif isinstance(raw, str):
        return {'S': raw}
    elif isinstance(raw, int):
        return {'N': str(raw)}

def updateDevice(event):
    # Get device event details to put on dynamo
    deviceID = event['deviceID']
    creationDate = event['creationDate']
    deviceSerial = event['deviceSerial']
    deviceType = event['deviceType']
    attributes = dict_to_item(event['attributes'])
    # Update DynamoDB for container execution
    response = dynamodb.update_item(
        TableName=TableName,
        Key={
            'deviceID': {
                'S': deviceID
                }
        },
        UpdateExpression='set creationDate = :d, deviceSerial = :ds, deviceType = :dt, attributes = :att',
        ExpressionAttributeValues={
            ':d': {
                'S': str(creationDate)
            },
            ':ds':{
                'S': deviceSerial
            },
            ':dt':{
                'S': deviceType
            },
            ':att': attributes
        }
    )
        

def lambda_handler(event, context):
    deviceID = str(event['deviceID'])
    if(deviceID.startswith('device')):
        updateDevice(event)
        print("Virtual Device, provisioning...")
    else:
        print("Device not virtual, skipping")
    return {
        "statusCode": 200,
        "body": json.dumps('device-simulator updated sucessfully')
    }