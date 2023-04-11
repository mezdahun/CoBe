The Vision Module

The Vision Module is a collection of tools to implement
the visual system for the CoBe system. It includes all methods
that are necessary to communicate with a triton inference server
on an edge device (e.g. nVidia Jetson Nano).

Files:
- `eye.py`: Contains the CoBeEye class that is the main interface
  to the vision system. It is used to communicate with the
  triton inference server and to process the results and to receive
  the detection results via Pyro.
