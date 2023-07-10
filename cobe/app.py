from cobe.cobe.cobemaster import CoBeMaster

def test_stream():
    """Test streaming of all eyes"""
    master = CoBeMaster()
    master.start_test_stream()

def collect_pngs():
    """Collects pngs from all eyes"""
    master = CoBeMaster()
    master.collect_images_from_stream()

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
    master.calibrate(with_visualization=True, interactive=True, detach=True)
    # master.calibrator.generate_calibration_image(detach=True)
