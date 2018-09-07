import yaml
import json

import json, ast, datetime
from datetime import timedelta

_DATE_FMT = '%Y-%m-%dT%H:%M:%S'

# returns a dictionary
def load_dictionary(encoded_dict):
    e = yaml.dump(encoded_dict).replace('!!python/unicode ', '')
    return yaml.load(e)

# returns a string
def load_yaml_as_str(encoded_dict):
    e = yaml.dump(encoded_dict).replace('!!python/unicode ', '')
    return e

def load_dict_as_yaml(encoded_dict):
    s = yaml.dump(
        encoded_dict, default_flow_style=False, allow_unicode=True) \
        .replace('!!python/unicode ', '')
    return s



# returns a dictionary
def load_yaml_from_file(file_name):
    with open(file_name, 'r') as stream:
        try:
            d = yaml.load(stream)
            return d
        except yaml.YAMLError as exc:
            print(exc)

# returns a dictionary
def load_yaml_from_str(stream):
    try:
        d = yaml.load(stream)
        return d
    except yaml.YAMLError as exc:
        print(exc)

def save_as_yaml(dictionary, file_name):
    with open(file_name, 'w', encoding='utf8') as outfile:
        yaml.dump(
            dictionary, outfile, default_flow_style=False, allow_unicode=True)

