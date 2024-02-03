import sys
import os
import datetime
import json

from PyQt5.QtCore import Qt, QProcess
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QMainWindow, QLabel, QApplication, QGridLayout, QWidget, QPushButton, \
    QPlainTextEdit, QMessageBox, QLineEdit, QVBoxLayout, QHBoxLayout, QSpinBox, QToolBar, QTabWidget

APP_CONFIG_JSON = 'app_config.json'


def resource_path(relative_path):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath("__file")))
    return os.path.join(base_path, relative_path)


def extract_vars(l):
    """
    Extracts variables from lines, looking for lines
    containing an equals, and splitting into key=value.
    """
    data = {}
    for s in l.splitlines():
        if "=" in s:
            name, value = s.split("=")
            data[name] = value
    return data


class MainWindow(QMainWindow):

    def __init__(self):
        super(MainWindow, self).__init__()

        self.app_config_json = resource_path(APP_CONFIG_JSON)

        if os.path.exists(self.app_config_json):
            self.app_config = json.load(open(self.app_config_json))
        else:
            self.app_config = {}

        self.app_config['rtde_config_file'] = resource_path('control_loop_configuration.xml')
        # self.app_config['app_config'] = resource_path('app_config.json')
        json.dump(self.app_config, open(self.app_config_json, 'w'))

        self.start_time = None
        self.p = None

        self.setWindowTitle("APM Machine Tending Exhibit")

        apm_logo = QLabel("APM Logo")
        apm_logo.setPixmap(QPixmap(resource_path("small-block-logo.jpg")))
        apm_logo.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        lego_brick_drawing = QLabel("Lego Brick")
        lego_brick_drawing.setPixmap(QPixmap(resource_path("universal lego brick v13.jpg")))
        lego_brick_drawing.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.start_button = QPushButton('Start', self)
        self.start_button.setToolTip("Start the Machine Tending Control Loop")
        self.start_button.clicked.connect(self.on_start_click)

        self.stop_button = QPushButton('Stop', self)
        self.stop_button.setToolTip("Stop the Machine Tending Control Loop")
        self.stop_button.clicked.connect(self.on_stop_click)
        self.stop_button.setDisabled(True)

        self.save_config_button = QPushButton('Save Config', self)
        self.save_config_button.clicked.connect(self.on_save_config_click)
        self.save_config_button.setDisabled(True)
        self.cancel_config_button = QPushButton('Cancel Config Change', self)
        self.cancel_config_button.clicked.connect(self.on_cancel_config_click)
        self.cancel_config_button.setDisabled(True)

        self.cobot_ip_address_label = QLabel("Cobot IP Address")
        self.cobot_ip_address = QLineEdit()
        self.cobot_ip_address.setText(self.app_config.get('cobot_ip_address', ''))
        self.cobot_ip_address.textEdited.connect(self.cobot_ip_address_edited)

        self.max_jobs_label = QLabel("Max Print Jobs")
        self.max_jobs = QSpinBox()
        self.max_jobs.setMinimum(1)
        self.max_jobs.setMaximum(50)
        self.max_jobs.setValue(self.app_config.get('max_jobs', 1))
        self.max_jobs.valueChanged.connect(self.max_jobs_changed)

        '''
        self.cobot_program_label = QLabel("Cobot Program Filename")
        self.cobot_program = QLineEdit()
        self.cobot_program.textEdited.connect(self.cobot_program_filename_edited)

        self.cobot_installation_label = QLabel("Cobot Installation Filename")
        self.cobot_installation = QLineEdit()
        self.cobot_installation.textEdited.connect(self.cobot_installation_filename_edited)
        '''

        self.gcode_with_prime_line_label = QLabel("G-Code (with Prime Line) Filename")
        self.gcode_with_prime_line = QLineEdit()
        self.gcode_with_prime_line.setText(self.app_config.get('gcode_filename', ''))
        self.gcode_with_prime_line.textEdited.connect(self.gcode_filename_edited)

        self.gcode_no_prime_line_label = QLabel("G-Code (without Prime Line) Filename")
        self.gcode_no_prime_line = QLineEdit()
        self.gcode_no_prime_line.setText(self.app_config.get('gcode_no_prime_filename', ''))
        self.gcode_no_prime_line.textEdited.connect(self.gcode_no_prime_filename_edited)

        self.octoprint_api_key_label = QLabel("Octoprint API Key")
        self.octoprint_api_key = QLineEdit()
        self.octoprint_api_key.setText(self.app_config.get('octoprint_api_key', ''))
        self.octoprint_api_key.textEdited.connect(self.octoprint_api_key_edited)

        self.octoprint_url_label = QLabel("Octoprint URL")
        self.octoprint_url = QLineEdit()
        self.octoprint_url.setText(self.app_config.get("octoprint_url", "127.0.0.1:5000"))
        self.octoprint_url.textEdited.connect(self.octoprint_url_edited)

        self.printer_bed_pick_temp_label = QLabel("Printer Bed Pick Temp (C)", )
        self.printer_bed_pick_temp = QSpinBox()
        self.printer_bed_pick_temp.setMinimum(25)
        self.printer_bed_pick_temp.setMaximum(60)
        self.printer_bed_pick_temp.setValue(self.app_config.get('printer_bed_pick_temp', 40))
        self.printer_bed_pick_temp.valueChanged.connect(self.printer_bed_pick_temp_changed)

        self.stderr_display = QPlainTextEdit()
        self.stderr_display.setReadOnly(True)
        self.stderr_display.setCenterOnScroll(True)

        self.job_count_label = QLabel("Completed Job Count:")
        self.job_count = QLineEdit()
        self.job_count.setReadOnly(True)
        self.run_time_label = QLabel("Control Loop Run Time:")
        self.run_time = QLineEdit()
        self.run_time.setReadOnly(True)

        grid_layout_session_stats = QGridLayout()
        grid_layout_session_stats.addWidget(apm_logo, 0, 0)
        grid_layout_session_stats.addWidget(lego_brick_drawing, 0, 1)
        grid_layout_session_stats.addWidget(self.job_count_label, 1, 0)
        grid_layout_session_stats.addWidget(self.job_count, 1, 1)
        grid_layout_session_stats.addWidget(self.run_time_label, 2, 0)
        grid_layout_session_stats.addWidget(self.run_time, 2, 1)

        horizontal_layout_graphics = QHBoxLayout()
        horizontal_layout_graphics.addWidget(apm_logo)
        horizontal_layout_graphics.addWidget(lego_brick_drawing)

        grid_layout_config_fields = QGridLayout()
        grid_layout_config_fields.addWidget(self.cobot_ip_address_label, 0, 0)
        grid_layout_config_fields.addWidget(self.cobot_ip_address, 0, 1)
        grid_layout_config_fields.addWidget(self.max_jobs_label, 1, 0)
        grid_layout_config_fields.addWidget(self.max_jobs, 1, 1)
        grid_layout_config_fields.addWidget(self.octoprint_api_key_label, 2, 0)
        grid_layout_config_fields.addWidget(self.octoprint_api_key, 2, 1)
        grid_layout_config_fields.addWidget(self.octoprint_url_label, 3, 0)
        grid_layout_config_fields.addWidget(self.octoprint_url, 3, 1)
        grid_layout_config_fields.addWidget(self.printer_bed_pick_temp_label, 4, 0)
        grid_layout_config_fields.addWidget(self.printer_bed_pick_temp, 4, 1)
        grid_layout_config_fields.addWidget(self.gcode_with_prime_line_label, 5, 0)
        grid_layout_config_fields.addWidget(self.gcode_with_prime_line, 5, 1)
        grid_layout_config_fields.addWidget(self.gcode_no_prime_line_label, 6, 0)
        grid_layout_config_fields.addWidget(self.gcode_no_prime_line, 6, 1)

        horizontal_layout_config_buttons = QHBoxLayout()
        horizontal_layout_config_buttons.addWidget(self.save_config_button)
        horizontal_layout_config_buttons.addWidget(self.cancel_config_button)

        grid_layout_run = QGridLayout()
        grid_layout_run.addLayout(grid_layout_session_stats, 0, 0)
        grid_layout_run.addWidget(self.stderr_display, 0, 1)

        grid_layout_run.addWidget(self.start_button, 1, 0)
        grid_layout_run.addWidget(self.stop_button, 1, 1)

        grid_layout_config = QGridLayout()
        grid_layout_config.addLayout(grid_layout_config_fields, 0, 0)
        grid_layout_config.addLayout(horizontal_layout_config_buttons, 1, 0)

        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.North)
        tabs.setMovable(False)

        self.run_widget = QWidget()
        self.run_widget.setLayout(grid_layout_run)
        tabs.addTab(self.run_widget, "Run")

        self.config_widget = QWidget()
        self.config_widget.setLayout(grid_layout_config)
        tabs.addTab(self.config_widget, "Config")

        self.setCentralWidget(tabs)

    def stderr_message(self, s):
        self.stderr_display.appendPlainText(s)

    def cobot_ip_address_edited(self, s):
        self.app_config['cobot_ip_address'] = s
        self.run_widget.setDisabled(True)
        self.save_config_button.setDisabled(False)
        self.cancel_config_button.setDisabled(False)

    def max_jobs_changed(self, n):
        self.app_config['max_jobs'] = n
        self.run_widget.setDisabled(True)
        self.save_config_button.setDisabled(False)
        self.cancel_config_button.setDisabled(False)

    def gcode_filename_edited(self, s):
        self.app_config['gcode_filename'] = s
        self.run_widget.setDisabled(True)
        self.save_config_button.setDisabled(False)
        self.cancel_config_button.setDisabled(False)

    def gcode_no_prime_filename_edited(self, s):
        self.app_config['gcode_no_prime_filename'] = s
        self.run_widget.setDisabled(True)
        self.save_config_button.setDisabled(False)
        self.cancel_config_button.setDisabled(False)

    def octoprint_api_key_edited(self, s):
        self.app_config['octoprint_api_key'] = s
        self.run_widget.setDisabled(True)
        self.save_config_button.setDisabled(False)
        self.cancel_config_button.setDisabled(False)

    def octoprint_url_edited(self, s):
        self.app_config['octoprint_url'] = s
        self.run_widget.setDisabled(True)
        self.save_config_button.setDisabled(False)
        self.cancel_config_button.setDisabled(False)

    def printer_bed_pick_temp_changed(self, n):
        self.app_config['printer_bed_pick_temp'] = n
        self.run_widget.setDisabled(True)
        self.save_config_button.setDisabled(False)
        self.cancel_config_button.setDisabled(False)

    def on_save_config_click(self):
        json.dump(self.app_config, open(self.app_config_json, 'w'))
        self.start_button.setDisabled(False)
        self.stop_button.setDisabled(True)
        self.run_widget.setDisabled(False)
        self.save_config_button.setDisabled(True)
        self.cancel_config_button.setDisabled(True)

    def on_cancel_config_click(self):
        self.app_config = json.load(open(self.app_config_json))
        self.cobot_ip_address.setText(self.app_config.get('cobot_ip_address', ''))
        self.max_jobs.setValue(self.app_config.get('max_jobs', 0))
        self.gcode_with_prime_line.setText(self.app_config.get('gcode_filename', ''))
        self.gcode_no_prime_line.setText(self.app_config.get('gcode_no_prime_filename', ''))
        self.start_button.setDisabled(False)
        self.stop_button.setDisabled(True)
        self.run_widget.setDisabled(False)
        self.save_config_button.setDisabled(True)
        self.cancel_config_button.setDisabled(True)

    def on_start_click(self):

        dlg = QMessageBox(self)
        dlg.setWindowTitle("Before Launch...")
        dlg.setText(
            'Before launching the machine tending control loop, verify the following:\n\n'
            '(a) the Cobot is powered on and in the normal mode\n'
            '(b) the 3D Printer is idle\n'
            '(c) the printer bed is clean\n\n'
            'Once the control loop has started, go to the Polyscope tablet and launch (or restart after protective stop ) the mt_rtde_control_loop program.')
        dlg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        dlg.setIcon(QMessageBox.Information)
        button = dlg.exec_()

        if button == QMessageBox.Ok:
            self.stderr_message("Launching Control Loop")
            self.p = QProcess()
            self.p.readyReadStandardOutput.connect(self.handle_stdout)
            self.p.readyReadStandardError.connect(self.handle_stderr)
            self.p.finished.connect(self.process_finished)
            self.p.start("python", [resource_path('mt_control_loop.py'),
                                    resource_path('app_config.json'),
                                    resource_path('control_loop_configuration.xml'),
                                    "True"])

            self.start_button.setDisabled(True)
            self.config_widget.setDisabled(True)
            self.stop_button.setDisabled(False)

    def on_stop_click(self):
        self.stop_button.setDisabled(True)
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Before Stop...")
        dlg.setText(
            'If printer is active, stopping the control loop will not halt the printer.  You will need to remove the print from the printer bed.')
        dlg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        dlg.setIcon(QMessageBox.Information)
        button = dlg.exec_()

        if button == QMessageBox.Ok:
            self.stderr_message("Stopping Control Loop")

            if self.p is not None:
                self.p.kill()
            self.start_button.setDisabled(False)
            self.config_widget.setDisabled(False)
        else:
            self.stop_button.setDisabled(False)

    def handle_stderr(self):
        data = self.p.readAllStandardError()
        message = bytes(data).decode("utf8")
        self.stderr_message(message)

    def handle_stdout(self):
        result = bytes(self.p.readAllStandardOutput()).decode("utf8")
        data = extract_vars(result)
        if 'print_job_count' in data:
            self.job_count.setText(data['print_job_count'])
        if 'start_time' in data:
            self.start_time = int(data['start_time'])
        if 'current_time' in data:
            if self.start_time is not None:
                runtime_seconds = int(data['current_time']) - self.start_time
                self.run_time.setText(str(datetime.timedelta(seconds=runtime_seconds)))

    def handle_state(self, state):
        states = {
            QProcess.NotRunning: 'Not running',
            QProcess.Starting: 'Starting',
            QProcess.Running: 'Running',
        }
        state_name = states[state]
        self.stderr_message("State changed: {}".format(state_name))

    def process_finished(self, exit_code, exit_status):
        self.stderr_message("Process finished, exit code = {0}, exit status = {1}".format(exit_code, exit_status))
        self.stop_button.setDisabled(True)
        self.start_button.setDisabled(False)
        self.config_widget.setDisabled(False)
        self.p = None


app = QApplication(sys.argv)

window = MainWindow()
window.show()

app.exec_()
