# This is the code that visits the warehouse.
import sys
from Pyro5.api import Proxy
import cobe.settings.network as network

# Example code of reaching a single eye via the local network
data_dict = network.eyes["eye_0"]
eye_0 = Proxy(data_dict["uri"] + data_dict["name"] + "@" + data_dict["host"] + ":" + data_dict["port"])

# accessing public method
assert eye_0.return_id() == data_dict["expected_id"]

# initializing the object detection model
eye_0.initODModel(api_key="gX0Z****",
                  name="projekt_gesty",
                  id="/projekt_gesty",
                  local="http://localhost:9001/",
                  version="2")

print("Success!")
