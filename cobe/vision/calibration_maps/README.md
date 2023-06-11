This folder holds calibration maps for the camera lenses of the nVidia boards. Each lense has a different calibration map. 
The calibration maps are used to correct the distortion of the camera lenses. They are stored in a single npz file under
map1 and map2 attributes. The maps are generated using the OpenCV (contrib) function initUndistortRectifyMap for omnidirectional
cameras.

