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

class ConfigSettings:
    def __init__(self, original_config, user_config_filename):
        self.original_config = original_config
        self.user_config_filename = user_config_filename
        self.config_changes = {}

    def get_latest_value(self, parameter_key):
        return self.config_changes.get(parameter_key, self.original_config[parameter_key])

    def save_config(self):
        try:
            user_config = load_config_file(self.user_config_filename)
            print("Found user config:", user_config)
        except FileNotFoundError:
            user_config = {}

        config_changed = False
        for key, value in self.config_changes.items():
            if value != self.original_config[key]:
                user_config[key] = value
                config_changed = True

        if config_changed:
            print("Writing new user config:", user_config)
            save_config_file(self.user_config_filename, user_config)
            return True
        else:
            return False