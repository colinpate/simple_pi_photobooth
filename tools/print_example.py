import cv2
import numpy as np
import glob
import os
import yaml
from print_kiosk.print_formatter import PrintFormatter
from argparse import ArgumentParser
from pprint import pprint
    
DEFAULT_KIOSK_PATH ="colin@192.168.1.211:/home/colin/"
    
def get_args():
    parser = ArgumentParser(prog='Print Format Example',
                    description='Generates sample print images and can copy print logo and configuration to the Print Kiosk')
                    
    parser.add_argument("-f", "--photo_dir", required=True,
                        help="Where to pick .jpg files from to put in the print")
                    
    parser.add_argument("-p", "--print_format", default="2x6",
                        help="Print size (4x3, 2x6, or 3x2)")
                        
    parser.add_argument("-c", "--h_crop_2x6", type=float, default=1,
                        help="Horizontal crop ratio for photos placed in 2x6")
                        
    parser.add_argument("-v", "--v_crop_2x6", type=float, default=1,
                        help="Vertical crop ratio for photos placed in 2x6")
                        
    parser.add_argument("-a", "--h_pad", type=float, default=0.04,
                        help="Blank padding added to sides to acount for cutoff")
                        
    parser.add_argument("-l", "--logo_path",
                        help="Path to logo to add to 2x6")
                        
    parser.add_argument("-w", "--logo_width_scale", type=float, default=1,
                        help="Ratio of the 2x6 width that the logo should be")
                        
    parser.add_argument("-y", "--yaml_path",
                        help="Path to save the yaml config to")
                        
    parser.add_argument("-n", "--no_preview", action="store_true",
                        help="Don't show image preview")
                        
    return parser.parse_args()
    
    
def write_yaml(yaml_path, config):
    with open(yaml_path, "w") as yaml_file:
        yaml_file.write(yaml.dump(config))#, dumper=yaml.CDumper))
    
    
def scp_image_to_watermarks(logo_path, kiosk_path, dryrun):
    logo_filename = os.path.split(logo_path)[-1]
    logo_destination = os.path.join(kiosk_path, f"watermarks/")
    command = f"scp {logo_path} {logo_destination}"
    print("\n", command, "\n")
    if not dryrun:
        os.system(command)
    return os.path.join(logo_destination.split(":")[-1], logo_filename)
    
    
def scp_temp_yaml(kiosk_path, config, yaml_name, dryrun):
    yaml_destination = os.path.join(kiosk_path, f"simple_pi_photobooth/{yaml_name}")
    temp_yaml_path = "example_print_config_yaml.temp"
    write_yaml(temp_yaml_path, config)
    command = f"scp {temp_yaml_path} {yaml_destination}"
    print("\n", command, "\n")
    if not dryrun:
        os.system(command)
    os.remove(temp_yaml_path)
    
    
def scp_files(kiosk_path, config, dryrun):
    if config["logo_config"]:
        logo_path = config["logo_config"]["logo_path"]
        logo_dest_path = scp_image_to_watermarks(logo_path, kiosk_path, dryrun)
        print("Changing logo_path in YAML to", logo_dest_path)
        config["logo_config"]["logo_path"] = logo_dest_path
        
    print("New config:")
    pprint(config)
        
    scp_temp_yaml(kiosk_path, config, yaml_name="print_config.user.yaml", dryrun=dryrun)
        
    
def main():
    args = get_args()
    
    logo_config = None
    if (args.print_format == "2x6") and args.logo_path:
        logo_config = {
            "enable": True,
            "logo_path": args.logo_path,
            "logo_width_scale": args.logo_width_scale
            }
            
    config = {
            "print_format": args.print_format,
            "h_crop_2x6": args.h_crop_2x6,
            "v_crop_2x6": args.v_crop_2x6,
            "h_pad": args.h_pad,
            "logo_config": logo_config
        }
        
    print("Config:")
    pprint(config)
    if args.yaml_path:
        print("Saving config to", args.yaml_path)
        write_yaml(args.yaml_path, config)
    
    formatter = PrintFormatter(**config)
        
    photos = glob.glob(os.path.join(args.photo_dir, "*.jpg"))
    assert len(photos) >= formatter.num_photos()
    print(f"Found {len(photos)}, using {formatter.num_photos()} in {args.photo_dir}")
    
    full_image, preview_image = formatter.format_print(photos[:formatter.num_photos()])
    cv2.imwrite("preview.jpg", preview_image)
    if not args.no_preview:
        cv2.imshow("Preview", preview_image)
        cv2.waitKey(0)
    
    scp = input("Transfer new config and logo to Print Kiosk? y/(n)/d (d=dryrun) : ")
    if scp:
        kiosk_path = input(f"Path to kiosk home? Enter for default ({DEFAULT_KIOSK_PATH}) : ")
        if not kiosk_path:
            kiosk_path = DEFAULT_KIOSK_PATH
        print("Kiosk path:", kiosk_path)
        if scp == "d":
            print("Doing dryrun")
            dryrun = True
        else:
            dryrun = False
        scp_files(kiosk_path, config, dryrun)
    
    
if __name__ == "__main__":
    main()
    
