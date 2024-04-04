#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jan 18 17:11:14 2024

@author: patecolin
"""

import numpy as np
import cv2 as cv
import glob
import pickle
from pprint import *
import tqdm

rows=8
cols=6
#rows=9
#cols=7

# termination criteria
criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 30, 0.001)
# prepare object points, like (0,0,0), (1,0,0), (2,0,0) ....,(6,5,0)
objp = np.zeros((rows*cols,3), np.float32)
objp[:,:2] = np.mgrid[0:rows,0:cols].T.reshape(-1,2)

# Arrays to store object points and image points from all the images.
objpoints = [] # 3d point in real world space
imgpoints = [] # 2d points in image plane.
images = []
#images += glob.glob('v1/*.jpg', recursive=True)
#images += glob.glob('v2/*.jpg', recursive=True)
#images += glob.glob('v3/*.jpg', recursive=True)
#images += glob.glob('v4/*.jpg', recursive=True)
#images += glob.glob('v5/*.jpg', recursive=True)
#images += glob.glob('circles_v1/*.jpg', recursive=True)
#images += glob.glob('circles_v2/*.jpg', recursive=True)
images += glob.glob('v6_6by8/*.jpg', recursive=True)

print("Found", len(images))
#print(images)

for fname in tqdm.tqdm(images):
    #print("Reading", fname)
    img = cv.imread(fname)
    gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
    #print("Converting color and finding corners")
    # Find the chess board corners
    ret, corners = cv.findChessboardCorners(gray, (cols,rows), cv.CALIB_CB_FAST_CHECK)
    #ret, corners = cv.findCirclesGrid(img, (cols, rows), flags=cv.CALIB_CB_CLUSTERING | cv.CALIB_CB_ASYMMETRIC_GRID)
    # If found, add object points, image points (after refining them)
    if ret == True:
        #print("Found corners")
        objpoints.append(objp)
        corners2 = cv.cornerSubPix(gray,corners, (11,11), (-1,-1), criteria)
        imgpoints.append(corners2)
        # Draw and display the corners
        cv.drawChessboardCorners(img, (cols,rows), corners2, ret)
        #cv.imwrite(fname[:-4] + "_corners.jpg", img)
        imS = cv.resize(img, (int(img.shape[1] / 6), int(img.shape[0] / 6)))
        cv.imshow("imS", imS)
        cv.waitKey(5000)
cv.destroyAllWindows()

print(img.shape)

f = open("lens_cal.bin", "wb")
ret, mtx, dist, rvecs, tvecs = cv.calibrateCamera(objpoints, imgpoints, gray.shape[::-1], None, None, flags=
                                                  #cv.CALIB_FIX_K3 |
                                                  cv.CALIB_FIX_ASPECT_RATIO |
                                                  #cv.CALIB_ZERO_TANGENT_DIST |
                                                  0)
print("Reprojection error", ret)
print("Matrix")
pprint(mtx)
print("Center x, y:", int(mtx[0, 2]), int(mtx[1, 2]))
print("Fx, Fy:", int(mtx[0, 0]), int(mtx[1, 1]))
print("distortion coeffs", dist)
h,  w = gray.shape[:2]
newcameramtx, roi = cv.getOptimalNewCameraMatrix(mtx, dist, (w,h), 1, (w,h))
pickle.dump([newcameramtx, roi, mtx, dist], f)
f.close()



