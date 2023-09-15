"""
parameters for the Pyro5 local network
"""
import os
import json

# Eyes
nano_username = "nano"
nano_cobe_installdir = "/home/nano/Desktop/CoBe"
unified_eyeserver_port = 1234

# Thymios
pi_username = "pi"
pi_cobe_installdir = "/home/pi/Desktop/CoBe"
unified_thymioserver_port = 1234

# reading eye_dicts.json from the directory of this file to fill eye_dictiornary
with open(os.path.join(os.path.dirname(__file__), "eye_dicts.json"), "r") as f:
    eyes = json.load(f)

# reading thymio_dicts.json from the directory of this file to fill thymio_dictiornary
with open(os.path.join(os.path.dirname(__file__), "thymio_dicts.json"), "r") as f:
    thymios = json.load(f)