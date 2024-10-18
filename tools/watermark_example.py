import cv2
import numpy as np
import glob
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from booth.apply_watermark import ApplyWatermark
from argparse import ArgumentParser
from pprint import pprint
from print_example import write_yaml, scp_image_to_watermarks, scp_temp_yaml
    
DEFAULT_BOOTH_PATH ="colin@192.168.1.114:/home/colin/"
    
def get_args():
    parser = ArgumentParser(prog='Watermarked Images Example',
                    description='Generates sample watermarked images and can copy watermark image and configuration to the Photo Booth')
                    
    parser.add_argument("-f", "--photo_dir", required=True,
                        help="Where to pick .jpg files from to put in the print")
                        
    parser.add_argument("--watermark_path",
                        help="Path to watermark")
                        
    parser.add_argument("-o", "--yaml_path",
                        help="Path to save the config yaml file to")
                        
    parser.add_argument("-w", "--weight", type=float, default=1,
                        help="Weight (opaqueness) of the watermark")
                        
    parser.add_argument("-x", "--x_offset", type=int, default=0,
                        help="Watermark x offset")
                        
    parser.add_argument("-y", "--y_offset", type=int, default=0,
                        help="Watermark y offset")
                        
    parser.add_argument("-s", "--h_size", type=int, default=1400,
                        help="Watermark x size")
                        
    parser.add_argument("-n", "--no_preview", action="store_true",
                        help="Don't show image preview")
                        
    return parser.parse_args()
    
def scp_files(booth_path, config, dryrun):
    watermark_path = config["watermark"]["watermark_path"]
    watermark_dest_path = scp_image_to_watermarks(watermark_path, booth_path, dryrun)
    print("Changing watermark_path in YAML to", watermark_dest_path)
    config["watermark"]["watermark_path"] = watermark_dest_path
        
    print("New config:")
    pprint(config)
        
    scp_temp_yaml(booth_path, config, yaml_name="config.user.yaml", dryrun=dryrun)
    
    
if __name__ == "__main__":

    args = get_args()
            
    config = {
            "watermark": {
                "watermark_path": args.watermark_path,
                "weight": args.weight,
                "h_size": args.h_size,
                "offset_x": args.x_offset,
                "offset_y": args.y_offset
            }
        }
        
    print("Config:")
    pprint(config)
    if args.yaml_path:
        print("Saving config to", args.yaml_path)
        write_yaml(args.yaml_path, config)
    
    watermarker = ApplyWatermark(**config["watermark"])
        
    images = glob.glob(os.path.join(args.photo_dir, "*.jpg"))
    print(f"Found {len(images)} images in {args.photo_dir}")
    
    for image in images:
        in_image = cv2.imread(image)
        in_image = cv2.cvtColor(in_image, cv2.COLOR_RGB2BGR)
        watermarker.apply_watermark(in_image)
        in_image = cv2.cvtColor(in_image, cv2.COLOR_BGR2RGB)
        image_name = os.path.split(image)[-1]
        in_image = cv2.resize(in_image, (int(in_image.shape[1] / 4), int(in_image.shape[0] / 4)))
        if not args.no_preview:
            cv2.imshow(image_name, in_image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        out_path = args.photo_dir + "/watermarked/" + image_name
        print("Writing", out_path)
        cv2.imwrite(out_path, in_image)
    
    scp = input("Transfer new config and watermark to Photo Booth? y/(n)/d (d=dryrun) : ")
    if scp in ["y", "d"]:
        booth_path = input(f"Path to booth home? Enter for default ({DEFAULT_BOOTH_PATH}) : ")
        if not booth_path:
            booth_path = DEFAULT_BOOTH_PATH
        print("Booth path:", booth_path)
        album_title = input("Album title? : ")
        config["album_title"] = album_title
        multi_shot = input("Enable double press for 3 shots (recommended for 2x6 print format)? y/(n) : ")
        config["enable_multi_shot"] = (multi_shot == "y")
        if scp == "d":
            print("Doing dryrun")
            dryrun = True
        else:
            dryrun = False
        scp_files(booth_path, config, dryrun)

