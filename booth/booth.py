import cv2
from picamera2 import Picamera2, Preview, MappedArray
from picamera2.previews.qt import QGlPicamera2
import libcamera
from libcamera import controls
import time
import subprocess
from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication
import numpy as np
import os
import random
import glob
import pickle
from pprint import *
from datetime import datetime
from PIL import Image
import piexif
import sys

from common.image_path_db import ImagePathDB
from common.timers import Timers
from common.common import load_config
from apply_watermark import ApplyWatermark

# Pi 5 stuff
from gpiozero import Button
from rpi_hardware_pwm import HardwarePWM

# GPIO
BUTTON_PIN = 14
PWM_FREQ = 20000

# Timing
SHUTDOWN_HOLD_TIME = 3

# Capture sequence timing
LED_FADE_S = 1.71 # How long before capture to start brightening LEDs
LED_END_S = 0.71 # How long before capture to hit 100% brightness
EXPOSURE_SET_S = 1.31 # How long before capture to set exposure
PRE_CONTROL_S = 0.31 # How long before capture to set the camera controls
COUNT_S = 5

AWB_MODE = controls.AwbModeEnum.Indoor
AE_MODE = controls.AeExposureModeEnum.Short

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

# Overlay stuff
colour = (255, 255, 255, 255)
font = cv2.FONT_HERSHEY_DUPLEX
origin = (int(DISPLAY_WIDTH / 2 - 62), int(DISPLAY_HEIGHT / 2 + 62))
scale = 6
thickness = 10

capture_overlay = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 4), dtype=np.uint8)
capture_overlay[:] = (255, 255, 255, 255)

BLACK_OVERLAY = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 4), dtype=np.uint8)
BLACK_OVERLAY[:]  = (0, 0, 0, 255)
    
NO_WIFI_OVERLAY = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 4), dtype=np.uint8)
NO_WIFI_OVERLAY[:]  = (0, 0, 0, 0)
wifi_text_origin = (int(DISPLAY_WIDTH / 2 - 100), 10)
wifi_text_scale = 2
wifi_text_thickness = 3
cv2.putText(NO_WIFI_OVERLAY, "Wifi not connected", wifi_text_origin, font, wifi_text_scale, colour, wifi_text_thickness)
    
def get_prev_crop_rectangle(crop_to_screen=True):
    # Crop the preview vertically so it doesn't look weird
    if crop_to_screen:
        y_ratio = (DISPLAY_HEIGHT / DISPLAY_WIDTH) / (FULL_IMG_HEIGHT / FULL_IMG_WIDTH)
    else:
        y_ratio = 1
    prev_crop_height = int(CROP_HEIGHT * y_ratio)
    prev_crop_offset_y = int((CROP_HEIGHT - prev_crop_height) / 2)
    prev_crop_rectangle = (
            CROP_OFFSET_X,
            prev_crop_offset_y,
            CROP_WIDTH,
            prev_crop_height
    )
    return prev_crop_rectangle
    
    
def close_window(event):
    photo_booth.stop_pwm()
    sys.exit(0)
    
    
def load_lens_cal(cal_file):
    with open(cal_file, "rb") as file_obj:
        return pickle.load(file_obj)
    
    
def get_exif(w, h, datetime_stamp, postfix=""):
    formatted_datetime = datetime_stamp.strftime("%Y:%m:%d %H:%M:%S")
    zeroth_ifd = {piexif.ImageIFD.Make: "Glowbot Photo Booth " + postfix,
              piexif.ImageIFD.XResolution: (w, 1),
              piexif.ImageIFD.YResolution: (h, 1),
              piexif.ImageIFD.Software: "Glowbot Photo Booth " + postfix
              }
    exif_ifd = {piexif.ExifIFD.DateTimeOriginal: formatted_datetime,
                piexif.ExifIFD.LensMake: "Glowbot Photo Booth " + postfix,
                piexif.ExifIFD.Sharpness: 65535,
                piexif.ExifIFD.LensSpecification: ((1, 1), (1, 1), (1, 1), (1, 1)),
                }
    exif_dict = {"0th":zeroth_ifd, "Exif":exif_ifd}
    exif_bytes = piexif.dump(exif_dict)
    return exif_bytes
    
    
class PhotoBooth:
    def __init__(self, config):
        self.state = "idle"
        self.cap_timestamp_str = ""
        self.mode_switched = False
        self.exposure_set = False
        self._config = config
        self.timestamps = {}
        if config.get("lens_cal_file", None):
            print("using calibration from ", config["lens_cal_file"])
            self._lens_cal = load_lens_cal(config["lens_cal_file"])
        else:
            self._lens_cal = None
        
        self._continuous_cap = config.get("continuous_cap", False)
        
        self._original_image_dir = config.get("original_image_dir", None)
        self._color_image_dir = config["color_image_dir"]
        self._gray_image_dir = config["gray_image_dir"]
        
        self._display_gray = config.get("display_gray", True)
        self._display_shuffle_time = config["display_shuffle_time"]
        self._display_first_image_time = config["display_first_image_time"]
        
        self._color_postfix = config["color_postfix"]
        self._gray_postfix = config["gray_postfix"]
        self._display_postfix = self._gray_postfix if self._display_gray else self._color_postfix 
        
        self._led_idle_dc = config["led_idle_brightness"]
        self._led_capture_dc = config["led_capture_brightness"]
        self._button_pulse_time = config["button_pulse_time"]
        self._contrast = float(config["contrast"])
        self._brightness = float(config["brightness"])
        
        self._overlay = None
        self._overlay_exclusive = False
        self._display_overlay = None
        self._displaying_qr_code = False
        self._display_image_name = None
        self._displaying_first_image = False
        
        self.photo_path_db = ImagePathDB(config["photo_path_db"])
        self.qr_path_db = ImagePathDB(config["qr_path_db"])
        
        for dir_i in [
                        self._gray_image_dir,
                        self._color_image_dir,
                        self._original_image_dir
                    ]:
            if dir_i:
                os.makedirs(dir_i, exist_ok=True)
        
        # Defaults
        self.exposure_settings = {
            "AnalogueGain": 4,
            "ExposureTime": 30000,
            "AwbMode": AWB_MODE,
        }
        
        self.button = None
        self.pwm_button_led = None
        self.pwm_main_leds = None
        
        self.init_gpio()
        self.set_leds(idle=True)
        
        self.capture_start_time = time.perf_counter()
        
        self.timers = Timers()
        self.timers.start("button_release", SHUTDOWN_HOLD_TIME)
        self.timers.setup("display_capture_timeout", config["display_timeout"])
        self.timers.setup("qr_code_check", config["qr_check_time"])
        self.timers.setup("wifi_check", config["wifi_check_time"])
        
        self._prev_crop_rectangle = get_prev_crop_rectangle(crop_to_screen=config["crop_preview"])
        self._prev_saturation = 0 if config["display_gray"] else 1
        
        if "watermark" in config:
            try:
                self._watermarker = ApplyWatermark(**config["watermark"])
            except Exception as e:
                print("Failed to load watermarker:", e)
                self._watermarker = None
        else:
            self._watermarker = None
        
        self.picam2 = self.init_camera()
        self.qpicamera2 = self.init_preview()
            
    def init_camera(self):
        picam2 = Picamera2()
        picam2.options["quality"] = 95

        still_config = picam2.create_still_configuration(
                lores={"size": PREV_STREAM_DIMS},
                display="lores",
                buffer_count=3,
            )

        picam2.configure(still_config)
        got_config = picam2.camera_configuration()

        if not FOCUS_MODE:
            picam2.set_controls({
                "Sharpness": 1,
                "Saturation": self._prev_saturation
                })
        picam2.set_controls({"AeEnable": True})
        picam2.set_controls({"ScalerCrop": get_prev_crop_rectangle(crop_to_screen=False)}) # Don't crop the initial preview
        picam2.set_controls({"AeExposureMode": AE_MODE})
        picam2.set_controls({"AwbMode": AWB_MODE})
        return picam2

    def init_preview(self):
        qpicamera2 = QGlPicamera2(
                        self.picam2,
                        width=DISPLAY_WIDTH,
                        height=DISPLAY_HEIGHT,
                        keep_ar=False,
                        transform=libcamera.Transform(hflip=1)
                    )
        qpicamera2.timer = QtCore.QTimer()
        qpicamera2.timer.start(25)
        qpicamera2.timer.timeout.connect(self.main_loop)
        qpicamera2.done_signal.connect(self.capture_done)
        qpicamera2.mousePressEvent = close_window

        self.picam2.start()

        qpicamera2.showFullScreen()
        return qpicamera2

    def set_capture_overlay(self):
        self.set_overlay(capture_overlay, exclusive = True)

    def init_gpio(self):
        self.init_button()
        self.init_pwm()
        
    def init_button(self):
        self.button = Button(BUTTON_PIN)
        
    def init_pwm(self):
        self.pwm_button_led = HardwarePWM(pwm_channel=1, hz=PWM_FREQ, chip=2) # This is GPIO 13 on Pi 5
        self.pwm_main_leds = HardwarePWM(pwm_channel=0, hz=PWM_FREQ, chip=2) # This is GPIO 12 on Pi 5
        self.pwm_button_led.start(0)
        self.pwm_main_leds.start(0)
        
    def change_button_led_dc(self, duty_cycle):
        self.pwm_button_led.change_duty_cycle(duty_cycle)
        
    def change_main_led_dc(self, duty_cycle):
        self.pwm_main_leds.change_duty_cycle(duty_cycle)
        
    def is_button_pressed(self):
        return self.button.is_pressed
    
    def stop_pwm(self):
        self.pwm_button_led.stop()
        self.pwm_main_leds.stop()

    def set_leds(self, idle=True, fade=0):
        if fade:
            interval = self._led_capture_dc - self._led_idle_dc
            fade = max(min(fade, 1), 0)
            dc = min(100, interval * fade + self._led_idle_dc)
            self.change_main_led_dc(dc)
        else:
            if idle:
                self.change_main_led_dc(self._led_idle_dc)
            else:
                self.change_main_led_dc(self._led_capture_dc)
        
    def apply_timestamp_overlay(self):
        countdown = str(int(np.ceil(self.timers.time_left("capture_countdown"))))
        if countdown != self.timestamps.get("countdown", -1):
            self.timestamps["countdown"] = countdown
            overlay = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 4), dtype=np.uint8)
            cv2.putText(overlay, countdown, origin, font, scale, colour, thickness)
            self.set_overlay(overlay, exclusive=True)
    
    def capture_done(self, job):
        (self.image_array,), metadata = self.picam2.wait(job)
        self.set_leds(idle=True)
        #print("Capture time", time.perf_counter() - self.capture_start_time)
        self.exposure_settings["AnalogueGain"] = metadata["AnalogueGain"]
        self.exposure_settings["ExposureTime"] = metadata["ExposureTime"]
        print(self.exposure_settings)
        print(
                "CAP",
                "AeEnable", metadata.get("AeEnable", ""),
                "AeLocked", metadata.get("AeLocked", ""),
                "Saturation", metadata.get("Saturation", ""),
            )
        #pprint(metadata)
        print("Color gains", metadata["ColourGains"])
        print("Color temp", metadata["ColourTemperature"])
        print("Lux", metadata["Lux"])
        if self.state == "display_capture":
            self.set_overlay(BLACK_OVERLAY, exclusive=True)
            display_image = self.save_capture()
            self.display_image(display_image)
    
    
    def save_capture(self):
        orig_image = self.image_array
        
        if self._lens_cal:
            newcameramtx, roi, mtx, dist = self._lens_cal
            dst = cv2.undistort(orig_image, mtx, dist, None, newcameramtx)
            x, y, w, h = roi
            final_image = dst[y:y+h, x:x+w]
        else:
            final_image = orig_image
            
        gray_image = cv2.cvtColor(final_image, cv2.COLOR_RGB2GRAY)
        gray_image = cv2.cvtColor(gray_image, cv2.COLOR_GRAY2BGR)
        
        h, w = final_image.shape[:2]
        datetime_stamp = datetime.now()
                    
        path_dict = {}
        photo_name = self.cap_timestamp_str
        self._display_image_name = photo_name
        for (cv_img, dir_i, postfix) in [
                (gray_image, self._gray_image_dir, self._gray_postfix),
                (final_image, self._color_image_dir, self._color_postfix),
                (orig_image, self._original_image_dir, "_original")
                ]:
            if dir_i:
                exif_bytes = get_exif(w, h, datetime_stamp, postfix)
                image_path = os.path.join(
                    dir_i,
                    photo_name + postfix + ".jpg"
                )
                if (self._watermarker is not None) and (postfix != "_original"):
                    self._watermarker.apply_watermark(cv_img)
                img = Image.fromarray(cv_img)
                img.save(image_path, quality=95, exif=exif_bytes)
                
                path_dict[postfix] = image_path
                
        self.photo_path_db.add_image(photo_name, path_dict)
        self.photo_path_db.update_file()
        
        #return an image to display
        if self._display_gray:
            display_image = cv2.cvtColor(gray_image, cv2.COLOR_BGR2RGB)
        else:
            display_image = cv2.cvtColor(final_image, cv2.COLOR_BGR2RGB)
        return display_image
    
    def get_qr_code(self, image_name):
        if not self.qr_path_db.try_update_from_file():
            print("Error updating qr path db")
        qr_image = None
        if self.qr_path_db.image_exists(image_name):
            qr_path = self.qr_path_db.get_image_path(image_name)
            qr_image = cv2.imread(qr_path)
        return qr_image
    
    def display_random_file(self):
        photo_names = list(self.photo_path_db.image_names())
        num_files = len(photo_names)
        name = photo_names[random.randrange(num_files)]
        photo_path = self.photo_path_db.get_image_path(name, self._display_postfix)
        image = None
        if os.path.exists(photo_path):
            self._display_image_name = name
            image = cv2.imread(photo_path)
        if image is not None:
            self.display_image(image, qr_code=self.get_qr_code(name))
    
    def add_qr_code(self, qr_code):
        self._displaying_qr_code = True
        q_pos = self._config["qr_pos"]
        resized_qrcode = cv2.resize(qr_code, (q_pos[2], q_pos[3]), cv2.INTER_NEAREST)
        self._display_overlay[q_pos[1]:q_pos[1]+q_pos[3],q_pos[0]:q_pos[0]+q_pos[2],:3] = resized_qrcode
        
    def display_image(self, bgr_image, qr_code=None):
        new_dims = (DISPLAY_IMG_WIDTH, DISPLAY_IMG_HEIGHT)
        rgb_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        resized_image = cv2.resize(rgb_image, new_dims)
        self._display_overlay = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 4), dtype=np.uint8)
        self._display_overlay[:] = (0, 0, 0, 255)
        self._display_overlay[BORDER_HEIGHT:BORDER_HEIGHT+DISPLAY_IMG_HEIGHT,BORDER_WIDTH:BORDER_WIDTH+DISPLAY_IMG_WIDTH,:3] = resized_image
        
        self._displaying_qr_code = False
        if qr_code is not None:
            self.add_qr_code(qr_code)
        
        self.set_overlay(self._display_overlay)
        
    def check_shutdown_button(self):
        if self.is_button_pressed():
            if self.timers.check("button_release"):
                self.stop_pwm()
                print("Shutting down")
                os.system("sudo shutdown now")
        else:
            self.timers.restart("button_release")
            
    def set_button_led(self, perf_counter):
        if self.state == "countdown":
            self.change_button_led_dc(0)
        elif (self.state == "idle") or (self.state == "display_capture"):
            pulse_time = perf_counter % self._button_pulse_time
            half_pulse_time = self._button_pulse_time / 2
            if pulse_time > half_pulse_time:
                pulse_time = self._button_pulse_time - pulse_time
             
            ratio = pulse_time / half_pulse_time
            pwm_ratio = np.exp(ratio * 3) / np.exp(3)
            pwm_val = pwm_ratio * 100
            self.change_button_led_dc(pwm_val)
        
    def main_loop(self):
        self.timers.update_time()
    
        perf_counter = time.perf_counter()
        
        self.check_shutdown_button()
        
        self.set_button_led(perf_counter)
        
        next_state = self.state

        if self.state == "idle":
            if self.is_button_pressed() or self._continuous_cap:
                next_state = "countdown"
                self.timers.start("capture_countdown", COUNT_S)
        elif self.state == "countdown":
            if self.timers.check("capture_countdown"):
                print("Capturing at", self.timers.time_left("capture_countdown"))
                next_state = "capture"
                self.exposure_set = False # Reset for next time
                self.mode_switched = False # Reset for next time
                self.capture_start_time = perf_counter
            else:
                self.apply_timestamp_overlay()
                time_left = self.timers.time_left("capture_countdown")
                if time_left <= LED_FADE_S:
                    led_fade = (LED_FADE_S - time_left) / (LED_FADE_S - LED_END_S)
                    self.set_leds(fade=led_fade)
                    
                if time_left <= EXPOSURE_SET_S:
                    if not self.exposure_set:
                        print("Setting exposure at", self.timers.time_left("capture_countdown"))
                        self.picam2.set_controls(
                            self.exposure_settings
                        )
                        self.exposure_set = True
                    else: # After setting the exposure, turn on Autoexposure so it can adjust if needed
                        if time_left > (EXPOSURE_SET_S - 0.2):
                            # Spam this for 0.2s
                            print("Setting AE true")
                            self.picam2.set_controls({"AeEnable": True})
                        
                if time_left <= PRE_CONTROL_S:
                    if not self.mode_switched:
                        print("Switching mode at", self.timers.time_left("capture_countdown"))
                        self.picam2.set_controls({
                                "ScalerCrop": FULL_CROP_RECTANGLE,
                                "Saturation": 1.0,
                                "Contrast": self._contrast,
                                "Brightness": self._brightness,
                            })
                        self.set_capture_overlay()
                        self.mode_switched = True
        elif self.state == "capture":
            next_state = "display_capture"
            self.timers.start("display_capture_timeout")
            self.timers.start("display_image_timeout", self._display_first_image_time)
            self.timers.start("qr_code_check")
            self.cap_timestamp_str = time.strftime("%y%m%d_%H%M%S")
            print("Captured", self.cap_timestamp_str)
            self.picam2.capture_arrays(["main"], signal_function=self.qpicamera2.signal_done)
        elif self.state == "display_capture":
            if self.timers.check("display_capture_timeout"):
                next_state = "idle"
            elif self.is_button_pressed():
                self.timers.start("capture_countdown", COUNT_S)
                next_state = "countdown"
            else:
                if self.timers.check("qr_code_check", auto_restart=True):
                    if self._display_image_name and not self._displaying_qr_code:
                        qr_code = self.get_qr_code(self._display_image_name)
                        if qr_code is not None:
                            print("FOUND QR CODE", self._display_image_name)
                            self.add_qr_code(qr_code)
                            self.set_overlay(self._display_overlay)
                
                if self.timers.check("display_image_timeout"):
                    self.display_random_file()
                    self.timers.start("display_image_timeout", self._display_shuffle_time)

            if next_state != "display_capture":
                # Reset the camera to the preview config when we leave this state
                self.picam2.set_controls({
                        "ScalerCrop": self._prev_crop_rectangle,
                        "Saturation": self._prev_saturation,
                        "AeEnable": True,
                    })
                self.set_overlay(blank_overlay = True)
        
        self.set_wifi_overlay()

        self.state = next_state

    def set_overlay(self, overlay = None, blank_overlay = False, exclusive = False):
        if blank_overlay:
            self._overlay = None
        else:
            self._overlay = overlay
        self._overlay_exclusive = exclusive
        self.qpicamera2.set_overlay(self._overlay)

    def add_overlay(self, overlay):
        if not self._overlay_exclusive:
            if self._overlay is not None:
                self._overlay = np.clip(overlay + self._overlay, a_min=0, a_max=255)
            else:
                self._overlay = overlay
        self.qpicamera2.set_overlay(self._overlay)

    def set_wifi_overlay(self):
        if not self._overlay_exclusive:
            if self.timers.check("wifi_check_time", auto_restart=True):
                wifi_network = self.check_wifi_connection()
                if not wifi_network:
                    self.add_overlay(NO_WIFI_OVERLAY)

    def check_wifi_connection(self):
        try:
            # Run the iwgetid command with the -r flag to get the SSID
            ssid = subprocess.check_output(['iwgetid', '-r']).decode('utf-8').strip()
            if ssid:
                return ssid
            else:
                return None
        except subprocess.CalledProcessError:
            return None


config = load_config()
app = QApplication([])
photo_booth = PhotoBooth(config)
app.exec()

