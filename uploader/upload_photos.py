import qrcode
import time
import os
import time
from datetime import datetime
from common.common import load_config
from common.image_path_db import ImagePathDB
from uploader.photo_service import PhotoService
from uploader.google_photos_upload import GooglePhotos
from uploader.smugmug import SmugMug
from uploader.s3_photos import S3Photos
from common.common import wait_for_network_connection
import signal

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
    

def get_album_title():
    # Default to timestamped album
    formatted_datetime = datetime.now().strftime("%Y/%m/%d %H:%M")
    album_title = 'Glowbot Photo Booth ' + formatted_datetime
    return album_title


def attempt_upload(photo_name, postfix, error_photos, photo_db, service):
    success = False
    image_url = None
    try:
        file_path = photo_db.get_image_path(photo_name, postfix)
        image_url = service.upload_photo(file_path, photo_name)
        success = True
    except Exception as foo:
        photo_error_id = photo_name + postfix
        print("upload_photos.py: Failed to upload", photo_error_id)
        print("upload_photos.py: Exception", foo)
        photo_error_id = photo_name + postfix
        if photo_error_id not in error_photos:
            with open("/home/colin/upload_error.txt", "a") as err_file:
                err_file.write("\n" + photo_error_id + " upload failed at " + str(datetime.now()) + "\n")
                err_file.write(str(foo))
            error_photos.append(photo_error_id)
    return success, image_url


class SigtermHandler:
    def __init__(self):
        self.sigterm = False
        signal.signal(signal.SIGTERM, self.handle_sigterm)

    def handle_sigterm(self, frame, ts):
        self.sigterm = True


def main():
    config = load_config()
    display_gray = config.get("display_gray", True)
    qr_db = ImagePathDB(config["qr_path_db"])
    photo_db = ImagePathDB(config["photo_path_db"])

    color_postfix = config["color_postfix"]
    gray_postfix = config["gray_postfix"]
    qr_dir = config["qr_dir"]
    display_postfix = gray_postfix if display_gray else color_postfix
    other_postfix = color_postfix if display_gray else gray_postfix

    sigterm_handler = SigtermHandler()
    
    print("upload_photos.py: Saving QR codes to", qr_dir)
    
    wait_for_network_connection()
    
    try:
        service = SmugMug(config)
    except Exception as e:
        with open("/home/colin/photo_service_error.txt", "w") as error_file:
            error_file.write(str(e))
        service = S3Photos()
        
    album_title = config.get("album_title", get_album_title())
    service.create_album(album_title)
                
    error_photos = []
        
    while True:
        if sigterm_handler.sigterm:
            print("upload_photos.py: Exiting gracefully")
            break

        # Returns list of photo file names
        photo_db.try_update_from_file()
        missing_qr_names = list(photo_db.image_names() - qr_db.image_names())
        missing_qr_names.sort() # Sort from oldest to newest
        missing_qr_names = missing_qr_names[::-1] # Reverse order so we start from newest
        
        if len(missing_qr_names):
            print()
            print("upload_photos.py: Missing qr codes")
            print(missing_qr_names)
            
            if not config.get("enable_upload", True):
                print("upload_photos.py: Upload disabled, skipping")
                time.sleep(1)
                continue
    
        for photo_name in missing_qr_names:
            # First upload the photo that the QR code will link to. If it fails, go to the next photo
            upload_success, qr_target = attempt_upload(photo_name, display_postfix, error_photos, photo_db, service)
            if not upload_success:
                continue
            
            os.makedirs(config["qr_dir"], exist_ok=True)
            qr_path = os.path.join(qr_dir, photo_name + ".png")
            create_qr_code(qr_target, qr_path)
            qr_db.add_image(photo_name, qr_path)
            qr_db.update_file()
            print("upload_photos.py: Qr target", qr_target)
            print("upload_photos.py: Qr path", qr_path)
                
            # Then if that succeeds, try to upload the other photo
            attempt_upload(photo_name, other_postfix, error_photos, photo_db, service)
            
        time.sleep(0.25)
            
if __name__ == "__main__":
    main()
