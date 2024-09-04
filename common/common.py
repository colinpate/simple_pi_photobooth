import yaml
import os

def load_config(filename="config.yaml"):
    parent_dir = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(parent_dir, "../" + filename)
    with open(config_path, "r") as config_file:
        config = yaml.load(config_file, yaml.Loader)
    return config
