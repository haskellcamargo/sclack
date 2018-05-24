import configparser
import os

def get_pyslack_config():
    config = configparser.ConfigParser()
    config.read(os.path.expanduser('~/.pyslack'))
    return config
