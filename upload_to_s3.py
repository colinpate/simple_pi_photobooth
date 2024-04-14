import boto3
from botocore.exceptions import NoCredentialsError
import yaml
import qrcode
import glob
import time
import os
from image_path_db import ImagePathDB
from photo_service import PhotoService


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


def create_qr_code(url, qr_code_file_path):
    """
    Create a QR code for the given URL and save it as an image file.
    :param url: The URL to encode in the QR code.
    :param qr_code_file_path: Path where the QR code image will be saved.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=4,
        border=3,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save(qr_code_file_path)
    

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


def main():
    config = load_config() #TODO make this be in a function LOL
    qr_db = ImagePathDB(config["qr_path_db"])
    photo_db = ImagePathDB(config["photo_path_db"])

    color_postfix = config["color_postfix"]
    gray_postfix = config["gray_postfix"]
    qr_dir = config["qr_dir"]
    
    print("Saving QR codes to", qr_dir)
    
    service = GooglePhotos()
        
    while True:
        # Returns list of photo file names
        photo_db.try_update_from_file()
        missing_qr_names = list(photo_db.image_names() - qr_db.image_names())
        
        if len(missing_qr_names):
            print("Missing qr codes")
            print(missing_qr_names)
            
            if not config.get("enable_upload", True):
                print("Upload disabled, skipping")
                time.sleep(1)
                continue
    
        for photo_name in missing_qr_names[:1]:
            try:
                for postfix in [color_postfix, gray_postfix]:
                    file_path = photo_db.get_image_path(photo_name, postfix)
                    qr_target = service.upload_photo(file_path, photo_name)
            except Exception as foo:
                print(foo)
                print("Failed to upload", photo_name)
                continue
            
            os.makedirs(config["qr_dir"], exist_ok=True)
            qr_path = os.path.join(qr_dir, photo_name + ".png")
            create_qr_code(qr_target, qr_path)
            qr_db.add_image(photo_name, qr_path)
            qr_db.update_file()
            print("Qr target", qr_target)
            print("Qr path", qr_path)
            
        time.sleep(0.5)
            
if __name__ == "__main__":
    main()
