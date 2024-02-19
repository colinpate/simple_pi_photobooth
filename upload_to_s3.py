import boto3
from botocore.exceptions import NoCredentialsError
import yaml

def get_keys(key_path):
    with open(key_path, "r") as key_file:
        keys = yaml.load(key_file, yaml.Loader)
    return keys
    
keys = get_keys("/home/colin/aws_key.yml")

print(keys)

# Your AWS credentials - it's recommended to use environment variables for security
aws_access_key_id = keys["public"]
aws_secret_access_key = keys["private"]

# Your S3 Bucket name
bucket_name = keys["bucket_name"]

# Path to your file
file_path = '/media/colin/USB20FD/booth_photos/color/24_01_21_12_38_48.jpg'
file_name = file_path.split('/')[-1]  # Assumes the file name is the last part of the path

# Initialize a session using Amazon S3
session = boto3.session.Session(aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
s3 = session.resource('s3')

def upload_file_to_s3(file_path, bucket_name, file_name):
    # Upload file
    s3.Bucket(bucket_name).upload_file(Filename=file_path, Key=file_name)#, ExtraArgs={'ACL': 'public-read'})
        
    # Construct URL
    location = boto3.client('s3').get_bucket_location(Bucket=bucket_name)['LocationConstraint']
    url = f"https://{bucket_name}.s3.{location}.amazonaws.com/{file_name}"
    return url

# Upload the file and get the URL
public_url = upload_file_to_s3(file_path, bucket_name, file_name)
print(f"File uploaded successfully. Public URL: {public_url}")
