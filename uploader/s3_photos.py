import os
import boto3
from botocore.exceptions import NoCredentialsError
from photo_service import PhotoService
import yaml

def get_keys(key_path):
    with open(key_path, "r") as key_file:
        keys = yaml.load(key_file, yaml.Loader)
    return keys

class S3Photos(PhotoService):
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
        
    def upload_photo(self, photo_path, photo_name):
        self.upload_file(photo_path)
        qr_target_url = self.page_url + photo_name
        return qr_target_url
        
    def upload_file(self, file_path):
        # Upload file
        file_name = os.path.split(file_path)[-1]
        self.s3.Bucket(self.bucket_name).upload_file(Filename=file_path, Key=file_name)#, ExtraArgs={'ACL': 'public-read'})
            
        # Construct URL
        location = boto3.client('s3').get_bucket_location(Bucket=self.bucket_name)['LocationConstraint']
        url = f"https://{self.bucket_name}.s3.{location}.amazonaws.com/{file_name}"
        return url
