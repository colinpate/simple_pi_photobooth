#!/bin/bash
#source /home/colin/simple_pi_photobooth/booth_venv/bin/activate
export PYTHONPATH=$PYTHONPATH:/home/colin/simple_pi_photobooth
python3 /home/colin/simple_pi_photobooth/print_kiosk/kiosk_gui.py 2> /home/colin/fail_log_print.txt
