import numpy as np
import time
import cv2
import os
import random

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

class State:
    def __init__(self, machine):
        self.machine = machine
        self.timers = machine.timers
        self.overlay_manager = machine.overlay_manager

    def enter(self):
        return
    
    def exit(self):
        return
    
    def run(self):
        return self
    

class StateIdle(State):
    def __init__(self, kwargs):
        super().__init__(**kwargs)
        self.first_run = True

    def enter(self):
        if self.first_run:
            self.first_run = False
            crop_preview = False
        else:
            crop_preview = self.machine._config["crop_preview"]
        self.machine.set_cam_controls_preview(crop_preview)
        self.overlay_manager.set_main_image(None, exclusive=False)

    def exit(self):
        self.machine.extra_shots = 0
        
    def run(self):
        if self.machine.is_button_pressed() or self.machine._continuous_cap:
            return self.machine.state_countdown
        return self


class StateCountdown(State):
    def __init__(self, kwargs):
        super().__init__(**kwargs)

    def enter(self):
        self.machine.set_cam_controls_preview(crop_preview=True)
        self.button_released = False
        self.exposure_set = False
        self.mode_switched = False
        self.exposure_set_s = EXPOSURE_SET_S
        self.countdown_timestamp = -1
        if self.machine.extra_shots > 0:
            self.machine.extra_shots -= 1
            self.set_ae = False
            self.led_fade_s = LED_FADE_S_EXTRA_SHOT
            self.led_end_s = LED_END_S_EXTRA_SHOT
            self.timers.start("capture_countdown", COUNT_S_EXTRA_SHOT)
        else:
            self.set_ae = True
            self.led_fade_s = LED_FADE_S
            self.led_end_s = LED_END_S
            if self.machine._enable_multi_shot:
                self.overlay_manager.activate_layer("three_shots")
            self.timers.start("capture_countdown", COUNT_S)

    def exit(self):
        return
    
    def run(self):
        if self.machine._enable_multi_shot:
            if not self.machine.is_button_pressed():
                self.button_released = True
            else:
                if self.button_released:
                    self.button_released = False
                    if self.machine.extra_shots == 0:
                        self.machine.extra_shots = 2
                        self.overlay_manager.deactivate_layer("three_shots")
                
        if self.timers.check("capture_countdown"):
            print("Capturing at", self.timers.time_left("capture_countdown"))
            if self.machine._enable_multi_shot:
                self.overlay_manager.deactivate_layer("three_shots")
            return self.machine.state_capture
        else:
            self.apply_timestamp_overlay()
            time_left = self.timers.time_left("capture_countdown")
            if time_left <= self.led_fade_s:
                led_fade = (self.led_fade_s - time_left) / (self.led_fade_s - self.led_end_s)
                self.machine.set_leds(fade=led_fade)
                
            if time_left <= self.exposure_set_s:
                if not self.exposure_set:
                    print("Setting exposure at", self.timers.time_left("capture_countdown"))
                    self.machine.picam2.set_controls(
                        self.machine.exposure_settings
                    )
                    self.exposure_set = True
                elif self.set_ae: # After setting the exposure, turn on Autoexposure so it can adjust if needed
                    if time_left > (self.exposure_set_s - 0.2):
                        # Spam this for 0.2s
                        print("Setting AE true")
                        self.machine.picam2.set_controls({"AeEnable": True})
                    
            if time_left <= PRE_CONTROL_S:
                if not self.mode_switched:
                    print("Switching mode at", self.timers.time_left("capture_countdown"))
                    self.machine.set_cam_controls_capture()
                    self.machine.set_capture_overlay()
                    self.mode_switched = True
        return self
        
    def apply_timestamp_overlay(self):
        countdown = str(int(np.ceil(self.timers.time_left("capture_countdown"))))
        if countdown != self.countdown_timestamp:
            self.countdown_timestamp = countdown
            overlay = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 4), dtype=np.uint8)
            cv2.putText(overlay, countdown, origin, font, scale, colour, thickness)
            self.overlay_manager.set_main_image(overlay, exclusive=False)
    
class StateCapture(State):
    def __init__(self, kwargs):
        super().__init__(**kwargs)

    def enter(self):
        cap_timestamp_str = time.strftime("%y%m%d_%H%M%S")
        print("Captured", cap_timestamp_str)
        self.machine.cap_timestamp_str = cap_timestamp_str
        self.machine.capture_completed = False
        self.machine.picam2.capture_arrays(["main"], signal_function=self.machine.qpicamera2.signal_done)

    def exit(self):
        return
        
    def run(self):
        if self.machine.capture_completed:
            captured_display_image, captured_image_name = self.machine.save_capture()
            self.machine.captured_display_image = captured_display_image
            self.machine.captured_image_name = captured_image_name
            return self.machine.state_display_capture
        return self
    
class StateDisplayCapture(State):
    def __init__(self, kwargs):
        super().__init__(**kwargs)
        self.timers.setup("display_capture_timeout", self.machine._config["display_timeout"])
        self.timers.setup("qr_code_check", self.machine._config["qr_check_time"])
        self._displaying_qr_code = False
        self._display_overlay = None

    def enter(self):
        self.timers.start("display_capture_timeout")
        self.timers.start("display_image_timeout", self.machine._display_first_image_time)
        self.timers.start("qr_code_check")
        self.display_image(self.machine.captured_display_image)
        self._display_image_name = self.machine.captured_image_name

    def exit(self):
        return
        
    def run(self):
        if self.timers.check("display_capture_timeout"):
            return self.machine.state_idle
        elif self.machine.is_button_pressed() or (self.machine.extra_shots > 0):
            return self.machine.state_countdown
        else:
            if self.timers.check("qr_code_check", auto_restart=True):
                if self._display_image_name and not self._displaying_qr_code:
                    qr_code = self.get_qr_code(self._display_image_name)
                    if qr_code is not None:
                        print("FOUND QR CODE", self._display_image_name)
                        self.add_qr_code(qr_code)
            
            if self.timers.check("display_image_timeout"):
                self.display_random_file()
                self.timers.start("display_image_timeout", self.machine._display_shuffle_time)

        return self
    
    def get_qr_code(self, image_name):
        if not self.machine.qr_path_db.try_update_from_file():
            print("Error updating qr path db")
        qr_image = None
        if self.machine.qr_path_db.image_exists(image_name):
            qr_path = self.machine.qr_path_db.get_image_path(image_name)
            qr_image = cv2.imread(qr_path)
        return qr_image
    
    def display_random_file(self):
        photo_names = list(self.machine.photo_path_db.image_names())
        num_files = len(photo_names)
        name = photo_names[random.randrange(num_files)]
        photo_path = self.machine.photo_path_db.get_image_path(name, self._display_postfix)
        image = None
        if os.path.exists(photo_path):
            self._display_image_name = name
            image = cv2.imread(photo_path)
        if image is not None:
            self.display_image(image, qr_code=self.get_qr_code(name))
    
    def add_qr_code(self, qr_code):
        self._displaying_qr_code = True
        q_pos = self.machine._config["qr_pos"]
        resized_qrcode = cv2.resize(qr_code, (q_pos[2], q_pos[3]), cv2.INTER_NEAREST)
        self._display_overlay[q_pos[1]:q_pos[1]+q_pos[3],q_pos[0]:q_pos[0]+q_pos[2],:3] = resized_qrcode
        self.overlay_manager.set_main_image(self._display_overlay, exclusive=False)
        
    def display_image(self, bgr_image, qr_code=None):
        self._display_overlay = self.machine.create_image_display_overlay(bgr_image)
        
        self._displaying_qr_code = False
        if qr_code is not None:
            self.add_qr_code(qr_code)
        
        self.overlay_manager.set_main_image(self._display_overlay, exclusive=False)