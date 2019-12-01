FROM python:2.7-alpine
ADD messagePublisher.py /
RUN pip install --upgrade pip
RUN pip install AWSIoTPythonSDK
RUN pip install boto3
CMD [ "python", "./messagePublisher.py" ]