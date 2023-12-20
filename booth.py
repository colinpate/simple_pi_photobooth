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
LED_WARM_IDLE_DC = 40
LED_COOL_IDLE_DC = 40
LED_WARM_CAPTURE_DC = 255
LED_COOL_CAPTURE_DC = 255
#LED_WARM_IDLE_DC = 0
#LED_COOL_IDLE_DC = 0
#LED_WARM_CAPTURE_DC = 64
#LED_COOL_CAPTURE_DC = 64

# Timing
DISPLAY_S = 1200 #for real
SHUTDOWN_HOLD_TIME = 4

# Capture sequence timing
LED_FADE_S = 2 # How long before capture to start brightening LEDs
LED_END_S = 1 # How long before capture to hit 100% brightness
EXPOSURE_SET_S = 1.5 # How long before capture to set exposure
PRE_CONTROL_S = 0.2 # How long before capture to set the camera controls
COUNT_S = 5

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
PREV_SATURATION = 0.0 # 0 for Black and White

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


def set_leds(idle=True, fade=0):
    if fade:
        warm_fade = LED_WARM_CAPTURE_DC - LED_WARM_IDLE_DC
        cool_fade = LED_COOL_CAPTURE_DC - LED_COOL_IDLE_DC
        fade = max(min(fade, 1), 0)
        warm_dc = min(255, int(warm_fade * fade + LED_WARM_IDLE_DC))
        cool_dc = min(255, int(cool_fade * fade + LED_COOL_IDLE_DC))
        pi.set_PWM_dutycycle(LED_WARM_PIN, warm_dc)
        pi.set_PWM_dutycycle(LED_COOL_PIN, cool_dc)
    else:
        if idle:
            pi.set_PWM_dutycycle(LED_WARM_PIN, LED_WARM_IDLE_DC)
            pi.set_PWM_dutycycle(LED_COOL_PIN, LED_COOL_IDLE_DC)
        else:
            pi.set_PWM_dutycycle(LED_WARM_PIN, LED_WARM_CAPTURE_DC)
            pi.set_PWM_dutycycle(LED_COOL_PIN, LED_COOL_CAPTURE_DC)
    

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
        self.mode_switched = False
        self.exposure_set = False
        
        # Defaults
        self.exposure_settings = {
            "AnalogueGain": 1,
            "ExposureTime": 30000,
        }
        
        self.last_button_release = time.perf_counter()
        self.capture_start_time = time.perf_counter()

    def apply_timestamp(self, request):
        if self.state == "countdown":
            countdown = str(COUNT_S - int(np.floor(time.perf_counter() - self.start_time)))
            with MappedArray(request, "lores") as m:
                cv2.putText(m.array, countdown, origin, font, scale, colour, thickness)
    
    def capture_done(self, job):
        (self.image_array,), metadata = picam2.wait(job)
        set_leds(idle=True)
        print("Capture time", time.perf_counter() - self.capture_start_time)
        self.exposure_settings = {
            "AnalogueGain": metadata["AnalogueGain"],
            "ExposureTime": metadata["ExposureTime"],
        }
        print(self.exposure_settings)
        print(metadata)
        if self.state == "display_capture":
            self.display_capture()
    
    def display_capture(self):
        qpicamera2.set_overlay(BLACK_OVERLAY)
        orig_image = cv2.cvtColor(self.image_array, cv2.COLOR_BGR2RGB)
        gray_image = cv2.cvtColor(orig_image, cv2.COLOR_RGB2GRAY)
        rgba_image = cv2.cvtColor(gray_image, cv2.COLOR_GRAY2RGBA)
        new_dims = (DISPLAY_IMG_WIDTH, DISPLAY_IMG_HEIGHT)
        resized_image = cv2.resize(rgba_image, new_dims)
        overlay = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 4), dtype=np.uint8)
        overlay[:]  = (0, 0, 0, 255)
        overlay[BORDER_HEIGHT:BORDER_HEIGHT+DISPLAY_IMG_HEIGHT,BORDER_WIDTH:BORDER_WIDTH+DISPLAY_IMG_WIDTH] = resized_image
        qpicamera2.set_overlay(overlay)
        cv2.imwrite(self.filename[:-4] + "_gray.jpg", gray_image)
        cv2.imwrite(self.filename, orig_image)
        
    def check_shutdown_button(self):
        if not pi.read(BUTTON_PIN):
            if time.perf_counter() > (self.last_button_release + SHUTDOWN_HOLD_TIME):
                print("Shutting down")
                pi.set_PWM_dutycycle(LED_WARM_PIN, 0)
                pi.set_PWM_dutycycle(LED_COOL_PIN, 0)
                os.system("sudo shutdown now")
        else:
            self.last_button_release = time.perf_counter()
        
    def main_loop(self):
        self.check_shutdown_button()
        
        if self.state == "idle":
            if not pi.read(BUTTON_PIN):
                self.state = "countdown"
                self.start_time = time.perf_counter()
        elif self.state == "countdown":
            if time.perf_counter() >= (self.start_time + COUNT_S):
                print("Capturing at", (time.perf_counter() - self.start_time))
                self.state = "capture"
                self.exposure_set = False # Reset for next time
                self.mode_switched = False # Reset for next time
                self.capture_start_time = time.perf_counter()
                set_capture_overlay()
            else:
                if time.perf_counter() > (self.start_time + COUNT_S - LED_FADE_S):
                    time_to_photo = COUNT_S - (time.perf_counter() - self.start_time)
                    led_fade = (LED_FADE_S - time_to_photo) / (LED_FADE_S - LED_END_S)
                    set_leds(fade=led_fade)
                    
                if time.perf_counter() >= (self.start_time + COUNT_S - EXPOSURE_SET_S):
                    if not self.exposure_set:
                        print("Setting exposure at", (time.perf_counter() - self.start_time))
                        picam2.set_controls(
                            self.exposure_settings
                        )
                        self.exposure_set = True
                    else:
                        picam2.set_controls({"AeEnable": True})
                        
                if time.perf_counter() > (self.start_time + COUNT_S - PRE_CONTROL_S):
                    if not self.mode_switched:
                        print("Switching mode at", (time.perf_counter() - self.start_time))
                        picam2.set_controls({
                                "ScalerCrop": FULL_CROP_RECTANGLE,
                                "Saturation": 1.0,
                            })
                        self.mode_switched = True
                        
        elif self.state == "capture":
            self.state = "display_capture"
            self.start_time = time.perf_counter()
            self.filename = "/home/colin/booth_photos/" + time.strftime("%y_%m_%d_%H_%M_%S") + ".jpg"
            print("Saving to", self.filename)
            picam2.capture_arrays(["main"], signal_function=qpicamera2.signal_done)
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
                    "Saturation": PREV_SATURATION,
                    "AeEnable": True,
                })
            qpicamera2.set_overlay(None)
            
photo_booth = PhotoBooth()
            
pi = pigpio.pi()
pi.set_mode(BUTTON_PIN, pigpio.INPUT)
pi.set_pull_up_down(BUTTON_PIN, pigpio.PUD_UP)
pi.set_mode(LED_COOL_PIN, pigpio.OUTPUT)
pi.set_mode(LED_WARM_PIN, pigpio.OUTPUT)
pi.set_PWM_frequency(LED_COOL_PIN, 1600)
pi.set_PWM_frequency(LED_WARM_PIN, 1600)
set_leds(idle=True)
            
picam2 = Picamera2()
picam2.options["quality"] = 95
picam2.post_callback = photo_booth.apply_timestamp

config = picam2.create_still_configuration(
        #main={'size': (4056, 3040), 'format': 'YUV420'},
        lores={"size": PREV_STREAM_DIMS, 'format': 'YUV420'},
        display="lores",
        buffer_count=2,
        transform=libcamera.Transform(hflip=1)
    )
print("Camera config:")
print(config)

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
if not FOCUS_MODE:
    picam2.set_controls({
        "Sharpness": 1,
        "Saturation": PREV_SATURATION
        })
picam2.set_controls({"AeEnable": True})
picam2.set_controls({"ScalerCrop": PREV_CROP_RECTANGLE})

# Uncomment for light testing
#picam2.set_controls({"AeEnable": False})
#picam2.set_controls({"ExposureTime": 30400, "AnalogueGain": 4.0})

print("Camera properties")
print(picam2.camera_properties)
qpicamera2.show()
app.exec()

