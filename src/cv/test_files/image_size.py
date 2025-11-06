import cv2
import os

folder_path = r"C:\Personal-Project\vision-guided-tracker\src\cv\data\Rocket Tracking.v1i.yolov12\train\images"
count = 0
for filename in os.listdir(folder_path):

    if filename.endswith(".jpg") or filename.endswith(".png"):
        image_path = os.path.join(folder_path, filename)
        image = cv2.imread(image_path)
        if image is not None:
            height, width, channels = image.shape
            if count % 100 == 0:
                print(f"Image: {filename}, Width: {width}, Height: {height}, Channels: {channels}")
        else:
            print(f"Failed to load image: {filename}")
    count += 1
