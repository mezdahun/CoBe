"""This file contains the settings regarding ABM simulations using
scioip34/abm framework."""

import os

# Switch to ABM simulations from Unity. If turned on, the whole rendering Unity submodule
# is replaced with agent based simulations from python
WITH_ABM = bool(int(os.getenv("WITH_ABM", 0)))

# App version of the ABM module to be used, can be Base, CoopSig or VisualFlocking
# Status: Base in progress, CoopSig is not working, VisualFlocking is not working
ABM_APP_VERSION = os.getenv("ABM_APP_VERSION", "Base")
