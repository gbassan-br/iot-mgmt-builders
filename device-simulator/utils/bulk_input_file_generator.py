from OpenSSL import crypto, SSL
import json
import boto3
import logging
import time
from shapely.geometry import Point
import random
from shapely.geometry import Polygon
from collections import OrderedDict
import argparse
import os
from boto3.dynamodb.conditions import Key
import uuid


# Read in command-line parameters
parser = argparse.ArgumentParser()
parser.add_argument("-n", "--number", action="store", required=True, dest="number", help="Number of devices you want to create.")
parser.add_argument("-f", "--file", action="store", required=True, dest="file", help="The name of the input file to be generated.")
parser.add_argument("-t", "--test", action="store_true", required=False, dest="test", help="Test the script.")
parser.add_argument("-1", "--err1", action="store", required=False, dest="err1", type=int, default=0, help="Number of rogue devices error type 1.")
parser.add_argument("-2", "--err2", action="store", required=False, dest="err2", type=int, default=0, help="Number of rogue devices error type 2.")
parser.add_argument("-3", "--err3", action="store", required=False, dest="err3", type=int, default=0, help="Number of rogue devices error type 3.")
#adding vibration error
parser.add_argument("-4", "--err4", action="store", required=False, dest="err4", type=int, default=0, help="Number of rogue devices error type 4.")
parser.add_argument("-p", "--prefix", action="store", required=False, dest="prefix", default="", help="Device name prefix.")

# CONSTANTS
TYPE_RSA = crypto.TYPE_RSA
TABLE_NAME = "devices-simulator"

try:
    TABLE_NAME = os.environ['TABLE_NAME']
except Exception:
    pass

# setup aws clients
dynamodb = boto3.client('dynamodb')
s3 = boto3.client('s3')
cfn = boto3.client('cloudformation')

# Configure logging
logger = logging.getLogger("AWSIoTPythonSDK.core")
logger.setLevel(logging.DEBUG)
streamHandler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)

#generate random gps
def generate_random(polygon):
        minx, miny, maxx, maxy = polygon.bounds
        contains = False
        while not contains:
                pnt = Point(random.uniform(minx, maxx), random.uniform(miny, maxy))
                if polygon.contains(pnt):
                        return pnt
                        break        
                else:
                        contains = False

def is_blank(my_string):
    if my_string and my_string.strip():
        #myString is not None AND myString is not empty or blank
        return False
    #myString is None OR myString is empty or blank
    return True

# Transform python dict to dynamodb Map
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


# Generate a private key
def generate_key(type, bits):
    key = crypto.PKey()
    key.generate_key(type, bits)
    return key


# Generate CSR
def generate_csr(nodename, key):
    req = crypto.X509Req()
    # Return an X509Name object representing the subject of the certificate.
    req.get_subject().CN = nodename
    req.get_subject().countryName = 'US'
    req.get_subject().stateOrProvinceName = 'NV'
    req.get_subject().localityName = 'LAS VEGAS'
    req.get_subject().organizationName = 'AWS'
    req.get_subject().organizationalUnitName = 'SA'

    # Set the public key of the certificate to pkey.
    req.set_pubkey(key)
    
    # Sign the certificate, using the key pkey and the message digest algorithm identified by the string digest.
    req.sign(key, "sha1")
    
    # Dump the certificate request req into a buffer string encoded with the type type.
    return crypto.dump_certificate_request(crypto.FILETYPE_PEM, req)


# Generate bulk json file
def generate_bulk_file(devices, file, err1, err2, err3, err4, prefix):
    logger.debug(">generate_bulk_file {} {} {}".format(err1, err2, err3, err4))

    # virtual device locations
    lasVegas = Polygon([(36.252783, -115.309517), (36.237003, -115.056027), (36.103602, -115.032501),(36.079889, -115.324110)])
    miami = Polygon([(25.938531, -80.120579),(25.936368, -80.344022), (25.736835, -80.376851),(25.773569, -80.132209)])
    sanfrancisco = Polygon([(37.780480, -122.510387), (37.803636, -122.405222), (37.636059, -122.395293),(37.644945, -122.492993)])
    nyc = Polygon([(40.909026, -73.774431),(40.942711, -73.894310), (40.750775, -74.006535),(40.744300, -73.974672)])
    saoPaulo = Polygon([(-23.508870, -46.709754), (-23.496853, -46.446429), (-23.596434, -46.554319),(-23.668282, -46.697371)])

    maploc = {'NYC':nyc, 'Miami':miami, 'LasVegas':lasVegas, 'SanFrancisco':sanfrancisco, 'SaoPaulo':saoPaulo}
    
    #checking if bulk.json file already exists and delete it
    if os.path.exists(file):
        logger.info("File '{}' already exists.".format(file))
        exit(2)
    
    map = {}

    for number in range(1, devices+1):    
        #Call key & CSR functions
        pKey = generate_key(TYPE_RSA, 2048)
        key = crypto.dump_privatekey(crypto.FILETYPE_PEM, pKey)

        #Needs to take input from user.
        csr = generate_csr('bootcamp.aws.iot',pKey)

        #generating different location
        location =  random.choice(list(maploc))
        coord = generate_random(maploc[location])


        # build the payload to append into bulk file    
        serial = '{0:03d}'.format(number)
        device = 'device-{}{}'.format(prefix, serial)
        
        id = uuid.uuid4()

        map[id] = {
            'key' : key, 
            'csr': csr,
            'device_id': device,
            'thing_type': "raspberryPI",
            'serial': serial,
            'type': 0,
            'location': str(location),
            'long': str(coord.x),
            'lat': str(coord.y)
        }
    
    logger.debug("Randomizing types... ")
    
    err1_cnt = 0
    err2_cnt = 0
    err3_cnt = 0
    err4_cnt = 0

    
    keys = list(map.keys())
    random.shuffle(keys)
    
    for k in keys:
        if err1_cnt < err1:
            map[k]['type'] = 1
            err1_cnt+=1
        elif err2_cnt < err2:
            map[k]['type'] = 2
            err2_cnt+=1
        elif err3_cnt < err3:
            map[k]['type'] = 3
            err3_cnt+=1
        elif err4_cnt < err4:
            map[k]['type'] = 4
            err4_cnt+=1
 
    logger.debug("Creating input file...")
    with open(file, "a") as f:
        for k, v in sorted(map.items()):
            payload = BulkPayload(map[k]['device_id'] , map[k]['thing_type'], map[k]['location'], map[k]['serial'], map[k]['csr'])
            f.write("%s\n"%json.dumps(payload.reprJSON(), cls=ComplexEncoder))

            response = dynamodb.put_item(
                TableName= TABLE_NAME,
                Item={
                    'deviceID': {'S': map[k]['device_id']},
                    'keyPem': {'S': map[k]['key'].decode('utf-8')},
                    'csrPem': {'S': map[k]['csr'].decode('utf-8')},
                    'type': {'S': str(map[k]['type']) },
                    'long':{'S': str(map[k]['long'])},
                    'lat':{'S': str(map[k]['lat'])}
                },
                ReturnValues='NONE',
                ReturnConsumedCapacity='TOTAL'
            )
    
    if args.test: 
        #This step will be done by students manually.
        objectKey = "bulk.json"
        f = open(file, "r")    
        contents = f.read()
        f.close()

        logger.debug("Uploading S3 object")
        s3.put_object(Bucket=bucket,
            Key=objectKey,
            Body=bytearray(contents, 'utf-8'))

        logger.debug("Done")

class BulkPayload:
    def __init__(self, thingname, thingtype, location, serialnumber, csr):
        self.ThingName = thingname
        self.ThingType = thingtype
        self.Location = location
        self.SerialNumber = serialnumber
        self.CSR = csr.decode('utf-8')

    def reprJSON(self):     
        # Ordered Dict is used to enforce JSON ordering to encode and decode
        return OrderedDict([("ThingName",self.ThingName),("ThingType",self.ThingType), ("Location",self.Location), ("SerialNumber",self.SerialNumber),("CSR", self.CSR)])

#Complex JSON encoder         
class ComplexEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj,'reprJSON'):
            return obj.reprJSON()
        else:
            return json.JSONEncoder.default(self, obj)


args = parser.parse_args()
number = int(args.number)
file = args.file

err1 = args.err1
err2 = args.err2
err3 = args.err3
err4 = args.err4


prefix = args.prefix

#to use with automated tests
bucket = ""

allowedQuantity = range(1,101)

if number not in allowedQuantity:
    parser.error("Wrong --number option %s. Must be one from %s to %s" % (args.number, str(allowedQuantity[0]), str(len(allowedQuantity))))
    exit(2)

if is_blank(file):
    parser.error("Wrong --file option %s. Must be a valid filename" % (args.file))
    exit(2)
        
if args.test:
    # utility for generate ecs scale for test
    bucket = os.environ['BUCKET']
    ecs = boto3.client('ecs')
    response = ecs.update_service(
        cluster='device-simulator-cluster',
        service='device-simulator-service',
        desiredCount=number/4,
        taskDefinition='device-simulator-task',
        deploymentConfiguration={
            'maximumPercent': 250,
            'minimumHealthyPercent': 50
        }
    )
# Generates an Input File for n devices

response = dynamodb.scan(
    TableName=TABLE_NAME,
    Select='COUNT',
    ExpressionAttributeValues={
        ':device': {
            'S': 'device-{}'.format(prefix)
            }
    },
    FilterExpression = "begins_with (deviceID, :device)"
)
# just checking if the student is running this command for the second time by accident
if response['Count']==0:
    generate_bulk_file(number, file, err1, err2, err3, err4, prefix)
else:
    logger.info("DynamoDB already have the devices. Check if the creation failed.")

