from PyQt5.QtWidgets import QListWidget, QDialog, QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox
import subprocess

def connect_to_wifi(ssid, password):
    result = subprocess.run(['nmcli', 'device', 'wifi', 'connect', ssid, 'password', password], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        print(f'Connected to {ssid}')
    else:
        print(f'Failed to connect to {ssid}')
        print(result.stderr.decode('utf-8'))


class PasswordDialog(QDialog):
    def __init__(self, ssid, parent=None):
        super(PasswordDialog, self).__init__(parent)
        self.setWindowTitle('Enter Password')
        self.layout = QVBoxLayout(self)
        self.label = QLabel(f'Enter password for {ssid}:')
        self.layout.addWidget(self.label)

        # Password Input Field
        self.passwordInput = QLineEdit()
        self.passwordInput.setEchoMode(QLineEdit.Password)
        self.layout.addWidget(self.passwordInput)

        # On-Screen Keyboard
        self.keyboard = OnScreenKeyboard(self.passwordInput)
        self.layout.addWidget(self.keyboard)

        # OK and Cancel Buttons
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.layout.addWidget(self.buttonBox)

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

    def get_password(self):
        return self.passwordInput.text()


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


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super(SettingsDialog, self).__init__(parent)
        self.setWindowTitle('Settings')
        self.layout = QVBoxLayout(self)

        # List Widget to Display Networks
        self.networkList = QListWidget()
        self.layout.addWidget(self.networkList)

        # Load Wi-Fi Networks
        self.load_wifi_networks()

        # Handle Network Selection
        self.networkList.itemClicked.connect(self.network_selected)

    def load_wifi_networks(self):
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