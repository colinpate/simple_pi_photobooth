import yaml
import os

def load_config_file(filename):
    parent_dir = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(parent_dir, "../" + filename)
    with open(config_path, "r") as config_file:
        config = yaml.load(config_file, yaml.Loader)
    return config

def load_config(config_name="config"):
    config = load_config_file(f"{config_name}.yaml")
    try:
        user_config = load_config_file(f"{config_name}.user.yaml")
        config.update(user_config)
        print("Loaded user config", user_config)
    except:
        print("Failed to load user config")
    return config
