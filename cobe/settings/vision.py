"""Configuration file holding all vision/camera/object detection related settings"""
import os

### Camera stream settings ###
flip_method = os.getenv("FLIP_METHOD", 2)
capture_width = os.getenv("CAPTURE_WIDTH", 3264)
capture_height = os.getenv("CAPTURE_HEIGHT", 2464)

display_width = os.getenv("DISPLAY_WIDTH", 320)  # fisheye calibration maps should be adjusted to this resolution
display_height = os.getenv("DISPLAY_HEIGHT", 240)  # fisheye calibration maps should be adjusted to this resolution
start_x = os.getenv("START_X", 0)  # start cropping from this x coordinate for display_width length
start_y = os.getenv("START_Y", 0)  # start cropping from this y coordinate for display_height length

end_x = min(start_x + display_width, capture_width)  # end cropping at this x coordinate
end_y = min(start_y + display_height, capture_height)  # end cropping at this y coordinate
frame_rate = os.getenv("FRAME_RATE", 5)

### Published MJPEG stream settings ###
publish_mjpeg_stream = os.getenv("PUBLISH_MJPEG_STREAM", True)
mjpeg_stream_port = os.getenv("MJPEG_STREAM_PORT", 8000)
