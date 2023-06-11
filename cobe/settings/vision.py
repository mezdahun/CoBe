"""Configuration file holding all vision/camera/object detection related settings"""
import os

### Parameters of Object Detector ###
# api_key = os.getenv("OD_API_KEY", "")
# model_name = os.getenv("OD_MODEL_NAME", "default")
# model_id = os.getenv("OD_MODEL_ID", "/default")
# version = os.getenv("OD_VERSION", "1")

### Camera stream settings ###
flip_method = os.getenv("FLIP_METHOD", 2)
capture_width = os.getenv("CAPTURE_WIDTH", 1280)  # fisheye calibration maps should be adjusted to this resolution
capture_height = os.getenv("CAPTURE_HEIGHT", 720)  # fisheye calibration maps should be adjusted to this resolution
frame_rate = os.getenv("FRAME_RATE", 5)

### Published MJPEG stream settings ###
publish_mjpeg_stream = os.getenv("PUBLISH_MJPEG_STREAM", False)
mjpeg_stream_port = os.getenv("MJPEG_STREAM_PORT", 8000)
