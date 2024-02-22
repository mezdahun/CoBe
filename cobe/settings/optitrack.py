# optitrack related settings
client_address = '192.168.0.104'  # the address of the CoBe computer
server_address = '192.168.0.105'  # the address of the Optitrack computer

# coordinate rescaling for arena size (arena length in meters)
# to set the grounplane and axes in optitrack put the riange in the middle, the longer edge facing
# to the near projector the shorter to the right, aligned with the middle axis of the arena
x_rescale = 3.5
y_rescale = 3.5

# optitrack related settings
# decide if we use optitrack client for calculating agent coordinates, etc.
use_optitrack_client = True

# decide if we use multicast for optitrack data
use_multicast = True

# decide on the ouput of the optitrack client. If we use ABM, we write a sinlge json file with all the data
# that can be used by P34 ABM. If we use COBE, we write a json file(s) according to the specifications
# of the original PModule with predator-prey dynamics
mode = "cobe"  # abm or cobe
