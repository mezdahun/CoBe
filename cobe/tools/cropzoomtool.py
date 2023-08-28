import numpy as np
from matplotlib import pyplot as plt
import json
import os

json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "settings", "eye_dicts.json")

image = None
eye_name = None

plt.rcParams["figure.autolayout"] = True

start_x, start_y = None, None
end_x, end_y = None, None

def update_settings(start_x, start_y, end_x, end_y):
    print("Updating network settings...")
    # get upper right corner of crop
    crop_width = end_x - start_x
    crop_height = end_y - start_y

    upper_right_x = end_x
    upper_right_y = start_y

    img_width = image.shape[1]
    img_height = image.shape[0]

    # start_x will count from right to left
    start_x = img_width - upper_right_x
    start_y = upper_right_y
    print(f"start_x: {start_x}, start_y: {start_y}, crop_width: {crop_width}, crop_height: {crop_height}")

    # write settings back to json file
    # reading dictionary from yaml
    with open(json_path, 'r') as stream:
        eye_dicts = json.load(stream)
    eye_dicts[eye_name]["start_x"] = int(start_x)
    eye_dicts[eye_name]["start_y"] = int(start_y)
    eye_dicts[eye_name]["crop_width"] = int(crop_width)
    eye_dicts[eye_name]["crop_height"] = int(crop_height)

    # writing dictionary to json
    with open(json_path, 'w') as stream:
        json.dump(eye_dicts, stream, indent=4)

    print("Done writing json. Don't forget to commit/push the changes to the repository and restart the eyeserver(s).")

def report_coordinate():
    global start_x, start_y, end_x, end_y
    print(f"start_x: {start_x}, start_y: {start_y}, end_x: {end_x}, end_y: {end_y}")
    update = input("Do you want to update the settings? (y/n)")
    if update.lower() == "y":
        update_settings(start_x, start_y, end_x, end_y)
        # close all matplotlib windows
        plt.close('all')
    else:
        plt.clf()
        plt.title(f"Crop/Zoom Tool - {eye_name}\nClick/Draw/Release to crop arena with cursor")
        plt.imshow(image)
        plt.show()
        start_x, start_y = None, None
        end_x, end_y = None, None


def mouse_event_start(event):
    global start_x, start_y
    start_x, start_y = event.xdata, event.ydata
    print(f"Crop start at x: {start_x} and y: {start_y}")
    plt.scatter(start_x, start_y, c='green', s=50)
    plt.show()

def mouse_event_stop(event):
    global start_x, start_y, end_x, end_y
    end_x, end_y = event.xdata, event.ydata
    if start_x == end_x or start_y == end_y:
        start_x = None
        start_y = None
        end_x = None
        end_y = None

    ex, ey = event.xdata, event.ydata
    # making box aspect ratio 1:1
    if abs(ex - start_x) > abs(ey - start_y):
        ey = start_y + np.sign(ey - start_y) * abs(ex - start_x)
    else:
        ex = start_x + np.sign(ex - start_x) * abs(ey - start_y)

    # enforcing image shape if ex or ey larger than image
    if ex > image.shape[1]:
        ex = image.shape[1]
    if ey > image.shape[0]:
        ey = image.shape[0]

    end_x = ex
    end_y = ey

    print(f"Crop stop at x: {end_x} and y: {end_y}")
    if start_x is not None and start_y is not None:
        plt.hlines(start_y, start_x, end_x, colors='green', linestyles='solid')
        plt.hlines(end_y, start_x, end_x, colors='green', linestyles='solid')
        plt.vlines(start_x, start_y, end_y, colors='green', linestyles='solid')
        plt.vlines(end_x, start_y, end_y, colors='green', linestyles='solid')
    plt.scatter(start_x, start_y, c='green', s=50)
    plt.scatter(end_x, end_y, c='green', s=50)
    plt.show()
    report_coordinate()

def draw_event(event):
    # Showinga  dashed line between current mouse coordinates and starting point
    if start_x is not None and start_y is not None:
        # only draw if mouse is pressed
        if event.button != 1:
            return
        # clearing the previous lines
        ex, ey = event.xdata, event.ydata
        # making box aspect ratio 1:1
        if abs(ex - start_x) > abs(ey - start_y):
            ey = start_y + np.sign(ey - start_y) * abs(ex - start_x)
        else:
            ex = start_x + np.sign(ex - start_x) * abs(ey - start_y)

        # enforcing image shape if ex or ey larger than image
        if ex > image.shape[1]:
            ex = image.shape[1]
        if ey > image.shape[0]:
            ey = image.shape[0]

        plt.clf()
        plt.title(f"Crop/Zoom Tool - {eye_name}\nClick/Draw/Release to crop arena with cursor")
        plt.imshow(image)
        plt.scatter(start_x, start_y, c='green', s=50)
        plt.hlines(start_y, start_x, ex, colors='green', linestyles='dashed')
        plt.hlines(ey, start_x, ex, colors='green', linestyles='dashed')
        plt.vlines(start_x, start_y, ey, colors='green', linestyles='dashed')
        plt.vlines(ex, start_y, ey, colors='green', linestyles='dashed')
        plt.show()


def cropzoomparameters(target_eye_name, image_capture):
    global image, eye_name
    eye_name = target_eye_name
    image = image_capture
    fig = plt.figure()
    plt.title(f"Crop/Zoom Tool - {eye_name}\nClick/Draw/Release to crop arena with cursor")
    plt.imshow(image)
    cid = fig.canvas.mpl_connect('button_press_event', mouse_event_start)
    cid = fig.canvas.mpl_connect('button_release_event', mouse_event_stop)
    cid = fig.canvas.mpl_connect('motion_notify_event', draw_event)
    plt.show()
