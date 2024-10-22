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
import booth_states
from settings import SettingsDialog

# Pi 5 stuff
from gpiozero import Button
from rpi_hardware_pwm import HardwarePWM

# GPIO
BUTTON_PIN = 14
PWM_FREQ = 20000

# Timing
SHUTDOWN_HOLD_TIME = 3

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


class TouchSensitivePreview(QGlPicamera2):
    settings_requested = QtCore.pyqtSignal()

    def __init__(self, camera, width, height, keep_ar, transform, parent=None):
        super().__init__(camera, parent=parent, width=width, height=height, keep_ar=keep_ar, transform=transform)
    
    def mousePressEvent(self, event):
        pos = event.pos()
        widget_width = self.width()
        widget_height = self.height()

        # Define the tap area (e.g., top 10% height, right 10% width)
        margin_width = widget_width * 0.1   # 10% of width
        margin_height = widget_height * 0.1  # 10% of height

        if (pos.x() >= widget_width - margin_width) and (pos.y() <= margin_height):
            # Emit signal to open settings
            self.settings_requested.emit()
        else:
            close_window(None)


class PhotoBooth:
    def __init__(self, config):
        self._config = config
        
        if config.get("lens_cal_file", None):
            print("using calibration from ", config["lens_cal_file"])
            self._lens_cal = load_lens_cal(config["lens_cal_file"])
        else:
            self._lens_cal = None
        
        self._continuous_cap = config.get("continuous_cap", False)
        
        self._original_image_dir = config.get("original_image_dir", None)
        self._color_image_dir = config["color_image_dir"]
        self._gray_image_dir = config["gray_image_dir"]
        
        self._display_gray = config["display_gray"]
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
        
        self.photo_path_db = ImagePathDB(config["photo_path_db"])
        self.qr_path_db = ImagePathDB(config["qr_path_db"])
        
        self.wifi_check = config["wifi_check"]

        self.needs_restart = False

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
        self.timers.start("wifi_check", config["wifi_check_time"])
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

        self.setup_states()
        
        self.state = None
        self.next_state = self.state_idle

    def setup_states(self):
        self.state_idle = booth_states.StateIdle(self)
        self.state_countdown = booth_states.StateCountdown(self)
        self.state_capture = booth_states.StateCapture(self)
        self.state_display_capture = booth_states.StateDisplayCapture(self)

    def get_prev_crop_rectangle(self, crop_to_screen=True):
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
            
    def init_camera(self):
        picam2 = Picamera2()
        picam2.options["quality"] = 95

        still_config = picam2.create_still_configuration(
                lores={"size": PREV_STREAM_DIMS},
                display="lores",
                buffer_count=3,
            )

        picam2.configure(still_config)

        if not FOCUS_MODE:
            picam2.set_controls({
                "Sharpness": 1,
                "Saturation": self._prev_saturation
                })
        picam2.set_controls({"AeEnable": True})
        picam2.set_controls({"ScalerCrop": self.get_prev_crop_rectangle(crop_to_screen=False)}) # Don't crop the initial preview
        picam2.set_controls({"AeExposureMode": AE_MODE})
        picam2.set_controls({"AwbMode": AWB_MODE})
        return picam2
    
    def set_cam_controls_capture(self):
        self.picam2.set_controls({
                "ScalerCrop": FULL_CROP_RECTANGLE,
                "Saturation": 1.0,
                "Contrast": self._contrast,
                "Brightness": self._brightness,
            })
        
    def set_cam_controls_preview(self, crop_preview):
        self.picam2.set_controls({
                "ScalerCrop": self.get_prev_crop_rectangle(crop_to_screen=crop_preview),
                "Saturation": self._prev_saturation,
                "AeEnable": True,
                "AeExposureMode": AE_MODE,
                "AwbMode": AWB_MODE
            })

    def init_preview(self):
        qpicamera2 = TouchSensitivePreview(
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
        qpicamera2.settings_requested.connect(self.open_settings)

        self.picam2.start()

        qpicamera2.showFullScreen()

        self.settings_dialog = None
        return qpicamera2
    
    def signal_restart(self):
        self.needs_restart = True

    def open_settings(self):
        print("opening settings")
        self.settings_dialog = SettingsDialog(
                config=self._config,
                signal_restart=self.signal_restart, 
                parent=self.qpicamera2
            )
        self.settings_dialog.exec_()
        print("Settings closed")
        self.settings_dialog = None

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
        return display_image, photo_name
        
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
        
        if self.state == self.state_countdown:
            self.change_button_led_dc(0)
        elif (self.state == self.state_idle) or (self.state == self.state_display_capture):
            pwm_ratio = np.exp(ratio * 3) / np.exp(3)
            pwm_val = pwm_ratio * 100
            self.change_button_led_dc(pwm_val)
        return ratio
            
    def main_loop(self):
        self.timers.update_time()
        self.check_shutdown_button()
        if self.needs_restart:
            print("Restarting uploader and booth now")
            os.system(self._config["restart_uploader_command"])
            close_window(None)
        
        if self.next_state != self.state:
            print("Moving from", self.state, "to", self.next_state, "at", time.time() % 100)
            if self.state:
                self.state.exit()
            self.state = self.next_state
            self.state.enter()
        self.next_state = self.state.run()
        
        # Update visuals
        button_brightness = self.set_button_led()
        self.set_arrow_overlay(button_brightness)
        
        if self.wifi_check and self.timers.check("wifi_check", auto_restart=True):
            self.set_wifi_overlay()
            
        new_overlay, overlay = self.overlay_manager.update_overlay()
        if new_overlay:
            self.qpicamera2.set_overlay(overlay)

    def set_arrow_overlay(self, button_brightness):
        if self.state in [self.state_idle, self.state_display_capture]:
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
            ssid = subprocess.check_output(['iwgetid', '-r']).decode('utf-8').strip()
            if ssid:
                return ssid
            else:
                return None
        except subprocess.CalledProcessError:
            return None

    def create_image_display_overlay(self, bgr_image):
        new_dims = (DISPLAY_IMG_WIDTH, DISPLAY_IMG_HEIGHT)
        rgb_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        resized_image = cv2.resize(rgb_image, new_dims)
        display_overlay = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 4), dtype=np.uint8)
        display_overlay[:] = (0, 0, 0, 255)
        display_overlay[BORDER_HEIGHT:BORDER_HEIGHT+DISPLAY_IMG_HEIGHT,BORDER_WIDTH:BORDER_WIDTH+DISPLAY_IMG_WIDTH,:3] = resized_image
        return display_overlay



config = load_config()
app = QApplication([])
photo_booth = PhotoBooth(config)
app.exec()

