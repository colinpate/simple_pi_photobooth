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
import yaml
import random
import glob
from pprint import *

def load_config():
    parent_dir = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(parent_dir, "config.yaml")
    with open(config_path, "r") as config_file:
        config = yaml.load(config_file, yaml.Loader)
    return config

config = load_config() #TODO make this be in a function LOL

# GPIO
BUTTON_PIN = 14 # GPIO number (header pin 16)
LED_BUTTON_PIN = 18
LED_COOL_PIN = 25
LED_COOL_IDLE_DC = config["led_idle_brightness"]
LED_COOL_CAPTURE_DC = config["led_capture_brightness"] # for testing
BUTTON_PULSE_TIME = config["button_pulse_time"]
#LED_COOL_CAPTURE_DC = 255

# Timing
#DISPLAY_S = 1200 #for real
DISPLAY_S = config["display_timeout"]
SHUTDOWN_HOLD_TIME = 4

# Capture sequence timing
LED_FADE_S = 2 # How long before capture to start brightening LEDs
LED_END_S = 1 # How long before capture to hit 100% brightness
EXPOSURE_SET_S = 1.4 # How long before capture to set exposure
PRE_CONTROL_S = 0.3 # How long before capture to set the camera controls
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
BORDER_HEIGHT = int((DISPLAY_HEIGHT - DISPLAY_IMG_HEIGHT) / 2)

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
CROP_OFFSET_Y = int((FULL_IMG_HEIGHT - CROP_HEIGHT) / 2)
# Uncomment to aim downwards
# CROP_OFFSET_Y = FULL_IMG_HEIGHT - CROP_HEIGHT
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
        cool_fade = LED_COOL_CAPTURE_DC - LED_COOL_IDLE_DC
        fade = max(min(fade, 1), 0)
        cool_dc = min(255, int(cool_fade * fade + LED_COOL_IDLE_DC))
        pi.set_PWM_dutycycle(LED_COOL_PIN, cool_dc)
    else:
        if idle:
            pi.set_PWM_dutycycle(LED_COOL_PIN, LED_COOL_IDLE_DC)
        else:
            pi.set_PWM_dutycycle(LED_COOL_PIN, LED_COOL_CAPTURE_DC)
    

def set_capture_overlay():
    qpicamera2.set_overlay(capture_overlay)
    
    
class PhotoBooth:
    def __init__(self, config):
        self.state = "idle"
        self.start_time = 0
        self.cap_timestamp_str = ""
        self.mode_switched = False
        self.exposure_set = False
        self.display_file_list = []
        self._config = config
        self.timestamps = {}
        
        os.makedirs(self._config["gray_image_dir"], exist_ok=True)
        os.makedirs(self._config["color_image_dir"], exist_ok=True)
        
        # Defaults
        self.exposure_settings = {
            "AnalogueGain": 1,
            "ExposureTime": 30000,
        }
        
        self.last_button_release = time.perf_counter()
        self.capture_start_time = time.perf_counter()

    def apply_timestamp(self, request):
        if self.state == "countdown":
            metadata = request.get_metadata()
            perf_counter = time.perf_counter()
            print(
                f"{int((perf_counter - self.timestamps.get('write', 0)) * 1000):3d}",
                "ena", metadata.get("AeEnable", ""),
                "loc", metadata.get("AeLocked", ""),
                "sat", metadata.get("Saturation", ""),
            )
            self.timestamps["write"] = perf_counter
            countdown = str(COUNT_S - int(np.floor(perf_counter - self.start_time)))
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
        print(
                "CAP",
                "ena", metadata.get("AeEnable", ""),
                "loc", metadata.get("AeLocked", ""),
                "sat", metadata.get("Saturation", ""),
            )
        #pprint(metadata)
        if self.state == "display_capture":
            qpicamera2.set_overlay(BLACK_OVERLAY)
            gray, color = self.save_capture()
            if self._config["display_gray"]:
                image, image_path = gray
            else:
                image, image_path = color
            self.display_image(image)
            self.display_file_list.append(image_path)
    
    def save_capture(self):
        orig_image = cv2.cvtColor(self.image_array, cv2.COLOR_BGR2RGB)
        gray_image = cv2.cvtColor(orig_image, cv2.COLOR_RGB2GRAY)
        
        gray_image_path = os.path.join(
            self._config["gray_image_dir"],
            self.cap_timestamp_str + "_gray.jpg"
        )
        
        color_image_path = os.path.join(
            self._config["color_image_dir"],
            self.cap_timestamp_str + ".jpg"
        )
        
        cv2.imwrite(gray_image_path, gray_image)
        cv2.imwrite(color_image_path, orig_image)
        
        rgb_gray_image = cv2.cvtColor(gray_image, cv2.COLOR_GRAY2RGB)
        rgb_image = orig_image
        return (rgb_gray_image, gray_image_path), (rgb_image, color_image_path)
    
    def display_random_file(self):
        if self._config["display_gray"]:
            image_dir = self._config["gray_image_dir"]
        else:
            image_dir = self._config["color_image_dir"]
        file_list = glob.glob(os.path.join(image_dir, "*.jpg"))
        num_files = len(file_list)
        photo_path = file_list[random.randrange(num_files)]
        print("Randomly displaying", photo_path)
        image = cv2.imread(photo_path)
        self.display_image(image)
    
    def display_image(self, bgr_image):
        new_dims = (DISPLAY_IMG_WIDTH, DISPLAY_IMG_HEIGHT)
        rgb_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        resized_image = cv2.resize(rgb_image, new_dims)
        overlay = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 4), dtype=np.uint8)
        overlay[:]  = (0, 0, 0, 255)
        overlay[BORDER_HEIGHT:BORDER_HEIGHT+DISPLAY_IMG_HEIGHT,BORDER_WIDTH:BORDER_WIDTH+DISPLAY_IMG_WIDTH,:3] = resized_image
        qpicamera2.set_overlay(overlay)
        
    def check_shutdown_button(self, perf_counter):
        if not pi.read(BUTTON_PIN):
            if perf_counter > (self.last_button_release + SHUTDOWN_HOLD_TIME):
                print("Shutting down")
                pi.set_PWM_dutycycle(LED_COOL_PIN, 0)
                os.system("sudo shutdown now")
        else:
            self.last_button_release = perf_counter
            
    def set_button_led(self, perf_counter):
        pulse_time = perf_counter % BUTTON_PULSE_TIME
        half_pulse_time = BUTTON_PULSE_TIME / 2
        if pulse_time > half_pulse_time:
            pulse_time = BUTTON_PULSE_TIME - pulse_time
            
        ratio = pulse_time / half_pulse_time
        pwm_ratio = ratio ** 2
        pwm_val = int(pwm_ratio * 255)
        pi.set_PWM_dutycycle(LED_BUTTON_PIN, pwm_val) 
        
    def main_loop(self):
        perf_counter = time.perf_counter()
        
        self.check_shutdown_button(perf_counter)
        
        self.set_button_led(perf_counter)
        
        if self.state == "idle":
            if not pi.read(BUTTON_PIN):
                self.state = "countdown"
                self.start_time = perf_counter
        elif self.state == "countdown":
            end_time = self.start_time + COUNT_S
            if perf_counter >= end_time:
                print("Capturing at", (perf_counter - self.start_time))
                self.state = "capture"
                self.exposure_set = False # Reset for next time
                self.mode_switched = False # Reset for next time
                self.capture_start_time = perf_counter
                set_capture_overlay()
            else:
                if perf_counter > (end_time - LED_FADE_S):
                    time_to_photo = COUNT_S - (perf_counter - self.start_time)
                    led_fade = (LED_FADE_S - time_to_photo) / (LED_FADE_S - LED_END_S)
                    set_leds(fade=led_fade)
                    if led_fade > 1:
                        if self.timestamps.get("leds_full", 0) < self.start_time:
                            print("LEDs full")
                            self.timestamps["leds_full"] = perf_counter
                    
                if perf_counter >= (end_time - EXPOSURE_SET_S):
                    if not self.exposure_set:
                        print("Setting exposure at", (perf_counter - self.start_time))
                        picam2.set_controls(
                            self.exposure_settings
                        )
                        self.exposure_set = True
                    else:
                        if perf_counter <= (end_time - EXPOSURE_SET_S + 0.2):
                            # Spam this for 0.2s
                            print("Setting AE true")
                            picam2.set_controls({"AeEnable": True})
                        
                if perf_counter > (end_time - PRE_CONTROL_S):
                    if not self.mode_switched:
                        print("Switching mode at", (perf_counter - self.start_time))
                        picam2.set_controls({
                                "ScalerCrop": FULL_CROP_RECTANGLE,
                                "Saturation": 1.0,
                            })
                        self.mode_switched = True
        elif self.state == "capture":
            self.state = "display_capture"
            self.timestamps["display_capture"] = perf_counter
            self.timestamps["display_image"] = perf_counter
            self.cap_timestamp_str = time.strftime("%y_%m_%d_%H_%M_%S")
            print("Captured", self.cap_timestamp_str)
            picam2.capture_arrays(["main"], signal_function=qpicamera2.signal_done)
        elif self.state == "display_capture":
            if perf_counter >= (self.timestamps["display_capture"] + DISPLAY_S):
                self.state = "idle"
            elif not pi.read(BUTTON_PIN):
                self.start_time = perf_counter
                self.state = "countdown"
            else:
                shuffle_time = self._config["display_shuffle_time"]
                if shuffle_time > 0:
                    if (perf_counter - shuffle_time) > self.timestamps["display_image"]:
                        self.display_random_file()
                        self.timestamps["display_image"] = perf_counter
                return
            picam2.set_controls({
                    "ScalerCrop": PREV_CROP_RECTANGLE,
                    "Saturation": PREV_SATURATION,
                    "AeEnable": True,
                })
            qpicamera2.set_overlay(None)
            
photo_booth = PhotoBooth(config)
            
pi = pigpio.pi()
pi.set_mode(BUTTON_PIN, pigpio.INPUT)
pi.set_mode(LED_BUTTON_PIN, pigpio.OUTPUT)
pi.set_mode(LED_COOL_PIN, pigpio.OUTPUT)
pi.set_pull_up_down(BUTTON_PIN, pigpio.PUD_UP)
pi.set_PWM_frequency(LED_COOL_PIN, 1600)
pi.set_PWM_frequency(LED_BUTTON_PIN, 1600)
set_leds(idle=True)
            
picam2 = Picamera2()
picam2.options["quality"] = 95
picam2.post_callback = photo_booth.apply_timestamp

config = picam2.create_still_configuration(
        #main={'size': (4056, 3040), 'format': 'YUV420'},
        lores={"size": PREV_STREAM_DIMS, 'format': 'YUV420'},
        display="lores",
        buffer_count=3,
        transform=libcamera.Transform(hflip=1)
    )
print("Camera config:")
pprint(config)
print("Camera modes:")
pprint(picam2.sensor_modes)

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
picam2.set_controls({"AeExposureMode": controls.AeExposureModeEnum.Short})

# Uncomment for light testing
#picam2.set_controls({"AeEnable": False})
#picam2.set_controls({"ExposureTime": 30400, "AnalogueGain": 4.0})

print("Camera properties")
pprint(picam2.camera_properties)
qpicamera2.show()
app.exec()

