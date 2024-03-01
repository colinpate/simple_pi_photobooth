#!/bin/bash
source /home/colin/simple_pi_photobooth/booth_venv/bin/activate
python3 /home/colin/simple_pi_photobooth/upload_to_s3.py 2> /home/colin/fail_log_upload.txt
