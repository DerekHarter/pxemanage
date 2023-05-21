#!/usr/bin/env python3
"""Implement a simple settings from a yaml file mechanism.  This file
loads configuration settings from an expected location.  Other files can
use settings by doing

from config import settings

print(f"{settings.ks_config_dir}/user-data")
"""
import yaml

with open("pxemanage.yml", "r") as file:
    settings = yaml.safe_load(file)
