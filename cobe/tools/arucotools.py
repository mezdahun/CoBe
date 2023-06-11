import cv2
import numpy as np

# Single tag parameters
code_content = 0
code_size = 100
pad_size = 30

# Calibration image parameters
# Resolution
width = 1640
height = 1232

# calculating how many codes fit on calibration image
num_tags_width = int(width / (code_size + 2 * pad_size))
num_tags_height = int(height / (code_size + 2 * pad_size))
print(f"In the calibration image we fit {num_tags_width} tags in width and {num_tags_height} tags in height")

# setting up aruco dictionary
aruco_type = cv2.aruco.DICT_ARUCO_ORIGINAL
aruco_dict = cv2.aruco.getPredefinedDictionary(aruco_type)
#
# # Generating calibration image
# calibration_image = np.ones((height, width), dtype=np.uint8) * 255
# for i in range(num_tags_height):
#     for j in range(num_tags_width):
#         code_content = i * num_tags_width + j
#         aruco_code = aruco_dict.generateImageMarker(code_content, code_size)
#         aruco_code = np.pad(aruco_code, pad_size, mode='constant', constant_values=255)
#         calibration_image[i * (code_size + 2 * pad_size):(i + 1) * (code_size + 2 * pad_size),
#                           j * (code_size + 2 * pad_size):(j + 1) * (code_size + 2 * pad_size)] = aruco_code
#
# # showing calibration image
# from matplotlib import pyplot as plt
# plt.imshow(calibration_image, cmap='gray')
# plt.show()
#
#
# detecting generated code
aruco_parameters = cv2.aruco.DetectorParameters()
detector = cv2.aruco.ArucoDetector()
detector.setDictionary(aruco_dict)
detector.setDetectorParameters(aruco_parameters)
#
# corners, ids, rejectedImgPoints = detector.detectMarkers(calibration_image)
# for i, id in enumerate(ids):
#     print(f"Detected code {id} with corners {corners[i]}")
#
# # visualizing detected codes
# aruco_image = cv2.aruco.drawDetectedMarkers(calibration_image, corners, ids)
# plt.imshow(aruco_image, cmap='gray')
# plt.show()

# read test.jpg and detect aruco codes on it
test_image = cv2.imread("test.jpg", cv2.IMREAD_GRAYSCALE)
corners, ids, rejectedImgPoints = detector.detectMarkers(test_image)
for i, id in enumerate(ids):
    print(f"Detected code {id} with corners {corners[i]}")

# visualizing detected codes
aruco_image = cv2.aruco.drawDetectedMarkers(test_image, corners, ids)
from matplotlib import pyplot as plt
plt.imshow(aruco_image)
plt.show()