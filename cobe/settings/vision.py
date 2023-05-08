"""Configuration file holding all vision/camera/object detection related settings"""
import os

### Parameters of Object Detector ###
# api_key = os.getenv("OD_API_KEY", "")
# model_name = os.getenv("OD_MODEL_NAME", "default")
# model_id = os.getenv("OD_MODEL_ID", "/default")
# version = os.getenv("OD_VERSION", "1")

### Camera stream settings ###
flip_method = os.getenv("FLIP_METHOD", 2)
capture_width = os.getenv("CAPTURE_WIDTH", 320)
capture_height = os.getenv("CAPTURE_HEIGHT", 240)
frame_rate = os.getenv("FRAME_RATE", 5)