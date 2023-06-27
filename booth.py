import cv2
from picamera2 import Picamera2, Preview, MappedArray
from picamera2.previews.qt import QGlPicamera2
from libcamera import controls
import time
import RPi.GPIO as GPIO
from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication
import numpy as np

COUNT_S = 3
DISPLAY_S = 5
BUTTON_PIN = 16 # Header pin number
WIDTH=1024
HEIGHT=600
BORDER_SIZE=50

state = "idle"
button_pressed = False
start_time = 0
filename = ""
capture_done = False

# Overlay stuff
colour = (255, 255, 255)
origin = (1152, 648)
font = cv2.FONT_HERSHEY_DUPLEX
scale = 6
thickness = 10

def apply_timestamp(request):
    if state == "countdown":
        #timestamp = time.strftime("%Y-%m-%d %X")
        countdown = str(COUNT_S - int(time.perf_counter() - start_time))
        with MappedArray(request, "main") as m:
            cv2.putText(m.array, countdown, origin, font, scale, colour, thickness)
        
            
def capture_done(job):
    result = picam2.wait(job)
    print("Displaying", filename)
    display_capture(filename)
        
           
def display_capture(filename):
    overlay = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
    overlay[:] = (0, 0, 0, 255)
    orig_image = cv2.imread(filename)
    orig_image = cv2.cvtColor(orig_image, cv2.COLOR_BGR2RGBA)
    new_dims = (WIDTH-(BORDER_SIZE*2), HEIGHT-(BORDER_SIZE*2))
    resized_image = cv2.resize(orig_image, new_dims)
    overlay[BORDER_SIZE:HEIGHT-BORDER_SIZE,BORDER_SIZE:WIDTH-BORDER_SIZE] = resized_image
    qpicamera2.set_overlay(overlay)
    

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
        filename = time.strftime("%y-%m-%d %X.jpg")
        print("Saving to", filename)
        picam2.switch_mode_and_capture_file(config, filename, signal_function=qpicamera2.signal_done)
        state = "display_capture"
        start_time = time.perf_counter()
    elif state == "display_capture":
        if time.perf_counter() >= (start_time + DISPLAY_S):
            qpicamera2.set_overlay(None)
            state = "idle"
        
GPIO.setmode(GPIO.BOARD)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
picam2 = Picamera2()    
print(picam2.sensor_modes)
picam2.pre_callback = apply_timestamp

config = picam2.create_still_configuration()
#prev_config = picam2.create_preview_configuration({"size": (1152, 648)})
prev_config = picam2.create_preview_configuration({"size": (2304, 1296)})
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
        

#if __name__ == "__main__":
#    main()
