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
from overlay_manager import OverlayManager

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

# Capture sequence timing on 2nd and 3rd shots
LED_FADE_S_EXTRA_SHOT = 0.51 # How long before capture to start brightening LEDs
LED_END_S_EXTRA_SHOT = 0.31 # How long before capture to hit 100% brightness
COUNT_S_EXTRA_SHOT = 3

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

CAPTURE_OVERLAY = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 4), dtype=np.uint8)
CAPTURE_OVERLAY[:] = (255, 255, 255, 255)

BLACK_OVERLAY = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 4), dtype=np.uint8)
BLACK_OVERLAY[:]  = (0, 0, 0, 255)
    
NO_WIFI_OVERLAY = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 4), dtype=np.uint8)
NO_WIFI_OVERLAY[:]  = (0, 0, 0, 0)
wifi_text_origin = (int(DISPLAY_WIDTH / 2 - 100), 25)
wifi_text_scale = 0.75
wifi_text_thickness = 1
cv2.putText(NO_WIFI_OVERLAY, "Wifi not connected", wifi_text_origin, font, wifi_text_scale, colour, wifi_text_thickness)
    
# States
ST_IDLE = 1
ST_COUNTDOWN = 2
ST_CAPTURE = 3
ST_PROCESS_CAPTURE = 4
ST_DISPLAY_CAPTURE = 5
    
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
        self._config = config
        
        self.state = ST_IDLE
        
        # capture state variables
        self.cap_timestamp_str = ""
        self.capture_completed = False
        
        # countdown state variables
        self.mode_switched = False
        self.exposure_set = False
        self.button_released = False
        self.extra_shots = 0
        self.countdown_timestamp = -1
        self.set_ae = True
        self.exposure_set_s = EXPOSURE_SET_S
        self.led_fade_s = LED_FADE_S
        self.led_end_s = LED_END_S
        
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
        self._enable_multi_shot = config["enable_multi_shot"]
        
        self.overlay_manager = OverlayManager(DISPLAY_WIDTH, DISPLAY_HEIGHT)
        self.setup_overlays(config["overlays"])
        self._display_overlay = None
        self._displaying_qr_code = False
        self._display_image_name = None
        
        self.photo_path_db = ImagePathDB(config["photo_path_db"])
        self.qr_path_db = ImagePathDB(config["qr_path_db"])
        
        self.wifi_check = config["wifi_check"]

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
        
        self.timers = Timers()
        self.timers.start("button_release", SHUTDOWN_HOLD_TIME)
        self.timers.setup("display_capture_timeout", config["display_timeout"])
        self.timers.setup("qr_code_check", config["qr_check_time"])
        self.timers.setup("wifi_check", config["wifi_check_time"])
        self.timers.start("wifi_check")
        
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

    def setup_overlays(self, overlay_config):
        self.overlay_manager.set_layer(NO_WIFI_OVERLAY, name="wifi")
        
        for name, config in overlay_config.items():
            image = cv2.imread(config["path"], cv2.IMREAD_UNCHANGED)
            self.overlay_manager.set_layer(image, name=name, size=config["size"], offset=config["offset"], weight=config["weight"])
        
    def set_capture_overlay(self):
        self.overlay_manager.set_main_image(CAPTURE_OVERLAY, exclusive = True)

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
        if countdown != self.countdown_timestamp:
            self.countdown_timestamp = countdown
            overlay = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 4), dtype=np.uint8)
            cv2.putText(overlay, countdown, origin, font, scale, colour, thickness)
            self.overlay_manager.set_main_image(overlay, exclusive=False)
    
    def capture_done(self, job):
        (self.image_array,), metadata = self.picam2.wait(job)
        self.set_leds(idle=True)
        self.qpicamera2.set_overlay(BLACK_OVERLAY)
        self.capture_completed = True
        
        self.exposure_settings["AnalogueGain"] = metadata["AnalogueGain"]
        self.exposure_settings["ExposureTime"] = metadata["ExposureTime"]
        
        print(self.exposure_settings)
        print(
                "CAP",
                "AeEnable", metadata.get("AeEnable", ""),
                "AeLocked", metadata.get("AeLocked", ""),
                "Saturation", metadata.get("Saturation", ""),
            )
        print("Color gains", metadata["ColourGains"])
        print("Color temp", metadata["ColourTemperature"])
        print("Lux", metadata["Lux"])
    
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
        self.overlay_manager.set_main_image(self._display_overlay, exclusive=False)
        
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
        
        self.overlay_manager.set_main_image(self._display_overlay, exclusive=False)
        
    def check_shutdown_button(self):
        if self.is_button_pressed():
            if self.timers.check("button_release"):
                self.stop_pwm()
                print("Shutting down")
                os.system("sudo shutdown now")
        else:
            self.timers.restart("button_release")
            
    def set_button_led(self):
        pulse_time = time.perf_counter() % self._button_pulse_time
        half_pulse_time = self._button_pulse_time / 2
        if pulse_time > half_pulse_time:
            pulse_time = self._button_pulse_time - pulse_time
        ratio = pulse_time / half_pulse_time
        
        if self.state == ST_COUNTDOWN:
            self.change_button_led_dc(0)
        elif (self.state == ST_IDLE) or (self.state == ST_DISPLAY_CAPTURE):
            pwm_ratio = np.exp(ratio * 3) / np.exp(3)
            pwm_val = pwm_ratio * 100
            self.change_button_led_dc(pwm_val)
        return ratio
            
    def setup_state(self, next_state):
        if next_state == ST_COUNTDOWN:
            if self._enable_multi_shot:
                self.overlay_manager.activate_layer("three_shots")
            self.button_released = False
            if self.extra_shots > 0:
                self.extra_shots -= 1
                self.set_ae = False
                self.led_fade_s = LED_FADE_S_EXTRA_SHOT
                self.led_end_s = LED_END_S_EXTRA_SHOT
                self.timers.start("capture_countdown", COUNT_S_EXTRA_SHOT)
            else:
                self.set_ae = True
                self.led_fade_s = LED_FADE_S
                self.led_end_s = LED_END_S
                self.timers.start("capture_countdown", COUNT_S)
            
        
    def main_loop(self):
        self.timers.update_time()
        self.check_shutdown_button()
        
        next_state = self.state

        if self.state == ST_IDLE:
            if self.is_button_pressed() or self._continuous_cap:
                next_state = ST_COUNTDOWN
                self.extra_shots = 0
                self.setup_state(ST_COUNTDOWN)
        elif self.state == ST_COUNTDOWN:
            if self._enable_multi_shot:
                if not self.is_button_pressed():
                    self.button_released = True
                else:
                    if self.button_released:
                        self.button_released = False
                        if self.extra_shots == 0:
                            self.extra_shots = 2
                            self.overlay_manager.deactivate_layer("three_shots")
                        elif self.extra_shots == 2:
                            self.extra_shots = 0
                    
            if self.timers.check("capture_countdown"):
                print("Capturing at", self.timers.time_left("capture_countdown"))
                next_state = ST_CAPTURE
                if self._enable_multi_shot:
                    self.overlay_manager.deactivate_layer("three_shots")
                self.exposure_set = False # Reset for next time
                self.mode_switched = False # Reset for next time
            else:
                self.apply_timestamp_overlay()
                time_left = self.timers.time_left("capture_countdown")
                if time_left <= self.led_fade_s:
                    led_fade = (self.led_fade_s - time_left) / (self.led_fade_s - self.led_end_s)
                    self.set_leds(fade=led_fade)
                    
                if time_left <= self.exposure_set_s:
                    if not self.exposure_set:
                        print("Setting exposure at", self.timers.time_left("capture_countdown"))
                        self.picam2.set_controls(
                            self.exposure_settings
                        )
                        self.exposure_set = True
                    elif self.set_ae: # After setting the exposure, turn on Autoexposure so it can adjust if needed
                        if time_left > (self.exposure_set_s - 0.2):
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
        elif self.state == ST_CAPTURE:
            next_state = ST_PROCESS_CAPTURE
            self.cap_timestamp_str = time.strftime("%y%m%d_%H%M%S")
            print("Captured", self.cap_timestamp_str)
            self.capture_completed = False
            self.picam2.capture_arrays(["main"], signal_function=self.qpicamera2.signal_done)
        elif self.state == ST_PROCESS_CAPTURE:
            if self.capture_completed:
                next_state = ST_DISPLAY_CAPTURE
                display_image = self.save_capture()
                self.display_image(display_image)
                self.timers.start("display_capture_timeout")
                self.timers.start("display_image_timeout", self._display_first_image_time)
                self.timers.start("qr_code_check")
        elif self.state == ST_DISPLAY_CAPTURE:
            if self.timers.check("display_capture_timeout"):
                next_state = ST_IDLE
            elif self.is_button_pressed() or (self.extra_shots > 0):
                next_state = ST_COUNTDOWN
                self.setup_state(ST_COUNTDOWN)
            else:
                if self.timers.check("qr_code_check", auto_restart=True):
                    if self._display_image_name and not self._displaying_qr_code:
                        qr_code = self.get_qr_code(self._display_image_name)
                        if qr_code is not None:
                            print("FOUND QR CODE", self._display_image_name)
                            self.add_qr_code(qr_code)
                
                if self.timers.check("display_image_timeout"):
                    self.display_random_file()
                    self.timers.start("display_image_timeout", self._display_shuffle_time)

            if next_state != ST_DISPLAY_CAPTURE:
                # Reset the camera to the preview config when we leave this state
                self.picam2.set_controls({
                        "ScalerCrop": self._prev_crop_rectangle,
                        "Saturation": self._prev_saturation,
                        "AeEnable": True,
                    })
                self.overlay_manager.set_main_image(None, exclusive=False)
        
        # Update visuals
        button_brightness = self.set_button_led()
        self.set_arrow_overlay(button_brightness)
        
        if self.wifi_check and self.timers.check("wifi_check", auto_restart=True):
            self.set_wifi_overlay()
            
        new_overlay, overlay = self.overlay_manager.update_overlay()
        if new_overlay:
            self.qpicamera2.set_overlay(overlay)

        # Update state
        self.state = next_state

    def set_arrow_overlay(self, button_brightness):
        if self.state in [ST_IDLE, ST_DISPLAY_CAPTURE]:
            if button_brightness < 0.5:
                self.overlay_manager.deactivate_layer("arrow")
            else:
                self.overlay_manager.activate_layer("arrow")
        else:
            self.overlay_manager.deactivate_layer("arrow")

    def set_wifi_overlay(self):
        wifi_network = self.check_wifi_connection()
        if not wifi_network:
            self.overlay_manager.activate_layer(name="wifi")
        else:
            self.overlay_manager.deactivate_layer(name="wifi")

    def check_wifi_connection(self):
        try:
            # Run the iwgetid command with the -r flag to get the SSID
            print("Checking wifi connection")
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

