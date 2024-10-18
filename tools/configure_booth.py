import glob
import os
import yaml
from argparse import ArgumentParser
from pprint import pprint
from print_example import write_yaml, scp_image_to_watermarks, scp_temp_yaml
    
DEFAULT_BOOTH_PATH ="colin@192.168.1.114:/home/colin/"
    
def get_args():
    parser = ArgumentParser(prog='Photo Booth Configurer',
                    description='Generates Photo Booth configuration and copies it to the booth if you want')
    
    parser.add_argument("-w", "--wm_config",
                        help="Path to load the watermark config yaml file to (optional)")
                        
    parser.add_argument("-o", "--yaml_out",
                        help="Path to save the config yaml file to")
    
    parser.add_argument("--booth_home", default=DEFAULT_BOOTH_PATH,
                        help="Path to home directory of Photo Booth")
                        
    return parser.parse_args()
    
def scp_files(booth_path, config, dryrun):
    if "watermark" in config.keys():
        watermark_path = config["watermark"]["watermark_path"]
        if os.path.isfile(watermark_path):
            watermark_dest_path = scp_image_to_watermarks(watermark_path, booth_path, dryrun)
            print("Copied", watermark_path, "to", watermark_dest_path)
            config["watermark"]["watermark_path"] = watermark_dest_path
            print("Changed watermark_path in YAML to", watermark_dest_path)
            print("New config:")
            pprint(config)
        else:
            print(watermark_path, "not found, hopefully it's already on the booth")
        
    scp_temp_yaml(booth_path, config, yaml_name="config.user.yaml", dryrun=dryrun)
    
    
if __name__ == "__main__":

    args = get_args()
            
    config = {}

    if args.wm_config:
        with open(args.wm_config, "r") as config_file:
            wm_config = yaml.load(config_file, yaml.Loader)
        config["watermark"] = wm_config["watermark"]

    album_title = input("Album title? : ")
    config["album_title"] = album_title
    multi_shot = input("Enable double press for 3 shots (recommended for 2x6 print format)? y/(n) : ")
    config["enable_multi_shot"] = (multi_shot == "y")
        
    print("Config:")
    pprint(config)

    if args.yaml_out:
        print("Saving config to", args.yaml_out)
        write_yaml(args.yaml_out, config)
    
    scp = input("Transfer new config and watermark to Photo Booth? y/(n)/d (d=dryrun) : ")
    if scp in ["y", "d"]:
        booth_path = args.booth_home
        print("Booth path:", booth_path)
        if scp == "d":
            print("Doing dryrun")
            dryrun = True
        else:
            dryrun = False
        scp_files(booth_path, config, dryrun)

