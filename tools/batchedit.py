import glob
from argparse import ArgumentParser
import os
import cv2
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from booth.apply_watermark import ApplyWatermark 

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
    height, width, _ = image.shape
    crop_width = int(x_ratio * width)
    x_offset = int((width - crop_width) / 2)
    y_start = int(y_top * height)
    y_end = int(y_bot * height)
    cropped = image[y_start:y_end, x_offset:x_offset+crop_width, :]
    return cropped


def main():
    args = get_args()
    photos = glob.glob(os.path.join(args.photo_dir, "*.jpg"))

    if args.overlay_path:
        watermarker = ApplyWatermark(args.overlay_path)

    for photo in photos:
        image = cv2.imread(photo)
        if args.dryrun:
            cv2.imshow("Before", image)
        if args.overlay_path:
            watermarker.apply_watermark(image)
        image = crop_image(image, args.x_crop, args.y_top, args.y_bot)
        filename = os.path.split(photo)[-1]
        new_path = os.path.join(args.out_dir, filename)
        print(new_path)
        if not args.dryrun:
            cv2.imwrite(new_path, image)
        else:
            cv2.imshow("After", image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        

if __name__ == "__main__":
    main()
