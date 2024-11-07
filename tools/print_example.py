import cv2
import numpy as np
import glob
import os
import yaml
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from print_kiosk.print_formatter import PrintFormatter
from argparse import ArgumentParser
from pprint import pprint
    
def get_args():
    parser = ArgumentParser(prog='Print Format Example',
                    description='Generates sample print images and can copy print logo and configuration to the Print Kiosk')
                    
    parser.add_argument("-f", "--photo_dir",
                        help="Where to pick .jpg files to put in the example photo")
                        
    parser.add_argument("-n", "--no_preview", action="store_true",
                        help="Don't show example photo preview")
                        
    parser.add_argument("-o", "--save_yaml_path",
                        help="Path of yaml file to save the config to")
                        
    parser.add_argument("-i", "--load_yaml_path",
                        help="Path of yaml file to load config from")
                    
    parser.add_argument("--print_format", default="2x6",
                        help="Print size (4x3, 2x6, or 3x2)")
                        
    parser.add_argument("--logo_path",
                        help="Path to logo to add to 2x6")
                        
    parser.add_argument("-w", "--logo_width_scale", type=float, default=1,
                        help="Ratio of the 2x6 width that the logo should be")
                        
    parser.add_argument("--h_crop_2x6", type=float, default=1,
                        help="Horizontal crop ratio for photos placed in 2x6")
                        
    parser.add_argument("--v_crop_2x6", type=float, default=1,
                        help="Vertical crop ratio for photos placed in 2x6")
                        
    parser.add_argument("--h_pad", type=float, default=0.04,
                        help="Blank padding added to sides to acount for cutoff")

    return parser.parse_args()
    
    
def write_yaml(yaml_path, config):
    with open(yaml_path, "w") as yaml_file:
        yaml_file.write(yaml.dump(config))


def read_yaml(yaml_path):
    with open(yaml_path, "r") as yaml_file:
        config = yaml.load(yaml_file, Loader=yaml.Loader)
    return config
        
    
def main():
    args = get_args()
    
    if args.load_yaml_path:
        print("Loading config from", args.load_yaml_path)
        config = read_yaml(args.load_yaml_path)
    else:
        if (args.print_format == "2x6") and args.logo_path:
            watermark = {
                "enable": True,
                "watermark_path": args.logo_path,
                "logo_width_scale": args.logo_width_scale
                }
        else:
            watermark = None
                
        config = {
                "print_format": args.print_format,
                "h_crop_2x6": args.h_crop_2x6,
                "v_crop_2x6": args.v_crop_2x6,
                "h_pad": args.h_pad,
                "watermark": watermark
            }
        
    print("Config:")
    pprint(config)
    if args.save_yaml_path:
        print("Saving config to", args.save_yaml_path)
        write_yaml(args.save_yaml_path, config)
    
    formatter = PrintFormatter(**config)
        
    if args.photo_dir:
        photos = glob.glob(os.path.join(args.photo_dir, "*.jpg"))
        assert len(photos) >= formatter.num_photos()
        print(f"Found {len(photos)}, using {formatter.num_photos()} in {args.photo_dir}")
        
        full_image, preview_image = formatter.format_print(photos[:formatter.num_photos()])
        print("Writing preview to preview.jpg")
        cv2.imwrite("preview.jpg", preview_image)
        if not args.no_preview:
            cv2.imshow("Preview", preview_image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
    
    
if __name__ == "__main__":
    main()
    
