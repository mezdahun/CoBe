"""
parameters for the Pyro5 local network
"""
nano_username = "nano"
nano_cobe_installdir = "/home/nano/Desktop/CoBe"
unified_eyeserver_port = 1234

eyes = {
    "eye_0": {
        "expected_id": 0,
        "host": "192.168.0.102",
        "port": f"{unified_eyeserver_port}",
        "uri": "PYRO:",
        "name": "cobe.eye",
        "fisheye_calibration_map": "map_eye_0.npz"
    },
    # "eye_1": {
    #     "expected_id": 1,
    #     "host": "192.168.0.103",
    #     "port": f"{unified_eyeserver_port}",
    #     "uri": "PYRO:",
    #     "name": "cobe.eye",
    #     "fisheye_calibration_map": "map_eye_1.npz"
    # }
}