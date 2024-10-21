from PyQt5.QtWidgets import QListWidget, QDialog, QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox, QApplication
import subprocess
import os
import sys
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt


def connect_to_wifi(ssid, password):
    result = subprocess.run(['nmcli', 'device', 'wifi', 'connect', ssid, 'password', password], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        print(f'Connected to {ssid}')
    else:
        print(f'Failed to connect to {ssid}')
        print(result.stderr.decode('utf-8'))


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
        super(PasswordDialog, self).__init__(parent)
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


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        self.local_test = True
        super(SettingsDialog, self).__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)

        font = QFont("Arial", 15)  # You can choose any font family and size
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

        # Load Wi-Fi Networks
        self.load_wifi_networks()

        # Handle Network Selection
        self.networkList.itemClicked.connect(self.network_selected)

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
        self.password_dialog = PasswordDialog(ssid)
        if self.password_dialog.exec_():
            password = self.password_dialog.get_password()
            # Attempt to connect to Wi-Fi
            connect_to_wifi(ssid, password)

if __name__ == "__main__":
    app = QApplication([])
    window = SettingsDialog()
    window.show()
    #window.showFullScreen()  # Show in full screen since it's a touch screen
    sys.exit(app.exec_())