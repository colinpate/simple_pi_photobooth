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
        return -1
    else:
        print(f'Failed to connect to {ssid}')
        print(result.stderr.decode('utf-8'))
        return 0


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


class PasswordDialog(QDialog):
    def __init__(self, ssid, parent=None):
        parent.close()
        super(PasswordDialog, self).__init__(parent)
        self.setWindowFlag(Qt.FramelessWindowHint)
        font = QFont("Arial", 15)
        self.setFont(font)

        self.setWindowTitle('Enter Password')
        self.layout = QVBoxLayout(self)
        self.label = QLabel(f'Enter password for {ssid}:')
        self.layout.addWidget(self.label)

        # Password Input Field
        self.passwordInput = QLineEdit()
        self.passwordInput.setEchoMode(QLineEdit.Password)
        self.layout.addWidget(self.passwordInput)

        # OK and Cancel Buttons
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.layout.addWidget(self.buttonBox)

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        # Initialize the keyboard process variable
        self.keyboard_process = None

        self.exec()

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
            self.keyboard_process = subprocess.Popen(['wvkbd-mobintl'])
            # Ensure the password input retains focus
            self.passwordInput.setFocus()
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

    def get_password(self):
        return self.passwordInput.text()


class WifiInfo(QDialog):
    def __init__(self, ssid, return_code, parent=None):
        super(WifiInfo, self).__init__(parent)
        self.setWindowFlag(Qt.FramelessWindowHint)
        font = QFont("Arial", 15)
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


class SettingsDialog(QDialog):
    def __init__(self, config, signal_restart, parent=None):
        self.local_test = True
        super(SettingsDialog, self).__init__(parent)

        self.original_config = config
        self.config_changes = {}
        self.signal_restart = signal_restart

        font = QFont("Arial", 25)  # You can choose any font family and size
        self.setFont(font)

        self.setWindowTitle('Settings')
        self.layout = QVBoxLayout(self)

        # List Widget to Display Networks
        self.networkList = QListWidget()
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
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(100)
        self.slider.setMaximum(200)
        self.slider.setValue(110)  # Set default value
        self.slider.valueChanged.connect(self.on_value_change)
        self.layout.addWidget(self.slider)

        # Add the save Button
        self.save_button = QPushButton("Save settings")
        self.layout.addWidget(self.save_button)
        self.save_button.pressed.connect(self.save_config)

        # Add the cancel Button
        self.cancel_button = QPushButton("Cancel")
        self.layout.addWidget(self.cancel_button)
        self.cancel_button.pressed.connect(self.close)

        self.resize(600, 400)
        
        # Add a timer to close the dialog after a set time period
        self.auto_close_timer = QTimer(self)
        self.auto_close_timer.setSingleShot(True)  # Ensures it runs only once
        self.auto_close_timer.timeout.connect(self.close)
        self.auto_close_timer.start(60 * 1000) # 60 seconds

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
            return "Displaying Black & White"
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
            self.networkList.addItem(network['SSID'])

    def network_selected(self, item):
        ssid = item.text()
        print("Network selected")
        self.password_dialog = PasswordDialog(ssid)
        if self.password_dialog.exec_():
            password = self.password_dialog.get_password()
            # Attempt to connect to Wi-Fi
            if not self.local_test:
                return_code = connect_to_wifi(ssid, password)
            else:
                return_code = 0
            self.wifi_dialog = WifiInfo(ssid, return_code)
            self.wifi_dialog.exec_()


if __name__ == "__main__":
    app = QApplication([])
    window = SettingsDialog(signal_restart=None, config=load_config())
    window.show()
    #window.showFullScreen()  # Show in full screen since it's a touch screen
    sys.exit(app.exec_())