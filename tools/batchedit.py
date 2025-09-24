import glob
from argparse import ArgumentParser
import os
import cv2
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from booth.apply_watermark import ApplyWatermark 
import piexif
import PIL
from PIL import Image
import numpy as np
import pickle

def get_args():
    parser = ArgumentParser(prog='Batch editor',
                    description='Batch edit photos')
                    
    parser.add_argument("-i", "--photo_dir",
                        help="Where to pick .jpg files")
    parser.add_argument("-o", "--out_dir",
                        help="Where to put .jpg files")
    parser.add_argument("-v", "--overlay_path",
                        help="Path to overlay")
    parser.add_argument("-x", "--x_crop", type=float, default=1,
                        help="X crop ratio")
    parser.add_argument("--y_top", type=float, default=0,
                        help="Y top crop (0-1) default 0")
    parser.add_argument("--y_bot", type=float, default=1,
                        help="Y bottom crop (0-1) default 1")
    parser.add_argument("-d", "--dryrun", action="store_true",
                        help="Don't save photos, preview")
    parser.add_argument("-l", "--lens_cal",
                        help="Lens cal file path (if applicable)")
    parser.add_argument("-g", "--convert_gray", action="store_true",
                        help="Convert to grayscale")
    
    return parser.parse_args()
    

def crop_image(image, x_ratio, y_top, y_bot):
    width, height = image.size
    crop_width = int(x_ratio * width)
    x_offset = int((width - crop_width) / 2)
    y_start = int(y_top * height)
    y_end = int(y_bot * height)
    crop_area = (x_offset, y_start, x_offset + crop_width, y_end) #left, upper, right, lower
    cropped = image.crop(crop_area)
    return cropped

def load_lens_cal(cal_file):
    with open(cal_file, "rb") as file_obj:
        return pickle.load(file_obj)

def main():
    args = get_args()
    photos = glob.glob(os.path.join(args.photo_dir, "*.jpg"))

    if args.lens_cal:
        lens_cal = load_lens_cal(args.lens_cal)

    if args.overlay_path:
        watermarker = ApplyWatermark(args.overlay_path)

    for photo in photos:
        try:
            image = Image.open(photo)
        except PIL.UnidentifiedImageError:
            print("Corrupt image", photo)
            continue
        exif_dict = piexif.load(image.info.get('exif', b''))

        if args.dryrun:
            cv_image = np.array(image)
            cv_image = cv2.cvtColor(cv_image, cv2.COLOR_RGB2BGR)
            cv2.imshow("Before", cv_image)

        if args.convert_gray or args.lens_cal:
            cv_image = np.array(image)
            if args.convert_gray:
                cv_image = convert_gray(cv_image)
            if args.lens_cal:
                cv_image = remap_original(cv_image, lens_cal)
            image = Image.fromarray(cv_image)

        if args.overlay_path:
            if watermarker.watermark_shape[:2] != image.shape[:2]:
                print("Mismatched shape between image and watermark:", image.shape[:2], watermarker.watermark_shape[:2], photo)
            else:
                watermarker.apply_watermark(image)

        image = crop_image(image, args.x_crop, args.y_top, args.y_bot)
        filename = os.path.split(photo)[-1]
        if args.convert_gray:
            filename = filename[:-4] + "_gray.jpg"
        new_path = os.path.join(args.out_dir, filename)
        print(new_path)
        if not args.dryrun:
            image.save(new_path, quality=95, exif=piexif.dump(exif_dict))
        else:
            cv_image = np.array(image)
            cv_image = cv2.cvtColor(cv_image, cv2.COLOR_RGB2BGR)
            cv2.imshow("After", cv_image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        
def convert_gray(image):
    gray_image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    gray_image = cv2.cvtColor(gray_image, cv2.COLOR_GRAY2BGR)
    return gray_image

def remap_original(orig_image, lens_cal):
    newcameramtx, roi, mtx, dist = lens_cal
    dst = cv2.undistort(orig_image, mtx, dist, None, newcameramtx)
    x, y, w, h = roi
    final_image = dst[y:y+h, x:x+w]
                
    return final_image

if __name__ == "__main__":
    main()
