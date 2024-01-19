#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jan 18 18:34:53 2024

@author: patecolin
"""
import glob
import cv2 as cv
import pickle

images = glob.glob('**/*.jpg', recursive=True)
print("Found", len(images))
print(images)
with open("lens_cal_good.bin", "rb") as file_obj:
    newcameramtx, roi, mtx, dist = pickle.load(file_obj)
    

for fname in images:
    print("Redoing", fname)
    img = cv.imread(fname)
    imS = cv.resize(img, (int(img.shape[1] / 4), int(img.shape[0] / 4)))
    cv.imshow(f"Original {img.shape}", imS)
    
    dst = cv.undistort(img, mtx, dist, None, newcameramtx)
    #cv.waitKey(5000)
    
    x, y, w, h = roi
    dst = dst[y:y+h, x:x+w]
    imS = cv.resize(dst, (int(dst.shape[1] / 4), int(dst.shape[0] / 4)))
    cv.imshow(f"imS cropped {w, h}", imS)
    cv.waitKey(5000)
cv.destroyAllWindows()