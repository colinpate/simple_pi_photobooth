import cv2
from picamera2 import Picamera2, Preview, MappedArray
from picamera2.previews.qt import QGlPicamera2
import libcamera
from libcamera import controls
import time
import RPi.GPIO as GPIO
from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication
import numpy as np

COUNT_S = 3
DISPLAY_S = 1200
BUTTON_PIN = 16 # Header pin number
WIDTH=1024
HEIGHT=600
BORDER_WIDTH = 50
IMG_WIDTH = 2304 * 2
IMG_HEIGHT = 1296 * 2
DISPLAY_IMG_WIDTH = int(WIDTH - (BORDER_WIDTH * 2))
DISPLAY_IMG_HEIGHT = int(DISPLAY_IMG_WIDTH * IMG_HEIGHT / IMG_WIDTH)
BORDER_HEIGHT = int((HEIGHT - DISPLAY_IMG_HEIGHT) / 2)

CROP_RATIO = 0.9
CROP_WIDTH = int(IMG_WIDTH * CROP_RATIO)
CROP_HEIGHT = int(IMG_HEIGHT * CROP_RATIO)
CROP_OFFSET_X = int((IMG_WIDTH - CROP_WIDTH) / 2)
CROP_OFFSET_Y = IMG_HEIGHT - CROP_HEIGHT
CROP_RECTANGLE = (
        CROP_OFFSET_X,
        CROP_OFFSET_Y, 
        CROP_WIDTH,
        CROP_HEIGHT
    )

# Overlay stuff
colour = (255, 255, 255, 255)
origin = (1152 - 125, 648 + 125)
font = cv2.FONT_HERSHEY_DUPLEX
scale = 12
thickness = 20

capture_overlay = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
capture_overlay[:] = (255, 255, 255, 255)

# Variables
state = "idle"
button_pressed = False
start_time = 0
filename = ""
capture_done = False


def apply_timestamp(request):
    if state == "countdown":
        #timestamp = time.strftime("%Y-%m-%d %X")
        countdown = str(COUNT_S - int(np.floor(time.perf_counter() - start_time)))
        with MappedArray(request, "main") as m:
            cv2.putText(m.array, countdown, origin, font, scale, colour, thickness)
        
            
def capture_done(job):
    result = picam2.wait(job)
    print("Displaying", filename)
    display_capture(filename)
        
           
def display_capture(filename):
    overlay = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
    overlay[:] = (0, 0, 0, 255)
    qpicamera2.set_overlay(overlay)
    orig_image = cv2.imread(filename)
    gray_image = cv2.cvtColor(orig_image, cv2.COLOR_BGR2GRAY)
    rgba_image = cv2.cvtColor(gray_image, cv2.COLOR_GRAY2RGBA)
    new_dims = (DISPLAY_IMG_WIDTH, DISPLAY_IMG_HEIGHT)
    resized_image = cv2.resize(rgba_image, new_dims)
    overlay[BORDER_HEIGHT:BORDER_HEIGHT+DISPLAY_IMG_HEIGHT,BORDER_WIDTH:BORDER_WIDTH+DISPLAY_IMG_WIDTH] = resized_image
    qpicamera2.set_overlay(overlay)
    cv2.imwrite(filename[:-4] + "_gray.jpg", gray_image)
    

def set_capture_overlay():
    qpicamera2.set_overlay(capture_overlay)
    

def main_loop():
    global state
    global button_pressed
    global start_time
    global filename
    
    if state == "idle":
        if not GPIO.input(BUTTON_PIN):
            state = "countdown"
            start_time = time.perf_counter()
    elif state == "countdown":
        if time.perf_counter() >= (start_time + COUNT_S):
            state = "capture"
    elif state == "capture":
        set_capture_overlay()
        filename = "/home/colin/booth_photos/" + time.strftime("%y-%m-%d %X.jpg")
        print("Saving to", filename)
        picam2.switch_mode_and_capture_file(config, filename, signal_function=qpicamera2.signal_done)
        state = "display_capture"
        start_time = time.perf_counter()
    elif state == "display_capture":
        if time.perf_counter() >= (start_time + DISPLAY_S):
            qpicamera2.set_overlay(None)
            state = "idle"
        elif not GPIO.input(BUTTON_PIN):
            qpicamera2.set_overlay(None)
            start_time = time.perf_counter() 
            state = "countdown"
            
        
GPIO.setmode(GPIO.BOARD)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
picam2 = Picamera2()
picam2.options["quality"] = 95
picam2.pre_callback = apply_timestamp

config = picam2.create_still_configuration(transform=libcamera.Transform(hflip=1))
config["controls"]["ScalerCrop"] = CROP_RECTANGLE
config["controls"]["Saturation"] = 1.0
prev_config = picam2.create_preview_configuration({"size": (2304, 1296)}, transform=libcamera.Transform(hflip=1))
prev_config["controls"]["ScalerCrop"] = CROP_RECTANGLE
prev_config["controls"]["Saturation"] = 0
picam2.configure(prev_config)

app = QApplication([])
qpicamera2 = QGlPicamera2(picam2, width=WIDTH, height=HEIGHT, keep_ar=False)
qpicamera2.timer = QtCore.QTimer()
qpicamera2.timer.start(100)
qpicamera2.timer.timeout.connect(main_loop)
qpicamera2.done_signal.connect(capture_done)
qpicamera2.setWindowFlag(QtCore.Qt.FramelessWindowHint)
qpicamera2.resize(WIDTH, HEIGHT)

picam2.start()
picam2.set_controls({"AfMode": controls.AfModeEnum.Continuous})
qpicamera2.show()
app.exec()

