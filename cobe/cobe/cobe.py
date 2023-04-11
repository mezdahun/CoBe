# This is the code that visits the warehouse.
import sys
from Pyro5.api import Proxy

uri = "PYRO:cobe.eye@localhost:33155"
eye_1 = Proxy(uri)

# accessing public method
eid = eye_1.return_id()
print(f"Eye ID: {eid}")
print(f"Recreating ID!")
eye_1.recalculate_id()
eid = eye_1.return_id()
print(f"Eye ID: {eid}")
eye_1.return_id()
print(f"Trying to get secret ID!")
eye_1._return_secret_id()