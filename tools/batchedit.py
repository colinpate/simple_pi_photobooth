import glob
from argparse import ArgumentParser
import os
import cv2
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from booth.apply_watermark import ApplyWatermark 
import piexif
from PIL import Image
import numpy as np

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


def main():
    args = get_args()
    photos = glob.glob(os.path.join(args.photo_dir, "*.jpg"))

    if args.overlay_path:
        watermarker = ApplyWatermark(args.overlay_path)

    for photo in photos:
        image = Image.open(photo)
        exif_dict = piexif.load(image.info.get('exif', b''))

        if args.dryrun:
            cv_image = np.array(image)
            cv_image = cv2.cvtColor(cv_image, cv2.COLOR_RGB2BGR)
            cv2.imshow("Before", cv_image)
        if args.overlay_path:
            if watermarker.watermark_shape[:2] != image.shape[:2]:
                print("Mismatched shape between image and watermark:", image.shape[:2], watermarker.watermark_shape[:2], photo)
            else:
                watermarker.apply_watermark(image)
        image = crop_image(image, args.x_crop, args.y_top, args.y_bot)
        filename = os.path.split(photo)[-1]
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
        

if __name__ == "__main__":
    main()
