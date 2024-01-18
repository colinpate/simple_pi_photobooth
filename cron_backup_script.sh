#!/bin/bash

SOURCE_FOLDER="/home/colin/booth_photos"
DESTINATION_FOLDER="/media/colin/USB20FD/"

rsync -av "$SOURCE_FOLDER" "$DESTINATION_FOLDER"
