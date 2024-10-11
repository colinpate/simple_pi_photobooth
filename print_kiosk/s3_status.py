import os
import boto3
from botocore.exceptions import NoCredentialsError
import yaml
import time
from common.common import load_config

def get_keys(key_path):
    with open(key_path, "r") as key_file:
        keys = yaml.load(key_file, yaml.Loader)
    return keys

class S3Status:
    def __init__(self):
        keys = get_keys("/home/colin/aws_key.yml")

        # Your AWS credentials - it's recommended to use environment variables for security
        aws_access_key_id = keys["public"]
        aws_secret_access_key = keys["private"]
        self.page_url = keys["page_url"]

        # Your S3 Bucket name
        self.bucket_name = keys["bucket_name"]

        # Initialize a session using Amazon S3
        session = boto3.session.Session(aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
        self.s3 = session.resource('s3')
        
    def upload_file(self, file_path):
        # Upload file
        file_name = os.path.split(file_path)[-1]
        self.s3.Bucket(self.bucket_name).upload_file(
            Filename=file_path,
            Key=file_name,
            ExtraArgs={
                'ContentType': 'application/json',
                'ContentDisposition': 'inline'
            }
        )
            
        # Construct URL
        location = boto3.client('s3').get_bucket_location(Bucket=self.bucket_name)['LocationConstraint']
        url = f"https://{self.bucket_name}.s3.{location}.amazonaws.com/{file_name}"
        return url

uploader = S3Status()
config = load_config("print_config")
file_path = config["status_file_path"]
file_content = ""

while True:
    with open(file_path, "r") as file_obj:
        data = file_obj.read()
    if data != file_content:
        file_content = data
        url = uploader.upload_file(file_path)
        print(url)
    time.sleep(10)
