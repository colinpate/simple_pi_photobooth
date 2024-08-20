#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jan 18 18:34:53 2024

@author: patecolin
"""
import glob
import cv2 as cv
import pickle
import os
from PIL import Image
from datetime import datetime
import piexif

folder = "test_door"
bin_file = input("Cal file?")

images = glob.glob(folder + '/*.jpg')
print("Found", len(images))
print(images)
with open(bin_file + ".bin", "rb") as file_obj:
    newcameramtx, roi, mtx, dist = pickle.load(file_obj)
    
os.makedirs("remapped/" + folder, exist_ok=True)

for fname in images:
    print("Redoing", fname)
    img = cv.imread(fname)
    img = cv.cvtColor(img, cv.COLOR_BGR2RGB)
    imS = cv.resize(img, (int(img.shape[1] / 5), int(img.shape[0] / 5)))
    cv.imshow(f"Original {img.shape}", imS)
    
    dst = cv.undistort(img, mtx, dist, None, newcameramtx)
    #cv.waitKey(5000)
    
    x, y, w, h = roi
    dst = dst[y:y+h, x:x+w]
    imS = cv.resize(dst, (int(dst.shape[1] / 5), int(dst.shape[0] / 5)))
    #cv.imshow(f"imS cropped {w, h}", imS)
    #cv.waitKey(15000)
    #cv.imwrite("remapped/" + fname[:-4] + "_" + bin_file + ".jpg", dst)
    img = Image.fromarray(dst)

    # Set the JPEG quality (0 to 95)
    jpeg_quality = 95  # Adjust as needed
    
    # Get current date and time
    current_datetime = datetime.now()
    
    # Format the datetime according to EXIF DateTimeOriginal format
    formatted_datetime = current_datetime.strftime("%Y:%m:%d %H:%M:%S")
    #formatted_datetime = "2024:01:01 11:59:42"
    
    w, h = img.size
    zeroth_ifd = {piexif.ImageIFD.Make: "Canon",
              piexif.ImageIFD.XResolution: (w, 1),
              piexif.ImageIFD.YResolution: (h, 1),
              piexif.ImageIFD.Software: "piexif"
              }
    exif_ifd = {piexif.ExifIFD.DateTimeOriginal: formatted_datetime,
                piexif.ExifIFD.LensMake: "LensMake",
                piexif.ExifIFD.Sharpness: 65535,
                piexif.ExifIFD.LensSpecification: ((1, 1), (1, 1), (1, 1), (1, 1)),
                }
    exif_dict = {"0th":zeroth_ifd, "Exif":exif_ifd}
    exif_bytes = piexif.dump(exif_dict)
    
    # Save the modified image with specified JPEG quality
    image_path = "remapped/" + fname[:-4] + "_" + bin_file + ".jpg"
    img.save(image_path, quality=jpeg_quality, exif=exif_bytes)
    
    new_image = Image.open(image_path)
    print(new_image.info)
cv.destroyAllWindows()