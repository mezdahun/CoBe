"""
parameters for the Pyro5 local network
"""
nano_username = "nano"
nano_cobe_installdir = "/home/nano/Desktop/CoBe"
unified_eyeserver_port = 1234

eyes = {
    "eye_0": {
        "expected_id": 0,
        "host": "192.168.0.103",
        "port": f"{unified_eyeserver_port}",
        "uri": "PYRO:",
        "name": "cobe.eye",
        "fisheye_calibration_map": "map_eye_0.npz",
        "start_x": 545,
        "start_y": 40,
        "crop_width": 2500,
        "crop_height": 2500},
    "eye_1": {
        "expected_id": 1,
        "host": "192.168.0.101",
        "port": f"{unified_eyeserver_port}",
        "uri": "PYRO:",
        "name": "cobe.eye",
        "fisheye_calibration_map": "map_eye_1.npz",
        "start_x": 1000,  #923
        "start_y": 600,  #600
        "crop_width": 1200,  #1500
        "crop_height": 1200  #1500
    }
}