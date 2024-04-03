import boto3
from botocore.exceptions import NoCredentialsError
import yaml
import qrcode
import glob
import time
import os

def get_keys(key_path):
    with open(key_path, "r") as key_file:
        keys = yaml.load(key_file, yaml.Loader)
    return keys

def load_config():
    parent_dir = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(parent_dir, "config.yaml")
    with open(config_path, "r") as config_file:
        config = yaml.load(config_file, yaml.Loader)
    return config

def upload_file_to_s3(file_path, bucket_name, file_name):
    # Upload file
    s3.Bucket(bucket_name).upload_file(Filename=file_path, Key=file_name)#, ExtraArgs={'ACL': 'public-read'})
        
    # Construct URL
    location = boto3.client('s3').get_bucket_location(Bucket=bucket_name)['LocationConstraint']
    url = f"https://{bucket_name}.s3.{location}.amazonaws.com/{file_name}"
    return url


def create_qr_code(url, qr_code_file_path):
    """
    Create a QR code for the given URL and save it as an image file.
    :param url: The URL to encode in the QR code.
    :param qr_code_file_path: Path where the QR code image will be saved.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=3,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save(qr_code_file_path)

        
def check_qr_codes(photo_dir, qr_dir):
    missing_qr_codes = []
    photos = [os.path.split(fn)[-1][:-4] for fn in glob.glob(photo_dir + "/*.jpg")]
    qr_codes = [os.path.split(fn)[-1][:-4] for fn in glob.glob(qr_dir + "/*.png")]
    for photo in photos:
        if photo not in qr_codes:
            missing_qr_codes.append(photo)
    return missing_qr_codes

config = load_config() #TODO make this be in a function LOL 

keys = get_keys("/home/colin/aws_key.yml")

# Your AWS credentials - it's recommended to use environment variables for security
aws_access_key_id = keys["public"]
aws_secret_access_key = keys["private"]

# Your S3 Bucket name
bucket_name = keys["bucket_name"]

# Initialize a session using Amazon S3
session = boto3.session.Session(aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
s3 = session.resource('s3')

if config["display_gray"]:
    upload_dir = config["gray_image_dir"]
else:
    upload_dir = config["color_image_dir"]
    
print("Checking for new images in", upload_dir)
print("Saving QR codes to", config["qr_dir"])
    
while True:
    # Path to your file
    missing_qr_codes = check_qr_codes(upload_dir, config["qr_dir"])
    
    if len(missing_qr_codes):
        print("Missing qr codes")
        print(missing_qr_codes)
        
        config = load_config()
        if not config.get("enable_upload", True):
            print("Upload disabled, skipping")
            time.sleep(1)
            continue
    
    for missing_qr in missing_qr_codes[:1]:
        file_name = missing_qr + ".jpg"
        file_path = upload_dir + "/" + file_name
        
        try:
            public_url = upload_file_to_s3(file_path, bucket_name, file_name)
        except:
            continue
        print(f"File uploaded successfully. Public URL: {public_url}")
        os.makedirs(config["qr_dir"], exist_ok=True)
        qr_path = config["qr_dir"] + "/" + missing_qr + ".png"
        create_qr_code(public_url, qr_path)
        
    time.sleep(0.5)
    
    
# Upload the file and get the URL
