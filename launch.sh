#!/bin/bash
source /home/colin/simple_pi_photobooth/booth_venv/bin/activate
export PYTHONPATH=$PYTHONPATH:/home/colin/simple_pi_photobooth
python3 /home/colin/simple_pi_photobooth/booth/booth.py 2> /home/colin/fail_log.txt
