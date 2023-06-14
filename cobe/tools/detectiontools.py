import cv2
def annotate_detections(img, preds):
    """Annotating the image with bounding boxes and labels"""
    for pred in preds:
        # getting bounding box coordinates
        print(img.shape)
        xmin = max(int(pred["x"] - (pred["width"] / 2)), 0)
        xmax = min(int(xmin + pred["width"]), img.shape[1])
        ymin = max(int(pred["y"] - (pred["height"] / 2)), 0)
        ymax = min(int(ymin + pred["height"]), img.shape[0])
        # getting label
        label = pred["class"] + " " + str(round(pred["confidence"], 2))
        # drawing bounding box
        cv2.rectangle(img, (xmin, ymin), (xmax, ymax), (0, 255, 0), 2)
        # adding label
        cv2.putText(img, label, (xmin, ymin - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (36, 255, 12), 2)
    return img