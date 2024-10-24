from PyQt5.QtWidgets import QListWidget, QDialog, QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox, QApplication, QPushButton, QSlider
import subprocess
import os
import sys
from PyQt5.QtGui import QFont
from PyQt5.QtCore import QTimer, Qt

from common.common import load_config_file, load_config, save_config_file


def connect_to_wifi(ssid, password):
    result = subprocess.run(['nmcli', 'device', 'wifi', 'connect', ssid, 'password', password], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        print(f'Connected to {ssid}')
        return 0
    else:
        print(f'Failed to connect to {ssid}')
        print(result.stderr.decode('utf-8'))
        return -1


def scan_wifi_networks():
    result = subprocess.run(['nmcli', '-f', 'SSID', 'device', 'wifi', 'list'], stdout=subprocess.PIPE)
    output = result.stdout.decode('utf-8')
    lines = output.strip().split('\n')
    networks = []
    for line in lines[1:]:
        ssid = line.strip()
        if ssid:
            networks.append({'SSID': ssid})
    return networks


class TextDialog(QDialog):
    def __init__(self, label_text, input_text="", parent=None):
        super(TextDialog, self).__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        font = QFont("Arial", 20)
        self.setFont(font)

        self.setWindowTitle('')
        self.layout = QVBoxLayout(self)

        self.label = QLabel(label_text)
        self.layout.addWidget(self.label)

        # Password Input Field
        self.passwordInput = QLineEdit()
        self.passwordInput.setText(input_text)
        self.layout.addWidget(self.passwordInput)

        # OK and Cancel Buttons
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.layout.addWidget(self.buttonBox)

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        # Initialize the keyboard process variable
        self.keyboard_process = None
        self.resize(400, 100)

    def showEvent(self, event):
        super().showEvent(event)
        self.launch_keyboard()

    def closeEvent(self, event):
        self.terminate_keyboard()
        super().closeEvent(event)

    def accept(self):
        self.terminate_keyboard()
        super().accept()

    def reject(self):
        self.terminate_keyboard()
        super().reject()

    def launch_keyboard(self):
        # Start the virtual keyboard process
        try:
            self.keyboard_process = subprocess.Popen(['wvkbd-mobintl', "-L", "200"])
            # Ensure the password input retains focus
            #vself.passwordInput.setFocus()
        except Exception as e:
            print(f"Failed to launch virtual keyboard: {e}")

    def terminate_keyboard(self):
        if self.keyboard_process:
            try:
                self.keyboard_process.terminate()
                self.keyboard_process.wait()
                self.keyboard_process = None
            except Exception as e:
                print(f"Failed to terminate virtual keyboard: {e}")

    def get_text(self):
        return self.passwordInput.text()


class WifiInfo(QDialog):
    def __init__(self, ssid, return_code, parent=None):
        super(WifiInfo, self).__init__(parent)
        self.setWindowFlag(Qt.FramelessWindowHint)
        font = QFont("Arial", 20)
        self.setFont(font)

        self.setWindowTitle('')
        self.layout = QVBoxLayout(self)
        label_text = "Successfully connected to" if (return_code == 0) else "Failed to connect to"
        self.label = QLabel(f'{label_text} {ssid}')
        self.layout.addWidget(self.label)

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok)
        self.layout.addWidget(self.buttonBox)
        self.buttonBox.accepted.connect(self.close)
        
        # Add a timer to close the dialog after a set time period
        self.auto_close_timer = QTimer(self)
        self.auto_close_timer.setSingleShot(True)  # Ensures it runs only once
        self.auto_close_timer.timeout.connect(self.close)
        self.auto_close_timer.start(5 * 1000) # 5 seconds


class ConfirmDeleteDialog(QDialog):
    def __init__(self, parent=None):
        super(ConfirmDeleteDialog, self).__init__(parent)
        self.setWindowFlag(Qt.FramelessWindowHint)
        font = QFont("Arial", 20)
        self.setFont(font)

        self.setWindowTitle('')
        self.layout = QVBoxLayout(self)
        label_text = "Are you sure you want to delete all photos on the Photo Booth?"
        self.label = QLabel(label_text)
        self.layout.addWidget(self.label)

        # OK and Cancel Buttons
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.layout.addWidget(self.buttonBox)

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)


class SettingsDialog(QDialog):
    album_title_key = "album_title"
    local_test = False

    def __init__(self, config, signal_restart, parent=None):
        super(SettingsDialog, self).__init__(parent)

        self.original_config = config
        self.config_changes = {}
        self.signal_restart = signal_restart

        font = QFont("Arial", 20)
        self.setFont(font)

        self.setWindowTitle('Settings')
        self.layout = QVBoxLayout(self)

        # List Widget to Display Networks
        self.networkList = QListWidget()
        self.networkList.setFixedHeight(200)
        self.networkList.setStyleSheet("""
            QScrollBar:vertical {
                width: 25px;   /* Adjust the width as needed */
            }
            QScrollBar:horizontal {
                height: 25px;  /* Adjust the height for horizontal scrollbars if needed */
            }
        """)
        self.layout.addWidget(self.networkList)
        self.networkList.itemClicked.connect(self.network_selected)
        self.load_wifi_networks()

        # Add the preview color Button
        self.toggle_button = QPushButton(self.get_display_gray_text())
        self.toggle_button.setCheckable(True)
        self.layout.addWidget(self.toggle_button)
        self.toggle_button.toggled.connect(self.toggle_button_clicked)

        # Add the Contrast slider
        # self.slider = QSlider(Qt.Horizontal)
        # self.slider.setMinimum(100)
        # self.slider.setMaximum(200)
        # self.slider.setValue(110)  # Set default value
        # self.slider.valueChanged.connect(self.on_value_change)
        # self.layout.addWidget(self.slider)

        # Add the delete photos Button
        self.album_title_button = QPushButton('')
        self.update_album_button()
        self.layout.addWidget(self.album_title_button)
        self.album_title_button.pressed.connect(self.change_album_title)

        # Add the delete photos Button
        self.delete_button = QPushButton("Delete Photos")
        self.layout.addWidget(self.delete_button)
        self.delete_button.pressed.connect(self.confirm_delete)

        # Add the save Button
        self.save_button = QPushButton("Apply settings")
        self.layout.addWidget(self.save_button)
        self.save_button.pressed.connect(self.save_config)

        # Add the cancel Button
        self.cancel_button = QPushButton("Cancel")
        self.layout.addWidget(self.cancel_button)
        self.cancel_button.pressed.connect(self.close)

        # Add the cancel Button
        self.restart_button = QPushButton("Restart")
        self.layout.addWidget(self.restart_button)
        self.restart_button.pressed.connect(self.restart)

        self.resize(600, 400)
        
        # Add a timer to close the dialog after a set time period
        self.auto_close_timer = QTimer(self)
        self.auto_close_timer.setSingleShot(True)  # Ensures it runs only once
        self.auto_close_timer.timeout.connect(self.close)
        self.auto_close_timer.start(60 * 1000) # 60 seconds

        self.exec()

    def restart(self):
        self.signal_restart()
        self.close()

    def get_latest_value(self, parameter_key):
        return self.config_changes.get(parameter_key, self.original_config[parameter_key])

    def update_album_button(self):
        self.album_title_button.setText(f"Album Title: {self.get_latest_value(self.album_title_key)}")

    def change_album_title(self):
        album_title = self.get_latest_value(self.album_title_key)
        dialog = TextDialog("Album title:", album_title, parent=self)
        if dialog.exec():
            self.config_changes["album_title"] = dialog.get_text()
            self.update_album_button()

    def confirm_delete(self):
        dialog = ConfirmDeleteDialog(self)
        if dialog.exec():
            self.delete_photos()
            self.signal_restart()
            self.close()

    def delete_photos(self):
        for postfix in ["gray", "color", "original"]:
            photo_dir = self.original_config[f"{postfix}_image_dir"]
            delete_command = f"rm -rf {photo_dir}/*.jpg"
            print(delete_command)
            os.system(delete_command)
        with open(self.original_config["photo_path_db"], "w") as path_db:
            path_db.write("{}")
        
    def save_config(self):
        user_config_filename = "config.user.yaml"
        try:
            user_config = load_config_file(user_config_filename)
            print("Found user config:", user_config)
        except FileNotFoundError:
            user_config = {}

        config_changed = False
        for key, value in self.config_changes.items():
            if value != self.original_config[key]:
                user_config[key] = value
                config_changed = True

        if config_changed:
            print("Writing new user config:", user_config)
            save_config_file(user_config_filename, user_config)
            self.signal_restart()
        self.close()

    def on_value_change(self, value):
        # Update the label text with the slider's current value
        #self.label.setText(f'Slider Value: {value}')
        print(value)

    def get_display_gray_text(self):
        if self.config_changes.get("display_gray", self.original_config["display_gray"]):
            return "Displaying Black/White"
        else:
            return "Displaying Color"

    def toggle_button_clicked(self, checked):
        if checked:
            self.config_changes["display_gray"] = True
        else:
            self.config_changes["display_gray"] = False
        self.toggle_button.setText(self.get_display_gray_text())

    def load_wifi_networks(self):
        if self.local_test:
            networks = [
                {"SSID": f"Network{i}"}
                for i in range(15)
            ]
        else:
            networks = scan_wifi_networks()
        for network in networks:
            if network["SSID"] != "--":
                self.networkList.addItem(network['SSID'])

    def network_selected(self, item):
        ssid = item.text()
        print("Network selected")
        self.password_dialog = TextDialog(label_text=f'Enter password for {ssid}:', parent=self)
        if self.password_dialog.exec_():
            password = self.password_dialog.get_text()
            # Attempt to connect to Wi-Fi
            if not self.local_test:
                return_code = connect_to_wifi(ssid, password)
            else:
                return_code = 0
            self.wifi_dialog = WifiInfo(ssid, return_code, parent=self)
            self.wifi_dialog.exec_()


if __name__ == "__main__":
    app = QApplication([])
    window = SettingsDialog(signal_restart=None, config=load_config())