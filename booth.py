import cv2
from picamera2 import Picamera2, Preview, MappedArray
from picamera2.previews.qt import QGlPicamera2
import libcamera
from libcamera import controls
import time
import pigpio
from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication
import numpy as np
import os

# GPIO
BUTTON_PIN = 23 # GPIO number (header pin 16)
LED_WARM_PIN = 24
LED_COOL_PIN = 25
LED_WARM_IDLE_DC = 63
LED_COOL_IDLE_DC = 63
LED_WARM_CAPTURE_DC = 255
LED_COOL_CAPTURE_DC = 255

# Lighting
CAPTURE_LUX=200
CAPTURE_MODE_LUX_RATIO = 0.5

# Timing
COUNT_S = 3
DISPLAY_S = 30
PRE_FLASH_S = 1

# Image and display
WIDTH=1024
HEIGHT=600
BORDER_WIDTH = 150
IMG_WIDTH = 4056 * 2
IMG_HEIGHT = 3040 * 2
PREV_STREAM_DIMS = (int(IMG_WIDTH / 2), int(IMG_HEIGHT / 2))
DISPLAY_IMG_WIDTH = int(WIDTH - (BORDER_WIDTH * 2))
#DISPLAY_IMG_HEIGHT = int(DISPLAY_IMG_WIDTH * IMG_HEIGHT / IMG_WIDTH)
DISPLAY_IMG_HEIGHT = int(HEIGHT - (BORDER_WIDTH * 2))
BORDER_HEIGHT = int((HEIGHT - DISPLAY_IMG_HEIGHT) / 2)


FOCUS_MODE = False

if FOCUS_MODE:
    HCROP_RATIO = 1/16#42.9/68.5
else:
    HCROP_RATIO = 6.287/7.7#42.9/68.5
VCROP_RATIO = HCROP_RATIO#4.71/3.63*HCROP_RATIO
CROP_WIDTH = int(IMG_WIDTH * HCROP_RATIO)
CROP_HEIGHT = int(IMG_HEIGHT * VCROP_RATIO)
if FOCUS_MODE:
    CROP_OFFSET_X = int(IMG_WIDTH / 4)
    CROP_OFFSET_Y = int(IMG_HEIGHT / 4)
else:
    CROP_OFFSET_X = int((IMG_WIDTH - CROP_WIDTH) / 2)
    CROP_OFFSET_Y = int((IMG_HEIGHT - CROP_HEIGHT) / 2)
#CROP_OFFSET_Y = IMG_HEIGHT - CROP_HEIGHT
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
start_time = 0
filename = ""
idle_metadata = []


def set_leds(idle=True, fade=0):
    if fade:
        warm_dc_spread = LED_WARM_CAPTURE_DC - LED_WARM_IDLE_DC
        cool_dc_spread = LED_COOL_CAPTURE_DC - LED_COOL_IDLE_DC
        warm_dc = min(255, int(warm_dc_spread * fade + LED_WARM_IDLE_DC))
        cool_dc = min(255, int(cool_dc_spread * fade + LED_COOL_IDLE_DC))
        pi.set_PWM_dutycycle(LED_WARM_PIN, warm_dc)
        pi.set_PWM_dutycycle(LED_COOL_PIN, cool_dc)
    else:
        if idle:
            pi.set_PWM_dutycycle(LED_WARM_PIN, LED_WARM_IDLE_DC)
            pi.set_PWM_dutycycle(LED_COOL_PIN, LED_COOL_IDLE_DC)
        else:
            pi.set_PWM_dutycycle(LED_WARM_PIN, LED_WARM_CAPTURE_DC)
            pi.set_PWM_dutycycle(LED_COOL_PIN, LED_COOL_CAPTURE_DC)
    

def apply_timestamp(request):
    if state == "countdown":
        #timestamp = time.strftime("%Y-%m-%d %X")
        countdown = str(COUNT_S - int(np.floor(time.perf_counter() - start_time)))
        with MappedArray(request, "main") as m:
            cv2.putText(m.array, countdown, origin, font, scale, colour, thickness)
        
            
def capture_done(job):
    metadata = picam2.wait(job)
    idle_metadata.append(dict(metadata))
    print(metadata["Lux"], metadata["AnalogueGain"], metadata["ExposureTime"], time.perf_counter() - start_time)
    if state == "display_capture":
        #picam2.set_controls({"AeEnable": False})
        set_leds(idle=True)
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
    
    
def set_exposure(metadata_list):
    average_lux = np.average([x["Lux"] for x in metadata_list])
    average_gain = np.average([x["AnalogueGain"] for x in metadata_list])
    average_exp = np.average([x["ExposureTime"] for x in metadata_list])
    print("Averages")
    print(average_lux, average_gain, average_exp)
    #picam2.set_controls({"AeEnable": False})
    exposure_ratio = average_lux / (CAPTURE_LUX + average_lux)
    new_exposure = int(average_exp * exposure_ratio)
    print("New exposure", new_exposure)
    #picam2.set_controls({"ExposureTime": new_exposure})
    

def main_loop():
    global state
    global start_time
    global filename
    global idle_metadata
    
    if state == "idle":
        if not pi.read(BUTTON_PIN):
            state = "countdown"
            start_time = time.perf_counter()
            idle_metadata = []
    elif state == "countdown":
        set_leds(fade=(time.perf_counter() - start_time)/COUNT_S)
        #if time.perf_counter() >= (start_time + PRE_FLASH_S):
        #    set_leds(idle=False)
        #else:
        #    set_leds(idle=True)
        #    set_exposure(idle_metadata)
        #picam2.capture_metadata(signal_function=qpicamera2.signal_done)
        if time.perf_counter() >= (start_time + COUNT_S):
            state = "capture"
    elif state == "capture":
        set_leds(idle=False)
        set_capture_overlay()
        filename = "/home/colin/booth_photos/" + time.strftime("%y_%m_%d_%X") + ".jpg"
        print("Saving to", filename)
        picam2.switch_mode_and_capture_file(
                config,
                filename,
                signal_function=qpicamera2.signal_done
            )
        state = "display_capture"
        start_time = time.perf_counter()
    elif state == "display_capture":
        if time.perf_counter() >= (start_time + DISPLAY_S):
            qpicamera2.set_overlay(None)
            state = "idle"
        elif not pi.read(BUTTON_PIN):
            qpicamera2.set_overlay(None)
            start_time = time.perf_counter() 
            state = "countdown"
            
        
pi = pigpio.pi()
pi.set_mode(BUTTON_PIN, pigpio.INPUT)
pi.set_pull_up_down(BUTTON_PIN, pigpio.PUD_UP)
pi.set_mode(LED_COOL_PIN, pigpio.OUTPUT)
pi.set_mode(LED_WARM_PIN, pigpio.OUTPUT)
pi.set_PWM_frequency(LED_COOL_PIN, 400)
pi.set_PWM_frequency(LED_WARM_PIN, 400)
set_leds(idle=True)
            
picam2 = Picamera2()
picam2.options["quality"] = 95
picam2.pre_callback = apply_timestamp

config = picam2.create_still_configuration()
config["controls"]["ScalerCrop"] = CROP_RECTANGLE
config["controls"]["Saturation"] = 1.0
if FOCUS_MODE:
    prev_config = picam2.create_preview_configuration({"size": PREV_STREAM_DIMS}, transform=libcamera.Transform(hflip=1))
else:
    prev_config = picam2.create_preview_configuration(transform=libcamera.Transform(hflip=1))
    prev_config["controls"]["Saturation"] = 0
prev_config["controls"]["ScalerCrop"] = CROP_RECTANGLE
picam2.configure(prev_config)

app = QApplication([])
qpicamera2 = QGlPicamera2(picam2, width=WIDTH, height=HEIGHT, keep_ar=True)
qpicamera2.timer = QtCore.QTimer()
qpicamera2.timer.start(100)
qpicamera2.timer.timeout.connect(main_loop)
qpicamera2.done_signal.connect(capture_done)
qpicamera2.setWindowFlag(QtCore.Qt.FramelessWindowHint)
qpicamera2.resize(WIDTH, HEIGHT)

picam2.start()
#picam2.set_controls({"AfMode": controls.AfModeEnum.Continuous})
picam2.set_controls({"AeConstraintMode": controls.AeConstraintModeEnum.Highlight})
picam2.set_controls({"Sharpness": 2})
print(picam2.camera_properties)
#print("Controls")
#for control in picam2.camera_controls.items():
#    print(control)
#exit()
qpicamera2.show()
app.exec()

