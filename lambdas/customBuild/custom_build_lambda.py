#
# c9_bootstrap_lambda.property
#

# add role to C9 instance
# create bashrc and copy to S3
# ssm send_command to bootstrap C9 instance


from __future__ import print_function
import boto3
import logging
import json
import time
import cfnresponse
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info('event: {}'.format(event))
    logger.info('context: {}'.format(context))
    responseData = {}
    session = boto3.Session()
    s3 = session.resource(service_name='s3')
    ecs = boto3.client('ecs')
    dynamo = boto3.client('dynamodb')
    iot = boto3.client('iot')
    logs = boto3.client('logs')
    codebuild = boto3.client('codebuild')
    ecr = boto3.client('ecr')
    # Immediately respond on Delete
    logger.info('Always printing the event: {}'.format(event))
    if event['RequestType'] == 'Delete':
        # Empty Bucket before CloudFormation deletes it
        try:
            #clean up the bucket before delete it
            bucket = s3.Bucket(event['ResourceProperties']['S3_BUCKET'])
            bucket.object_versions.delete()
            logger.info('Bucket '+event['ResourceProperties']['S3_BUCKET']+' objects/versions deleted.')
            ecrresponse = ecr.delete_repository(
                registryId=event['ResourceProperties']['AccountNumber'],
                repositoryName=event['ResourceProperties']['ECRRepo'],
                force=True
            )

            # scale dow ecs service
            response = ecs.update_service(
                cluster='device-simulator-cluster',
                service='device-simulator-service',
                desiredCount=0,
                taskDefinition='device-simulator-task',
                deploymentConfiguration={
                    'maximumPercent': 250,
                    'minimumHealthyPercent': 50
                }
            )

            #wait ecs-service to scale down
            waitscaledown = True 
            while waitscaledown:
                response = ecs.describe_services(
                    cluster='device-simulator-cluster',
                    services=[
                        'device-simulator-service',
                    ]
                )
                if response['services'][0]['runningCount'] is 0:
                    waitscaledown = False
                    break
                time.sleep(60)

            #cleaning ecs cloudwatch logs

            response = logs.describe_log_streams(
                logGroupName='/ecs/device-simulator',
                logStreamNamePrefix='ecs/device-simulator',
            )
            hastoken = True
            while hastoken:
                for stream in response['logStreams']:
                    delete = logs.delete_log_stream(
                        logGroupName='/ecs/device-simulator',
                        logStreamName=stream['logStreamName']
                    )
                if 'nextToken' in response:
                    response = logs.describe_log_streams(
                        logGroupName='/ecs/device-simulator',
                        logStreamNamePrefix='ecs/device-simulator',
                        nextToken=response['nextToken']
                    )
                else:
                    hastoken = False
            #trying to cleanup the iot created resources
            try:
                response = dynamo.scan(
                    TableName='devices-simulator',
                    AttributesToGet=[
                        'deviceID',
                    ],
                )
                policyName = ""
                for item in response['Items']:
                    response = iot.list_thing_principals(
                        thingName=item['deviceID']['S']
                    )
                    for principal in response['principals']:
                        response = iot.list_principal_policies(
                            principal=principal,
                        )
                        for policy in response['policies']:

                            response = iot.detach_principal_policy(
                                policyName=policy['policyName'],
                                principal=principal
                            )
                            policyName =  policy['policyName']
                            
                        response = iot.update_certificate(
                            certificateId=principal.split("/")[1],
                            newStatus='INACTIVE'
                        )
                        response = iot.detach_thing_principal(
                            thingName=item['deviceID']['S'],
                            principal=principal
                        )
                        response = iot.delete_certificate(
                            certificateId=principal.split("/")[1],
                            forceDelete=True
                        )

                    response = iot.delete_thing(
                        thingName=item['deviceID']['S'],
                    )   
                    response = dynamo.delete_item(
                        TableName='devices-simulator',
                        Key={
                            'deviceID': {
                                'S': item['deviceID']['S']
                            }
                        }
                    )
                logger.info('policyName: {}'.format(policyName))
                response = iot.delete_policy(
                    policyName=policyName
                )
                response = iot.delete_thing_group(
                    thingGroupName='SaoPaulo'
                )
                response = iot.delete_thing_group(
                    thingGroupName='Miami'
                )
                response = iot.delete_thing_group(
                    thingGroupName='NYC'
                )
                response = iot.delete_thing_group(
                    thingGroupName='LasVegas'
                )
                response = iot.delete_thing_group(
                    thingGroupName='SanFrancisco'
                )
                time.sleep(3)
                response = iot.delete_thing_group(
                    thingGroupName='South-America'
                )
                time.sleep(3)
                response = iot.delete_thing_group(
                    thingGroupName='East-USA'
                )            
                time.sleep(3)
                response = iot.delete_thing_group(
                    thingGroupName='West-USA'
                )
                time.sleep(5)
                response = iot.delete_thing_group(
                    thingGroupName='Location'
                )                        
                response = iot.delete_dynamic_thing_group(
                    thingGroupName='HighVibration'
                )
                response = iot.delete_policy(
                    policyName='alexaPolicy'
                )
                response = iot.delete_job(
                    jobId='ChangeTempUnit',
                    force=True
                )
                response = iot.delete_job(
                    jobId='TurnPowerSaveMode',
                    force=True
                )
            except Exception as e:
                logger.info("Complete cleanup of created groups wasnt possible, manual delete the remain resources")
                logger.error(e, exc_info=True)
            #continuing anyway since the major stack resources has been deleted
            cfnresponse.send(event, context, cfnresponse.SUCCESS, responseData, 'CustomResourcePhysicalID')
        except Exception as e:
            logger.error(e, exc_info=True)
            responseData = {'Error': str(e)}
            cfnresponse.send(event, context, cfnresponse.FAILED, responseData, 'CustomResourcePhysicalID')

    if event['RequestType'] == 'Create':
        try:
            build = codebuild.start_build(
                projectName=event['ResourceProperties']['CodeBuildProject']
            )
            buildid = build['build']['id']
            logger.info('Buid ID: {}'.format(buildid))
            buildStatus = False
            while not buildStatus :
                response = codebuild.batch_get_builds(
                ids=[
                        buildid
                    ]
                )
                buildStatus = response['builds'][0]['buildComplete']
                logger.info('Build still executing')
                time.sleep(5)
            if response['builds'][0]['buildStatus'] != 'SUCCEEDED':
                raise Exception(''.format('The build {} has not succeed, check the Build logs.'))
            cfnresponse.send(event, context, cfnresponse.SUCCESS, responseData, 'CustomResourcePhysicalID')
        except Exception as e:
            logger.error(e, exc_info=True)
            responseData = {'Error': str(e)}
            cfnresponse.send(event, context, cfnresponse.FAILED, responseData, 'CustomResourcePhysicalID')
