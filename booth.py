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
DISPLAY_S = 1200
PRE_CONTROL_S = 0.2

# Image and display
DISPLAY_WIDTH=1024
DISPLAY_HEIGHT=600
BORDER_WIDTH = 150
FULL_IMG_WIDTH = 4056
FULL_IMG_HEIGHT = 3040
PREV_STREAM_DIMS = (int(FULL_IMG_WIDTH / 2), int(FULL_IMG_HEIGHT / 2))
DISPLAY_IMG_WIDTH = int(DISPLAY_WIDTH - (BORDER_WIDTH * 2))
DISPLAY_IMG_HEIGHT = int(DISPLAY_IMG_WIDTH * FULL_IMG_HEIGHT / FULL_IMG_WIDTH)
#DISPLAY_IMG_HEIGHT = int(DISPLAY_HEIGHT - (BORDER_WIDTH * 2))
BORDER_HEIGHT = int((DISPLAY_HEIGHT - DISPLAY_IMG_HEIGHT) / 2)
#BORDER_HEIGHT = BORDER_WIDTH


FOCUS_MODE = False

if FOCUS_MODE:
    HCROP_RATIO = 1/8
else:
    HCROP_RATIO = 1
VCROP_RATIO = HCROP_RATIO
CROP_WIDTH = int(FULL_IMG_WIDTH * HCROP_RATIO)
CROP_HEIGHT = int(FULL_IMG_HEIGHT * VCROP_RATIO)
CROP_OFFSET_X = int((FULL_IMG_WIDTH - CROP_WIDTH) / 2)
#CROP_OFFSET_Y = int((FULL_IMG_HEIGHT - CROP_HEIGHT) / 2)
# Uncomment to aim downwards
CROP_OFFSET_Y = FULL_IMG_HEIGHT - CROP_HEIGHT
FULL_CROP_RECTANGLE = (
        CROP_OFFSET_X,
        CROP_OFFSET_Y, 
        CROP_WIDTH,
        CROP_HEIGHT,
    )
    
# Crop the preview vertically so it doesn't look weird
Y_RATIO = (DISPLAY_HEIGHT / DISPLAY_WIDTH) / (CROP_HEIGHT / CROP_WIDTH)
PREV_CROP_HEIGHT = int(CROP_HEIGHT * Y_RATIO)
PREV_CROP_OFFSET_Y = int((FULL_IMG_HEIGHT - PREV_CROP_HEIGHT) / 2)
PREV_CROP_RECTANGLE = (
        CROP_OFFSET_X,
        PREV_CROP_OFFSET_Y,
        CROP_WIDTH,
        PREV_CROP_HEIGHT
)

# Overlay stuff
colour = (255, 255, 255, 255)
#origin = (1152 - 125, 648 + 125)
origin = (int(FULL_IMG_WIDTH / 4 - 125), int(FULL_IMG_HEIGHT / 4 + 125))
font = cv2.FONT_HERSHEY_DUPLEX
scale = 12
thickness = 20

capture_overlay = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 4), dtype=np.uint8)
capture_overlay[:] = (255, 255, 255, 255)

BLACK_OVERLAY = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 4), dtype=np.uint8)
BLACK_OVERLAY[:]  = (0, 0, 0, 255)

SHUTDOWN_HOLD_TIME = 5


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
        
           
def display_capture(filename):
    qpicamera2.set_overlay(BLACK_OVERLAY)
    print("Displaying", filename)
    orig_image = cv2.imread(filename)
    gray_image = cv2.cvtColor(orig_image, cv2.COLOR_BGR2GRAY)
    rgba_image = cv2.cvtColor(gray_image, cv2.COLOR_GRAY2RGBA)
    new_dims = (DISPLAY_IMG_WIDTH, DISPLAY_IMG_HEIGHT)
    resized_image = cv2.resize(rgba_image, new_dims)
    overlay = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 4), dtype=np.uint8)
    overlay[:]  = (0, 0, 0, 255)
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
    
    
class PhotoBooth:
    def __init__(self):
        self.state = "idle"
        self.start_time = 0
        self.filename = ""
        self.idle_metadata = []
        self.mode_switched = False
        self.last_button_release = time.perf_counter()

    def apply_timestamp(self, request):
        if self.state == "countdown":
            countdown = str(COUNT_S - int(np.floor(time.perf_counter() - self.start_time)))
            with MappedArray(request, "lores") as m:
                cv2.putText(m.array, countdown, origin, font, scale, colour, thickness)
    
    def capture_done(self, job):
        metadata = picam2.wait(job)
        #self.idle_metadata.append(dict(metadata))
        #print(
        #    "Lux", int(metadata["Lux"]),
        #    "Gain", metadata["AnalogueGain"],
        #    "Exposure", int(metadata["ExposureTime"] / 1000)
        #)
        #print(self.state, time.perf_counter() - self.start_time)
        #set_leds(idle=True)
        if self.state == "display_capture":
            display_capture(self.filename)
            set_leds(idle=True)
        
    def check_shutdown_button(self):
        if not pi.read(BUTTON_PIN):
            if time.perf_counter() > (self.last_button_release + SHUTDOWN_HOLD_TIME):
                print("Shutting down")
                os.system("sudo shutdown now")
        else:
            self.last_button_release = time.perf_counter()
        
    def main_loop(self):
        self.check_shutdown_button()
        
        if self.state == "idle":
            #if not (int(time.perf_counter() * 10) % 10):
            #    picam2.capture_metadata(signal_function=qpicamera2.signal_done)
            if not pi.read(BUTTON_PIN):
                self.state = "countdown"
                self.start_time = time.perf_counter()
                self.idle_metadata = []
        elif self.state == "countdown":
            if time.perf_counter() >= (self.start_time + COUNT_S):
                self.state = "capture"
                self.mode_switched = False # Reset for next time
                set_capture_overlay()
            elif time.perf_counter() > (self.start_time + COUNT_S - PRE_CONTROL_S):
                if not self.mode_switched:
                    print("Switching mode")
                    set_leds(idle=False)
                    picam2.set_controls({
                            "ScalerCrop": FULL_CROP_RECTANGLE,
                            "Saturation": 1.0
                        })
                    self.mode_switched = True
            else:
                led_fade = (time.perf_counter() - self.start_time)/COUNT_S
                set_leds(fade=led_fade)
        elif self.state == "capture":
            self.state = "display_capture"
            self.start_time = time.perf_counter()
            self.filename = "/home/colin/booth_photos/" + time.strftime("%y_%m_%d_%H_%M_%S") + ".jpg"
            print("Saving to", self.filename)
            """picam2.switch_mode_and_capture_file(
                    config,
                    self.filename,
                    signal_function=qpicamera2.signal_done
                )"""
            picam2.capture_file(self.filename, signal_function=qpicamera2.signal_done)
        elif self.state == "display_capture":
            if time.perf_counter() >= (self.start_time + DISPLAY_S):
                self.state = "idle"
            elif not pi.read(BUTTON_PIN):
                self.start_time = time.perf_counter() 
                self.state = "countdown"
            else:
                return
            picam2.set_controls({
                    "ScalerCrop": PREV_CROP_RECTANGLE,
                    "Saturation": 0.0
                })
            qpicamera2.set_overlay(None)
            
photo_booth = PhotoBooth()
            
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
picam2.post_callback = photo_booth.apply_timestamp

config = picam2.create_still_configuration(lores={"size": PREV_STREAM_DIMS}, display="lores", buffer_count=2, transform=libcamera.Transform(hflip=1))
#config["controls"]["ScalerCrop"] = PREV_CROP_RECTANGLE
#config["controls"]["Saturation"] = 0
print(config)

if FOCUS_MODE:
    prev_config = picam2.create_preview_configuration({"size": (FULL_IMG_WIDTH, FULL_IMG_HEIGHT)})
else:
    prev_config = picam2.create_preview_configuration({"size": PREV_STREAM_DIMS}, transform=libcamera.Transform(hflip=1))
    prev_config["controls"]["Saturation"] = 0
prev_config["controls"]["ScalerCrop"] = PREV_CROP_RECTANGLE
print(prev_config)
picam2.configure(config)

app = QApplication([])
qpicamera2 = QGlPicamera2(picam2, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT, keep_ar=False)
qpicamera2.timer = QtCore.QTimer()
qpicamera2.timer.start(25)
qpicamera2.timer.timeout.connect(photo_booth.main_loop)
qpicamera2.done_signal.connect(photo_booth.capture_done)
qpicamera2.setWindowFlag(QtCore.Qt.FramelessWindowHint)
qpicamera2.resize(DISPLAY_WIDTH, DISPLAY_HEIGHT)

picam2.start()
#picam2.set_controls({"AfMode": controls.AfModeEnum.Continuous})
#picam2.set_controls({"AeConstraintMode": controls.AeConstraintModeEnum.Highlight}) Seems to do nothing
picam2.set_controls({"Sharpness": 1})
picam2.set_controls({
        "ScalerCrop": PREV_CROP_RECTANGLE,
        "Saturation": 0.0
    })
print(picam2.camera_properties)
qpicamera2.show()
app.exec()

