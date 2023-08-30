import cv2

aruco_type = cv2.aruco.DICT_ARUCO_ORIGINAL
aruco_dict = cv2.aruco.getPredefinedDictionary(aruco_type)
aruco_params = cv2.aruco.DetectorParameters()

# ARUCO code id to position mapping for calibration image
# calibration image size / size of projection space or arena
proj_calib_image_width = 4000
proj_calib_image_height = proj_calib_image_width

# single aruco code size
num_codes_per_row = 8
pad_size = 100
code_size = int(proj_calib_image_width / num_codes_per_row) - 2 * pad_size
if code_size < 50:
    raise Exception("Code size too small. Decrease number of codes per row or pad size")

# generating aruco code lookup for real projection coordinates
aruco_id_to_proj_pos = {}

num_tags_width = int(proj_calib_image_width / (code_size + 2 * pad_size))
num_tags_height = num_tags_width

# # Generating calibration image
# calibration_image = np.ones((height, width), dtype=np.uint8) * 255
for i in range(num_tags_height):
    for j in range(num_tags_width):
        code_content = i * num_tags_width + j
        xmin = i * (code_size + 2 * pad_size)
        xmax = (i + 1) * (code_size + 2 * pad_size)
        ymin = j * (code_size + 2 * pad_size)
        ymax = (j + 1) * (code_size + 2 * pad_size)
        center = (int((xmin + xmax) / 2), int((ymin + ymax) / 2))
        aruco_id_to_proj_pos[code_content] = center
