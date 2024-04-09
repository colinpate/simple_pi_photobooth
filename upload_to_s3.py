import boto3
from botocore.exceptions import NoCredentialsError
import yaml
import qrcode
import glob
import time
import os
from image_path_db import ImagePathDB

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


def upload_file_to_s3(file_path, bucket_name, file_name, s3):
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


def main():
        config = load_config() #TODO make this be in a function LOL
        qr_db = ImagePathDB(config["qr_path_db"])
        photo_db = ImagePathDB(config["photo_path_db"])

        keys = get_keys("/home/colin/aws_key.yml")

        # Your AWS credentials - it's recommended to use environment variables for security
        aws_access_key_id = keys["public"]
        aws_secret_access_key = keys["private"]

        # Your S3 Bucket name
        bucket_name = keys["bucket_name"]

        # Initialize a session using Amazon S3
        session = boto3.session.Session(aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)
        s3 = session.resource('s3')

        color_postfix = config["color_postfix"]
        gray_postfix = config["gray_postfix"]
        qr_dir = config["qr_dir"]
        page_url = config["page_url"]
        
        print("Checking for new images in", color_dir)
        print("Saving QR codes to", qr_dir)
            
        while True:
            # Returns list of photo file names
            self.photo_db.try_update_from_file()
            missing_qr_names = list(self.photo_db.image_names() - self.qr_db.image_names())
            
            if len(missing_qr_names):
                print("Missing qr codes")
                print(missing_qr_names)
                
                if not config.get("enable_upload", True):
                    print("Upload disabled, skipping")
                    time.sleep(1)
                    continue
        
            for photo_name in missing_qr_codes[:1]:
                try:
                    for postfix in [color_postfix, gray_postfix]:
                        file_path = self.photo_db.get_image_path(photo_name, postfix)
                        file_name = os.path.split(file_path)[-1]
                        url = upload_file_to_s3(file_path, bucket_name, file_name, s3)
                except:
                    print("Failed to upload", photo_name)
                    continue
                print(f"File uploaded successfully. Public URL: {color_url}")
                os.makedirs(config["qr_dir"], exist_ok=True)
                qr_path = os.path.join(qr_dir, photo_name + ".png")
                qr_target = page_url + photo_name
                create_qr_code(qr_target, qr_path)
                self.qr_db.update_file()
                print("Qr target", qr_target)
                print("Qr path", qr_path)
                
            time.sleep(0.5)
            
if __name__ == "__main__":
    main()
