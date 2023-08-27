"""Configuration file holding all vision/camera/object detection related settings"""
import os

### Camera stream settings ###
# The stream is taken according to the available sensor modes with capture_width and capture_height resolution
# on framerate frame_rate. The stream is then cropped to crop_width and crop_height starting from start_x and
# start_y. The cropped image is then resized to display_width and display_height. The resized image is then
# flipped according to flip_method.
eye_version = "ORIN"  # "ORIN" or "JETSON"

flip_method = os.getenv("FLIP_METHOD", 2)
capture_width = os.getenv("CAPTURE_WIDTH", 3264)
capture_height = os.getenv("CAPTURE_HEIGHT", 2464)
start_x = os.getenv("START_X", 0)  # start cropping from this x coordinate for display_width length  345
start_y = os.getenv("START_Y", 0)  # start cropping from this y coordinate for display_height length  40
crop_width = os.getenv("CROP_WIDTH", 3264)  # crop the image to this width  2500
crop_height = os.getenv("CROP_HEIGHT", 2464)  # crop the image to this height  2500

display_width = os.getenv("DISPLAY_WIDTH", 1632)  # fisheye calibration maps should be adjusted to this resolution 416
display_height = os.getenv("DISPLAY_HEIGHT", 1234)  # fisheye calibration maps should be adjusted to this resolution 416

end_x = min(start_x + crop_width, capture_width)  # end cropping at this x coordinate
end_y = min(start_y + crop_height, capture_height)  # end cropping at this y coordinate
frame_rate = os.getenv("FRAME_RATE", 20)

### Published MJPEG stream settings ###
publish_mjpeg_stream = os.getenv("PUBLISH_MJPEG_STREAM", True)
mjpeg_stream_port = os.getenv("MJPEG_STREAM_PORT", 8000)

### Mapping parameters
# resolution of interpolated map
interp_map_res = os.getenv("INTERP_MAP_RES", 500)
# number of points to use for extrapolation on sides of map
extrap_skirt = 50

