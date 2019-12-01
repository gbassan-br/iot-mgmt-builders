import subprocess, os, sys
import urllib2
import json
import boto3
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTShadowClient
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTThingJobsClient
from AWSIoTPythonSDK.core.jobs.thingJobManager import jobExecutionTopicType
from AWSIoTPythonSDK.core.jobs.thingJobManager import jobExecutionTopicReplyType
from AWSIoTPythonSDK.core.jobs.thingJobManager import jobExecutionStatus
import logging
import time
import random
import threading
import datetime
import string

# get the env variables 

region = os.environ['AWS_DEFAULT_REGION']
TableName = os.environ['TABLE_NAME']
topic = os.environ['TOPIC']
sqsURL = os.environ['SQS_URL']
metadataUrl = '{}/task'.format(os.environ['ECS_CONTAINER_METADATA_URI'])


def random_generator(size=512, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for x in range(size))



# Class definition to handle job processing routine
class JobsMessageProcessor(object):
    def __init__(self, awsIoTMQTTThingJobsClient, clientToken):
        #keep track of this to correlate request/responses
        self.clientToken = clientToken
        self.awsIoTMQTTThingJobsClient = awsIoTMQTTThingJobsClient
        self.done = False
        self.jobsStarted = 0
        self.jobsSucceeded = 0
        self.jobsRejected = 0
        self._setupCallbacks(self.awsIoTMQTTThingJobsClient)

    def _setupCallbacks(self, awsIoTMQTTThingJobsClient):
        self.awsIoTMQTTThingJobsClient.createJobSubscription(self.newJobReceived, jobExecutionTopicType.JOB_NOTIFY_NEXT_TOPIC)
        self.awsIoTMQTTThingJobsClient.createJobSubscription(self.startNextJobSuccessfullyInProgress, jobExecutionTopicType.JOB_START_NEXT_TOPIC, jobExecutionTopicReplyType.JOB_ACCEPTED_REPLY_TYPE)
        self.awsIoTMQTTThingJobsClient.createJobSubscription(self.startNextRejected, jobExecutionTopicType.JOB_START_NEXT_TOPIC, jobExecutionTopicReplyType.JOB_REJECTED_REPLY_TYPE)

        # '+' indicates a wildcard for jobId in the following subscriptions
        self.awsIoTMQTTThingJobsClient.createJobSubscription(self.updateJobSuccessful, jobExecutionTopicType.JOB_UPDATE_TOPIC, jobExecutionTopicReplyType.JOB_ACCEPTED_REPLY_TYPE, '+')
        self.awsIoTMQTTThingJobsClient.createJobSubscription(self.updateJobRejected, jobExecutionTopicType.JOB_UPDATE_TOPIC, jobExecutionTopicReplyType.JOB_REJECTED_REPLY_TYPE, '+')

    #call back on successful job updates
    def startNextJobSuccessfullyInProgress(self, client, userdata, message):
        payload = json.loads(message.payload.decode('utf-8'))
        if 'execution' in payload:
            self.jobsStarted += 1
            execution = payload['execution']
            if self.executeJob(execution):
                statusDetails = {'HandledBy': 'ClientToken: {}'.format(self.clientToken)}
                threading.Thread(target = self.awsIoTMQTTThingJobsClient.sendJobsUpdate, kwargs = {'jobId': execution['jobId'], 'status': jobExecutionStatus.JOB_EXECUTION_SUCCEEDED, 'statusDetails': statusDetails, 'expectedVersion': execution['versionNumber'], 'executionNumber': execution['executionNumber']}).start()
            else:
                statusDetails = {'HandledBy': 'ClientToken: {}'.format(self.clientToken)}
                threading.Thread(target = self.awsIoTMQTTThingJobsClient.sendJobsUpdate, kwargs = {'jobId': execution['jobId'], 'status': jobExecutionStatus.JOB_EXECUTION_FAILED, 'statusDetails': statusDetails, 'expectedVersion': execution['versionNumber'], 'executionNumber': execution['executionNumber']}).start()     
        else:
            logger.debug('Start next saw no execution: ' + message.payload.decode('utf-8'))
            self.done = True

    def executeJob(self, execution):
        logger.debug('Executing job ID, version, number: {}, {}, {}'.format(execution['jobId'], execution['versionNumber'], execution['executionNumber']))
        logger.debug('With jobDocument: ' + json.dumps(execution['jobDocument']))
        try:
            global temp_convertion
            global powersave_temp
            if 'powersave' in execution['jobDocument']:
                # simulating led color for updating
                shadowCallbackContainer_Bot.sendUpdate("blue")
                # simulating update time
                time.sleep(15)
                if execution['jobDocument']['powersave'] == 'powersave':
                    powersave_temp = True
                else:
                    powersave_temp = False
                shadowCallbackContainer_Bot.sendUpdate(execution['jobDocument']['powersave'])
            else:
                # simulating led color for updating
                shadowCallbackContainer_Bot.sendUpdate("blue")
                # simulating update time
                time.sleep(15)
                # commiting changes
                temp_convertion = execution['jobDocument']['tempUnit']
                shadowCallbackContainer_Bot.sendUpdate(execution['jobDocument']['ledColor'])
            return True
        except:
            return False

    def newJobReceived(self, client, userdata, message):
        payload = json.loads(message.payload.decode('utf-8'))
        if 'execution' in payload:
            self._attemptStartNextJob()
        else:
            logger.debug('Notify next saw no execution')
            self.done = True

    def processJobs(self):
        self.done = False
        self._attemptStartNextJob()

    def startNextRejected(self, client, userdata, message):
        logger.debugf('Start next rejected:' + message.payload.decode('utf-8'))
        self.jobsRejected += 1

    def updateJobSuccessful(self, client, userdata, message):
        self.jobsSucceeded += 1

    def updateJobRejected(self, client, userdata, message):
        self.jobsRejected += 1

    def _attemptStartNextJob(self):
        statusDetails = {'StartedBy': 'ClientToken: {} on {}'.format(self.clientToken, datetime.datetime.now().isoformat())}
        threading.Thread(target=self.awsIoTMQTTThingJobsClient.sendJobsStartNext, kwargs = {'statusDetails': statusDetails}).start()

    def isDone(self):
        return self.done

    def getStats(self):
        stats = {}
        stats['jobsStarted'] = self.jobsStarted
        stats['jobsSucceeded'] = self.jobsSucceeded
        stats['jobsRejected'] = self.jobsRejected
        return stats


class shadowCallbackContainer:
    def __init__(self, deviceShadowInstance):
        self.deviceShadowInstance = deviceShadowInstance

    # Custom Get Shadow Callback
    def customShadowGetCallback(self, payload, responseStatus, token):
        logger.debug("Receive Shadow")
        logger.debug(json.loads(payload))

		
    # Custom Shadow callback	
    def customShadowCallback_Delta(self, payload, responseStatus, token):
        # payload is a JSON string ready to be parsed using json.loads(...)
        # in both Py2.x and Py3.x
        logger.debug("Received a delta message:")
        logger.debug(json.loads(payload))
	
    def customShadowCallback_Update(self, payload, responseStatus, token):
        logger.debug("Token: "+token)
        logger.debug("ResponseStatus: "+responseStatus)
        logger.debug(payload)
        if responseStatus == "rejected":
            self.deviceShadowInstance.shadowGet(shadowCallbackContainer_Bot.customShadowGetCallback, 5)

    #custom Alexa Callback if some button or cool stuff will be implemented
    def sendAlexaUpdate(self, client, userdata, message):
        jsonMessage = json.loads(message.payload)
        ledcolor = jsonMessage['ledcolor']
        self.sendUpdate(ledcolor)

    # Custom Shadow Update 
    def sendUpdate(self, message):
        logger.debug("Request to update the reported state...")
        
        #dealing with the powersavemode
        if message == 'powersave' or message =='nopowersave':
            newPayload = json.dumps(
                            {
                                'state':{
                                    'reported':{
                                        'powersave': message
                                    }
                                }
                            })
            logger.debug(newPayload)
        # dealing with alexa integration shadow update
        elif message == 'alexa' or message =='noalexa':
            newPayload = json.dumps(
                            {
                                'state':{
                                    'reported':{
                                        'alexastatus': message
                                    }
                                }
                            })
            logger.debug(newPayload)
        elif(str(message).isdigit()):
            newPayload = json.dumps(
                            {
                                'state':{
                                    'reported':{
                                        'vibration': message
                                    }
                                }
                            })
            logger.debug(newPayload)
        else:
            newPayload = json.dumps(
                            {
                                'state':{
                                    'reported':{
                                        'ledcolor': message
                                    }
                                }
                            })
            logger.debug(newPayload)
        self.deviceShadowInstance.shadowUpdate(newPayload, shadowCallbackContainer_Bot.customShadowCallback_Update, 5)
        logger.debug("Shadow update Sent.")

# update device status on dynamodb while the container is running or provisioning
def update_dynamodb(deviceID, status, taskID):
    try:
        dynamodb.update_item(
            TableName=TableName,
            Key={
                'deviceID': {
                    'S': deviceID
                    }
            },
            UpdateExpression='set deviceStatus = :r, lastUpdateDate = :d, taskID = :t',
            ExpressionAttributeValues={
                ':r': {
                    'S': status
                },
                ':d':{
                    'S': str(time.time()).split(".")[0]
                },
                ':t':{
                    'S': taskID
                }
            }
        )
        return True
    except Exception as err:
        logger.debug("Error trying to update Dynamo: "+err)
        return False
    
def getThingCert(deviceID):
    # Get iot thing details to list certificates
    certNum = 0
    # loop until certificate is attached to the thing
    while certNum == 0 : 
        response = iot.list_thing_principals(
            thingName = deviceID
        )
        certNum = len(response['principals'])
        time.sleep(5)

    # remove arn information. just id is needed
    certificateArn = response['principals'][0]
    certificateId = certificateArn.split('/')[1]

    # Get certicate pem details to put on dynamo. this information will be used on the fargate task
    response = iot.describe_certificate(
        certificateId = certificateId 
    )
    certificatePem = response['certificateDescription']['certificatePem']

    #update dynamodb with thing certificate
    response = dynamodb.update_item(
        TableName=TableName,
        Key={
            'deviceID': {
                'S': deviceID
                }
        },
        UpdateExpression='set certificatePem = :c',
        ExpressionAttributeValues={
            ':c':{
                'S': certificatePem
            }
        }
    )

    #return the certificate to the function
    return certificatePem


def get_thing_cert_jitr(deviceID):

    #get device certificate and CA certificate
    response = dynamodb.get_item(
        TableName=TableName,
        Key={
            'deviceID': {
                'S': deviceID
                }
        },
        AttributesToGet=[
            'certificatePem', 'caPem' 
        ]
    )
    
    return response['Item']['certificatePem']['S']+response['Item']['caPem']['S']


def get_device_type(deviceID):

    #get device type
    response = dynamodb.get_item(
        TableName=TableName,
        Key={
            'deviceID': {
                'S': deviceID
                }
        },
        AttributesToGet=[
            'type'
        ]
    )
    
    return response['Item']['type']['S']

    
def getCert(deviceID, is_jitr):
    if is_jitr:
        return get_thing_cert_jitr(deviceID)
    else:
        return getThingCert(deviceID)

# Configure logging
logger = logging.getLogger("AWSIoTPythonSDK.core")
logger.setLevel(logging.DEBUG)
streamHandler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)

# define the clients
iot = boto3.client('iot',region_name=region)
dynamodb = boto3.client('dynamodb',region_name=region)
ecs = boto3.client('ecs',region_name=region)
sqs = boto3.client('sqs',region_name=region)

hasMessages = False
while  not hasMessages:
    # get message from sqs to become a device
    response = sqs.receive_message(
        QueueUrl= sqsURL,
        AttributeNames=[
            'All',
        ],
        MessageAttributeNames=[
            '*',
        ],
        MaxNumberOfMessages=1,
        VisibilityTimeout=120,
        WaitTimeSeconds=20,
    )
    if 'Messages' in response:
        hasMessages = True
        break
    else:
        hasMessages = False

#define device details from SQS message
deviceID = json.loads(response['Messages'][0]['Body'])['deviceID']
location = json.loads(response['Messages'][0]['Body'])['attributes']['Location']
receipt = response['Messages'][0]['ReceiptHandle']

logger.info("Starting device '{}' hosted on '{}'...".format(deviceID, location))

jitr = False
rogue = False

if 'JITR' in response['Messages'][0]['Body']:
    jitr = response['Messages'][0]['Body']

if 'rogue' in response['Messages'][0]['Body']:
    rogue = response['Messages'][0]['Body']

logger.info("Using JITR? '{}'".format(jitr))
logger.info("Is Rogue? '{}'".format(rogue))

# get ECS Container Metadata Info from file
# set ECS_ENABLE_CONTAINER_METADATA=true on ECS instance userdata bootstraping
# it will automatically set the file path to the ECS_CONTAINER_METADATA_FILE env var
try:
    logger.info('Task metadata URL: {}'.format(metadataUrl))
    ecsMetaData = json.load(urllib2.urlopen(metadataUrl))
    logger.info('return: {}'.format(ecsMetaData))
    taskID = ecsMetaData['TaskARN']
except Exception as e:
    taskID = "123456"
    logger.info(e)

# update dynamodb device table to PROVISIONING status
dynamoUpdate = update_dynamodb(deviceID,'PROVISIONING',taskID)
if (dynamoUpdate):
    #deletes the message from the queue
        response = sqs.delete_message(
            QueueUrl=sqsURL,
            ReceiptHandle = receipt
        )
        logger.debug('SQS Message Deleted. starting the device...')
else:
    #kill the container and let sqs message visibility timeout expires
    logger.debug("Could not update dynamodb with task details. Aborting container!")
    raise Exception

# get endpoint with ATS enable to avoid Symantec CA
# avoid using iot:Data if using ATS rootCA, it will throw a error with SSL Validation
logger.info("Download root CA certificate...")

response = iot.describe_endpoint(
    endpointType='iot:Data-ATS'
)
endpoint = response['endpointAddress']

# get ATS rootCA cert from ats urls, which works best
urls = [
    "https://www.amazontrust.com/repository/AmazonRootCA1.pem", 
    "https://www.amazontrust.com/repository/AmazonRootCA2.pem",
    "https://www.amazontrust.com/repository/AmazonRootCA3.pem",
    "https://www.amazontrust.com/repository/AmazonRootCA4.pem"
    ]

# persist rootCA on local filesystem
filename = "rootCA.pem"

# avoiding url open timeout
noCert = True
while noCert:
    for url in urls:
        try:
            filedata = urllib2.urlopen(url)  
            datatowrite = filedata.read()
            with open(filename, 'wb') as f:  
                f.write(datatowrite)
            noCert = False
            break
        except Exception as e:
            logger.debug(e)
            logger.debug("Error trying to get ATS pem. wait for a while and try again...")
            time.sleep(10)
            noCert = True


# save cert locally to estabilish mqtt connection
f = open('incommon.crt', "w")
f.write(getCert(deviceID, jitr))
f.close()

dev_type = str(get_device_type(deviceID))

# get key pem from dynamodb
response = dynamodb.get_item(
    TableName= TableName,
    Key={
        'deviceID': {
            'S': deviceID}
    },
    AttributesToGet=[
        'keyPem',
    ],
    ConsistentRead=True,
    ReturnConsumedCapacity='TOTAL'
)
# save cert locally to estabilish mqtt connection
k = open('incommon.key', "w")
k.write(response['Item']['keyPem']['S'])
k.close()

temp_convertion = "fahrenheit"
powersave_temp = False
# setting MQTT TLS details
host = endpoint
rootCAPath = filename
certificatePath = "incommon.crt"
privateKeyPath = "incommon.key"
thingName = deviceID
clientId = thingName


# Init AWSIoTMQTTShadowClient
myAWSIoTMQTTShadowClient = None
myAWSIoTMQTTShadowClient = AWSIoTMQTTShadowClient(clientId+"_shadow")
myAWSIoTMQTTShadowClient.configureEndpoint(host, 8883)
myAWSIoTMQTTShadowClient.configureCredentials(rootCAPath, privateKeyPath, certificatePath)

# AWSIoTMQTTShadowClient configuration
myAWSIoTMQTTShadowClient.configureAutoReconnectBackoffTime(1, 64, 20)
myAWSIoTMQTTShadowClient.configureConnectDisconnectTimeout(15)  # 15 sec
myAWSIoTMQTTShadowClient.configureMQTTOperationTimeout(5)  # 5 sec

# Connect to AWS IoT
if jitr:
    not_connected = True

    logger.info("JITR: Trying first connection...")
    while not_connected:
        try:
            myAWSIoTMQTTShadowClient.connect()
            not_connected = False
        except Exception as e: # Try to reconnect, now properly provisioned
            time.sleep(1)
            logger.info("JITR: Reconnecting...")
else:
    myAWSIoTMQTTShadowClient.connect()

# Create a deviceShadow with persistent subscription
deviceShadowHandler = myAWSIoTMQTTShadowClient.createShadowHandlerWithName(thingName, False)
shadowCallbackContainer_Bot = shadowCallbackContainer(deviceShadowHandler)

# Get last delta on get
#deviceShadowHandler.shadowGet(shadowCallbackContainer_Bot.customShadowGetCallback, 15)

# Listen on deltas
#deviceShadowHandler.shadowRegisterDeltaCallback(shadowCallbackContainer_Bot.customShadowCallback_Delta)

myMQTTClient = myAWSIoTMQTTShadowClient.getMQTTConnection()


# Init AWSIoTMQTTShadowClient
myAWSIoTMQTTClient = None

# Init AWSIoTMQTTClient with another cliendID to divide topic subscription
myAWSIoTMQTTClient = AWSIoTMQTTClient(clientId)
myAWSIoTMQTTClient.configureEndpoint(host, 8883)
myAWSIoTMQTTClient.configureCredentials(rootCAPath, privateKeyPath, certificatePath)

# AWSIoTMQTTClient connection configuration
myAWSIoTMQTTClient.configureAutoReconnectBackoffTime(1, 64, 20)
myAWSIoTMQTTClient.configureConnectDisconnectTimeout(15)  # 15 sec
myAWSIoTMQTTClient.configureMQTTOperationTimeout(5) # 5 sec


# Connect to AWS IoT

myAWSIoTMQTTClient.connect()
time.sleep(5)

# Initialize the jobclient using simple mqtt client (using shadow previous connection)
jobsClient = AWSIoTMQTTThingJobsClient(clientId, thingName, QoS=1, awsIoTMQTTClient=myAWSIoTMQTTClient)


logger.debug('Connecting to MQTT server and setting up callbacks...')

# Trying to connect jobclient
jobConnected = False
while not jobConnected:
    try:
        jobsClient.connect()
        jobConnected = True
    except:
        logger.debug("Error Connecting Job, waiting for a while")
        time.sleep(10)
        jobConnected = False

# processing jobs
jobsMsgProc = JobsMessageProcessor(jobsClient, clientId)
logger.debug('Starting to process jobs...')
jobsMsgProc.processJobs()

# setting led initial status
shadowCallbackContainer_Bot.sendUpdate("red")

# setting led initial powersave status 
shadowCallbackContainer_Bot.sendUpdate("nopowersave")

# setting alexa subscription initial
alexasub = False

# Device types
# 0 = normal behavior
# 1 = extra messages
# 2 = large message
# 3 = invalid topic

logger.info("Device type: {}".format(dev_type))

# Publish to the same topic in a loop forever
while True:
    #updating status and containerid on dynamodb
    dynamoUpdate = update_dynamodb(deviceID, 'RUNNING', taskID)

    # just checking if dynamo could be updated, not required but it will be logged
    if(not dynamoUpdate):
        logger.debug("Could not update dynamo with last updated status")
    
    # simulate dht11 celsius temp and humidity
    # add 2 celsius degrees in powersavemode
    if powersave_temp :
        temp = random.randrange(24,28)
    else:
        temp = random.randrange(20,24)

    humid = random.randrange(40,45)

    #check global var to identify if the job already run
    if temp_convertion != "celsius":
        temp = (1.8*temp)+32

    payload = {
                'deviceID':deviceID,
                'location':location,
                'temp_unit':temp_convertion,
                'temp':round(temp,2), 
                'humid':humid
    }
    
    if dev_type == '2':
        payload = {
            'deviceID':deviceID,
            'location':location,
            'temp_unit':temp_convertion,
            'temp':round(temp,2), 
            'humid':humid,
            'extra': random_generator()
        }
    
    finalTopic = "{}/{}/{}".format(topic, location, deviceID)    
    alexaTopic = "alexa/integration/{}".format(deviceID)
    
    try:
        myAWSIoTMQTTClient.publish(finalTopic, json.dumps(payload), 1)
        logger.debug("Published topic:"+finalTopic+" message: "+json.dumps(payload))

        if dev_type == '4':
            high_vibration = random.randrange(100,200)
        else:
            high_vibration = random.randrange(50,90)
        
        shadowCallbackContainer_Bot.sendUpdate(high_vibration)
        
        if dev_type == '3':
            time.sleep(random.randrange(31, 40))

            logger.debug("Trying to publish to an unauth topic...")
            finalTopic = "unauth/{}/{}/{}".format(topic, location, deviceID)
            myAWSIoTMQTTClient.publish(finalTopic, json.dumps(payload), 1)
            logger.debug("Published topic: {} message: {}".format(finalTopic, json.dumps(payload)))

    except Exception as e:
        logger.debug(str(e))
        logger.debug("Error publish iot")
        dynamoUpdate = update_dynamodb(deviceID,'ERROR', taskID)
        # trying to wait to publish again using the mqtt client
        time.sleep(15)
    
    # getting thing group
    response = iot.list_thing_groups_for_thing(
        thingName=deviceID,
    )
    logger.debug(response)
    #check if the group is defined for the thing already
    if len(response['thingGroups'])>0:
        policies = {'policies':[]}
        for group in response['thingGroups']:
        # checking if alexaPolicy is attached already to change the shadow state
            response = iot.list_attached_policies(
                target=group['groupArn'],
            )
            for policy in response['policies']:
                policies['policies'].append(policy)
    else:
        #if not setting dummy empty response['policies']
        policies = {'policies':[]}

    logger.debug(policies)
    # checking if the alexaPolicy is attached of the device's group
    if len(policies['policies']) > 0:
        for policy in policies['policies']:
            if 'alexaPolicy' in policy['policyName']:
                #check if a subscription is already running to avoid overload the iot
                if not alexasub:
                    try:
                        # if not, trying to subscribe
                        logger.debug(str(alexaTopic))
                        alexasub = myAWSIoTMQTTClient.subscribe(str(alexaTopic), 1, shadowCallbackContainer_Bot.sendAlexaUpdate)
                        shadowCallbackContainer_Bot.sendUpdate("alexa")
                    except Exception as e:
                        logger.debug(e)
                        #if there is something wrong with the policy, update back the shadow to noalexa integration
                        logger.debug("Error subscribing alexa topic. Check the permissions of alexaPolicy")
                        shadowCallbackContainer_Bot.sendUpdate("noalexa")

            else:
                # if there is not a policy attached on device's group, update the shadow
                # checking also if the policy is not alexaPolicy
                shadowCallbackContainer_Bot.sendUpdate("noalexa")
                try:
                    # if there is not a policy trying to unsbscribe to maintain correct state
                    myAWSIoTMQTTClient.unsubscribe(str(alexaTopic))
                    # setting false to try again later
                    alexasub = False
                except Exception as e:
                    logger.debug(e)
                    logger.debug("Error unsubscribing alexa topic")
    else:
        # no policy is attached, updating shadow
        shadowCallbackContainer_Bot.sendUpdate("noalexa")
        try:
            # if there is not a policy trying to unsbscribe to maintain correct state
            myAWSIoTMQTTClient.unsubscribe(str(alexaTopic))
            alexasub = False
        except Exception as e:
            logger.debug(e)
            # maybe there is no subscription whatsoever
            logger.debug("Error unsubscribing alexa topic")

    if dev_type != '1':
        # publish from 31 to 40 seconds to not flood IoT
        time.sleep(random.randrange(35, 40))
    elif dev_type == '1':
        # hacked device simulation
        time.sleep(random.randrange(1))
