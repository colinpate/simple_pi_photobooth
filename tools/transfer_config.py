import os
from pprint import pprint
from print_example import read_yaml, write_yaml
from argparse import ArgumentParser
    
BOOTH_USER = "colin"
    
def get_args():
    parser = ArgumentParser(prog='Photo Booth/Print Kiosk Configurer',
                    description='Transfers a config file and watermark image (if applicable) to the booth/kiosk')
                        
    parser.add_argument("-d", "--device",
                        help="Choose the device to transfer to: b for Booth or k for Kiosk")

    parser.add_argument("-i", "--config_path",
                        help="Config file path")
    
    parser.add_argument("-a", "--address",
                        help="IP address of Booth/Kiosk")
    
    parser.add_argument("-w", "--watermark_path",
                        help="Path to watermark image, if you want to change it")
                        
    return parser.parse_args()


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
    temp_yaml_path = "example_config_yaml.temp"
    write_yaml(temp_yaml_path, config)
    command = f"scp {temp_yaml_path} {yaml_destination}"
    print("\n", command, "\n")
    if not dryrun:
        os.system(command)
    os.remove(temp_yaml_path)
    

def scp_files(booth_path, config, yaml_name, dryrun):
    if "watermark" in config.keys():
        watermark_path = config["watermark"]["watermark_path"]
        if os.path.isfile(watermark_path):
            watermark_dest_path = scp_image_to_watermarks(watermark_path, booth_path, dryrun)
            print("Copied", watermark_path, "to", watermark_dest_path)
            config["watermark"]["watermark_path"] = watermark_dest_path
            print("Changed watermark_path in config from", watermark_path, "to", watermark_dest_path)
        else:
            raise FileNotFoundError(f"Watermark file {watermark_path} not found")
        
    scp_temp_yaml(booth_path, config, yaml_name=yaml_name, dryrun=dryrun)


def run_booth_command(booth_ip, dryrun, booth_command):
    command = f'ssh {BOOTH_USER}@{booth_ip} "{booth_command}"' 
    print("\n", command)
    if not dryrun:
        os.system(command)


def restart_booth_services(booth_ip, services, dryrun):
    for action in ["disable", "enable"]:
        for service in services:
            booth_command = f"sh /home/{BOOTH_USER}/simple_pi_photobooth/{action}_{service}_service.sh"
            run_booth_command(booth_ip, dryrun, booth_command)


def main():
    args = get_args()

    device = args.device
    while device not in ["b", "k"]:
        device = input("Transfer to (b)ooth or (k)iosk? ")
        if device not in ["b", "k"]:
            print("Error: You must specify either b for booth or k for kiosk.")
    if device == "b":
        device_name = "Photo Booth"
        services = ["booth", "upload"]
        yaml_name = "config.user.yaml"
    elif device == "k":
        device_name = "Print Kiosk"
        services = ["kiosk"]
        yaml_name = "print_config.user.yaml"
    print(f"{device_name} selected")

    if not args.config_path:
        config_path = input("Path to config yaml file to transfer? ")
    else:
        config_path = args.config_path
    print("Loading config from", config_path)
    config = read_yaml(config_path)

    if not args.address:
        booth_ip = input(f"{device_name} IP address? ")
    else:
        booth_ip = args.address

    if args.watermark_path:
        config["watermark"]["watermark_path"] = args.watermark_path
    
    scp = input(f"Transfer new config and logo/watermark to {device_name}? y/(n)/d (d=dryrun) : ")
    if scp in ["y", "d"]:
        booth_path = f"{BOOTH_USER}@{booth_ip}:/home/{BOOTH_USER}/"
        print(f"{device_name} path:", booth_path)
        if scp == "d":
            print("Doing dryrun")
            dryrun = True
        else:
            dryrun = False
        scp_files(booth_path, config, yaml_name, dryrun)
        print(f"Restarting {device_name} services to apply updates")
        restart_booth_services(booth_ip, services, dryrun)
    else:
        print("Not transferring.")


if __name__ == "__main__":
    main()