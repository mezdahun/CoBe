from cobe.cobe.cobemaster import CoBeMaster

def main():
    master = CoBeMaster()
    master.start()

def cleanup_inf_servers():
    """Cleans up the inference servers on all eyes"""
    master = CoBeMaster()
    master.cleanup_inference_servers()

def shutdown_eyes():
    """Shuts down all eyes"""
    master = CoBeMaster()
    master.shutdown_eyes()

def calibrate():
    """Test Calibration of all eyes interactively"""
    master = CoBeMaster()
    master.calibrator.generate_calibration_image(detach=True)
    master.calculate_calibration_maps(with_visualization=True, interactive=True, detach=True)