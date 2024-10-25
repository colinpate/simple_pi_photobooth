import yaml
import os
import socket
import time


def check_network_connection(host="8.8.8.8", port=53, timeout=3):
    """
    Check network connectivity by trying to connect to a specific host and port.
    Google's public DNS server at 8.8.8.8 over port 53 (DNS) is used as default.
    """
    try:
        socket.setdefaulttimeout(timeout)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        sock.close()
        return True
    except socket.error as ex:
        print(f"Network is not reachable. Error: {ex}")
        return False


def wait_for_network_connection():
    """
    Wait indefinitely until the network is available.
    """
    print("upload_to_s3.py: Waiting for network connection...")
    while not check_network_connection():
        time.sleep(5)  # wait for 5 seconds before checking again
    print("upload_to_s3.py: Network connection established.")


def load_config_file(filename):
    parent_dir = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(parent_dir, "../" + filename)
    with open(config_path, "r") as config_file:
        config = yaml.load(config_file, yaml.Loader)
    return config


def save_config_file(filename, config):
    parent_dir = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(parent_dir, "../" + filename)
    with open(config_path, "w") as config_file:
        yaml.dump(config, config_file)


def load_config(config_name="config"):
    config = load_config_file(f"{config_name}.yaml")
    try:
        user_config = load_config_file(f"{config_name}.user.yaml")
        config.update(user_config)
        print("Loaded user config", user_config)
    except:
        print("Failed to load user config")
    return config
