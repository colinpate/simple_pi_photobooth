mkdir -p /home/colin/.config/systemd/user
cp /home/colin/simple_pi_photobooth/services/photo_booth_gui.service /home/colin/.config/systemd/user/photo_booth_gui.service
systemctl --user enable photo_booth_gui.service
systemctl --user start photo_booth_gui.service

