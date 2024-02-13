import sys
import os
import datetime
import json

from PyQt5.QtCore import Qt, QProcess
from PyQt5.QtGui import QPixmap, QPainter
from PyQt5.QtWidgets import QMainWindow, QLabel, QApplication, QGridLayout, QWidget, QPushButton, \
    QPlainTextEdit, QMessageBox, QLineEdit, QVBoxLayout, QHBoxLayout, QSpinBox, QTabWidget, QDoubleSpinBox
from PyQt5.QtChart import QChart, QChartView, QBarSet, QBarCategoryAxis, QStackedBarSeries, QValueAxis

APP_CONFIG_JSON = 'app_config.json'

GLOBAL_STYLE = """ QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox { 
    border: 1px solid;
    border-color: grey;
    font-size: 17px;
    }
    QLabel {font-size: 17px}
    QPushButton:hover {background-color: lightblue;}
    """
# QPushButton {font-size: 30px; border-radius: 8px}
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

        self.setGeometry(100, 100, 1000, 100)

        self.app_config_json = resource_path(APP_CONFIG_JSON)

        if os.path.exists(self.app_config_json):
            self.app_config = json.load(open(self.app_config_json))
        else:
            self.app_config = {}

        self.app_config['rtde_config_file'] = resource_path('control_loop_configuration.xml')
        json.dump(self.app_config, open(self.app_config_json, 'w'))

        self.start_time = None
        self.p = None

        self.setWindowTitle("APM Machine Tending Exhibit")

        apm_logo = QLabel("APM Logo")
        apm_logo.setPixmap(QPixmap(resource_path("small-block-logo.jpg")))
        apm_logo.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        ur_logo = QLabel("UR Logo")
        ur_logo.setPixmap(QPixmap(resource_path("UR logo.jpg")))
        ur_logo.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        lego_brick_drawing = QLabel("Lego Brick")
        lego_brick_drawing.setPixmap(QPixmap(resource_path("universal lego brick v13.jpg")))
        lego_brick_drawing.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.start_button = QPushButton('Start', self)
        font = self.start_button.font()
        font.setBold(True)
        font.setPointSize(20)
        self.start_button.setFont(font)
        self.start_button.setStyleSheet("border: 1px solid; border-radius: 5px; border-color: grey")
        self.start_button.setToolTip("Start the Machine Tending Control Loop")
        self.start_button.clicked.connect(self.on_start_click)

        self.stop_button = QPushButton('Stop', self)
        font = self.stop_button.font()
        font.setBold(True)
        font.setPointSize(20)
        self.stop_button.setFont(font)
        self.stop_button.setStyleSheet("border: 1px solid; border-radius: 5px; border-color: grey")
        self.stop_button.setToolTip("Stop the Machine Tending Control Loop")
        self.stop_button.clicked.connect(self.on_stop_click)
        self.stop_button.setDisabled(True)

        self.save_config_button = QPushButton('Save Config', self)
        font = self.save_config_button.font()
        font.setBold(True)
        font.setPointSize(20)
        self.save_config_button.setFont(font)
        self.save_config_button.setStyleSheet("border: 1px solid; border-radius: 5px; border-color: grey")
        self.save_config_button.clicked.connect(self.on_save_config_click)
        self.save_config_button.setDisabled(True)

        self.cancel_config_button = QPushButton('Cancel Config Change', self)
        font = self.cancel_config_button.font()
        font.setBold(True)
        font.setPointSize(20)
        self.cancel_config_button.setFont(font)
        self.cancel_config_button.setStyleSheet("border: 1px solid; border-radius: 5px; border-color: grey")
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

        self.printer_bed_pick_temp_label = QLabel("Printer Bed Pick Temp", )
        self.printer_bed_pick_temp = QSpinBox()
        self.printer_bed_pick_temp.setMinimum(25)
        self.printer_bed_pick_temp.setMaximum(60)
        self.printer_bed_pick_temp.setSuffix(' C')
        self.printer_bed_pick_temp.setValue(self.app_config.get('printer_bed_pick_temp', 40))
        self.printer_bed_pick_temp.valueChanged.connect(self.printer_bed_pick_temp_changed)

        self.max_cycle_time_label = QLabel("Max cycle time (for bar chart display)")
        self.max_cycle_time = QSpinBox()
        self.max_cycle_time.setSingleStep(1)
        self.max_cycle_time.setMinimum(1)
        self.max_cycle_time.setMaximum(60)
        self.max_cycle_time.setSuffix(' min')
        self.max_cycle_time.setValue(self.app_config.get('max_cycle_time', 20))
        self.max_cycle_time.valueChanged.connect(self.max_cycle_time_changed)

        self.watchdog_timer_interval_label = QLabel("Cobot Watchdog Timer Interval")
        self.watchdog_timer_interval = QDoubleSpinBox()
        self.watchdog_timer_interval.setRange(0.1,0.5)
        self.watchdog_timer_interval.setSingleStep(0.05)
        self.watchdog_timer_interval.setSuffix(' sec')
        self.watchdog_timer_interval.setStyleSheet("border: 1px solid; border-color:grey")
        self.watchdog_timer_interval.setValue(self.app_config.get("watchdog_timer_interval", 0.25))
        self.watchdog_timer_interval.valueChanged.connect(self.watchdog_timer_interval_edited)

        self.stderr_display = QPlainTextEdit()
        self.stderr_display.setReadOnly(True)
        self.stderr_display.setCenterOnScroll(True)

        self.job_count_label = QLabel("Completed Job Count:")
        self.job_count = QLineEdit()
        self.job_count.setReadOnly(True)
        self.last_completed_job_time_label = QLabel("Last Job Cycle Time:")
        self.last_completed_job_time = QLineEdit()
        self.last_completed_job_time.setReadOnly(True)
        self.run_time_label = QLabel("Control Loop Run Time:")
        self.run_time = QLineEdit()
        self.run_time.setReadOnly(True)

        self.series = QStackedBarSeries()

        self.printing_bar_set = QBarSet("Printing")
        self.cooling_bar_set = QBarSet("Cooling")
        self.pick_and_place_bar_set = QBarSet("Pick and Place")
        self.series.append(self.printing_bar_set)
        self.series.append(self.cooling_bar_set)
        self.series.append(self.pick_and_place_bar_set)

        self.bc_widget = QChart()
        self.bc_widget.setAnimationOptions(QChart.SeriesAnimations)
        self.bc_widget.addSeries(self.series)

        cycle_categories = [str(i) for i in range(1, self.app_config['max_jobs']+1)]
        self.axisX = QBarCategoryAxis()
        self.axisX.append(cycle_categories)
        self.axisX.setTitleText("Job Count")
        self.bc_widget.setAxisX(self.axisX, self.series)

        self.axisY = QValueAxis()
        self.axisY.setRange(0, self.app_config.get('max_cycle_time', 20))
        self.axisY.setTickType(QValueAxis.TicksFixed)
        self.axisY.setTickAnchor(0)
        self.axisY.setTickInterval(1.0)
        self.axisY.setTitleText("Minutes")
        self.bc_widget.addAxis(self.axisY, Qt.AlignLeft)
        self.series.attachAxis(self.axisY)

        chartview = QChartView(self.bc_widget)
        chartview.setRenderHint(QPainter.Antialiasing)
        self.bc_widget.setMinimumHeight(300)

        session_stats_layout = QGridLayout()
        session_stats_layout.addWidget(self.job_count_label, 0, 0)
        session_stats_layout.addWidget(self.job_count, 0, 1)
        session_stats_layout.addWidget(self.last_completed_job_time_label, 1, 0)
        session_stats_layout.addWidget(self.last_completed_job_time, 1, 1)
        session_stats_layout.addWidget(self.run_time_label, 2, 0)
        session_stats_layout.addWidget(self.run_time, 2, 1)

        grid_layout_basic_config_fields = QGridLayout()
        grid_layout_basic_config_fields.addWidget(self.max_jobs_label, 1, 0)
        grid_layout_basic_config_fields.addWidget(self.max_jobs, 1, 1)
        grid_layout_basic_config_fields.addWidget(self.gcode_with_prime_line_label, 2, 0)
        grid_layout_basic_config_fields.addWidget(self.gcode_with_prime_line, 2, 1)
        grid_layout_basic_config_fields.addWidget(self.gcode_no_prime_line_label, 3, 0)
        grid_layout_basic_config_fields.addWidget(self.gcode_no_prime_line, 3, 1)
        grid_layout_basic_config_fields.addWidget(self.printer_bed_pick_temp_label, 4, 0)
        grid_layout_basic_config_fields.addWidget(self.printer_bed_pick_temp, 4, 1)
        grid_layout_basic_config_fields.addWidget(self.max_cycle_time_label, 5, 0)
        grid_layout_basic_config_fields.addWidget(self.max_cycle_time, 5, 1)

        grid_layout_advanced_config_fields = QGridLayout()
        grid_layout_advanced_config_fields.addWidget(self.cobot_ip_address_label, 0, 0)
        grid_layout_advanced_config_fields.addWidget(self.cobot_ip_address, 0, 1)
        grid_layout_advanced_config_fields.addWidget(self.octoprint_api_key_label, 1, 0)
        grid_layout_advanced_config_fields.addWidget(self.octoprint_api_key, 1, 1)
        grid_layout_advanced_config_fields.addWidget(self.octoprint_url_label, 2, 0)
        grid_layout_advanced_config_fields.addWidget(self.octoprint_url, 2, 1)
        grid_layout_advanced_config_fields.addWidget(self.watchdog_timer_interval_label, 3, 0)
        grid_layout_advanced_config_fields.addWidget(self.watchdog_timer_interval, 3, 1)

        horizontal_layout_config_buttons = QHBoxLayout()
        horizontal_layout_config_buttons.addWidget(self.save_config_button)
        horizontal_layout_config_buttons.addWidget(self.cancel_config_button)

        graphics_layout = QHBoxLayout()
        graphics_layout.addWidget(apm_logo)
        graphics_layout.addWidget(ur_logo)

        status_layout_left = QVBoxLayout()
        status_layout_left.addLayout(graphics_layout)
        status_layout_left.addWidget(lego_brick_drawing)
        status_layout_left.addLayout(session_stats_layout)
        status_layout = QHBoxLayout()
        status_layout.addLayout(status_layout_left)
        status_layout.addWidget(self.stderr_display)

        start_stop_layout = QHBoxLayout()
        start_stop_layout.addWidget(self.start_button)
        start_stop_layout.addWidget(self.stop_button)

        vertical_layout_run_tab = QVBoxLayout()
        vertical_layout_run_tab.addLayout(status_layout)
        vertical_layout_run_tab.addWidget(chartview)
        vertical_layout_run_tab.addLayout(start_stop_layout)

        label1 = QLabel('Basic')
        hlayout1 = QHBoxLayout()
        hlayout1.addWidget(label1)
        label2 = QLabel('Advanced (changes require coordination with Cobot and Octoprint configurations)')
        hlayout2 = QHBoxLayout()
        hlayout2.addWidget(label2)

        vertical_layout_config_tab = QVBoxLayout()
        vertical_layout_config_tab.addLayout(hlayout1)
        vertical_layout_config_tab.addLayout(grid_layout_basic_config_fields)
        vertical_layout_config_tab.addLayout(hlayout2)
        vertical_layout_config_tab.addLayout(grid_layout_advanced_config_fields)
        vertical_layout_config_tab.insertSpacing(5,100)
        vertical_layout_config_tab.addLayout(horizontal_layout_config_buttons)

        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.North)
        tabs.setMovable(False)

        self.run_widget = QWidget()
        self.run_widget.setLayout(vertical_layout_run_tab)
        tabs.addTab(self.run_widget, "Run")

        self.config_widget = QWidget()
        self.config_widget.setLayout(vertical_layout_config_tab)
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

    def max_cycle_time_changed(self, n):
        self.app_config['max_cycle_time'] = n
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

    def watchdog_timer_interval_edited(self, x):
        self.app_config['watchdog_timer_interval'] = x
        self.run_widget.setDisabled(True)
        self.save_config_button.setDisabled(False)
        self.cancel_config_button.setDisabled(False)

    def on_save_config_click(self):
        json.dump(self.app_config, open(self.app_config_json, 'w'))

        self.bc_widget.removeAxis(self.axisX)
        cycle_categories = [str(i) for i in range(1, self.app_config['max_jobs']+1)]
        self.axisX = QBarCategoryAxis()
        self.axisX.append(cycle_categories)
        self.axisX.setTitleText("Job Count")
        self.bc_widget.setAxisX(self.axisX, self.series)

        self.bc_widget.removeAxis(self.axisY)
        self.axisY = QValueAxis()
        self.axisY.setRange(0, self.app_config['max_cycle_time'])
        self.axisY.setTickType(QValueAxis.TicksFixed)
        self.axisY.setTickAnchor(0)
        self.axisY.setTickInterval(1.0)
        self.axisY.setTitleText("Minutes")
        self.bc_widget.setAxisY(self.axisY, self.series)

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
        self.octoprint_api_key.setText(self.app_config.get('octoprint_api_key', ''))
        self.octoprint_url.setText(self.app_config.get("octoprint_url", "127.0.0.1:5000"))
        self.printer_bed_pick_temp.setValue(self.app_config.get('printer_bed_pick_temp', 40))
        self.max_cycle_time.setValue(self.app_config.get('max_cycle_time', 20))
        self.watchdog_timer_interval.setValue(self.app_config.get("watchdog_timer_interval", 0.25))

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
            '(c) the print sheet is empty and clean\n\n'
            'IMPORTANT: Once the control loop has started, go to the Polyscope tablet and launch (or restart after protective stop) the mt_rtde_control_loop program.')
        dlg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        dlg.setIcon(QMessageBox.Information)
        button = dlg.exec_()

        if button == QMessageBox.Ok:
            self.stderr_message("Launching Control Loop")

            self.printing_bar_set.remove(0, self.printing_bar_set.count())
            self.cooling_bar_set.remove(0, self.cooling_bar_set.count())
            self.pick_and_place_bar_set.remove(0,self.pick_and_place_bar_set.count())

            self.job_count.clear()
            self.last_completed_job_time.clear()
            self.run_time.clear()

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
            self.job_count.setText("{0} of {1}".format(data['print_job_count'], self.app_config['max_jobs']))
        if 'start_time' in data:
            self.start_time = int(data['start_time'])
        if 'current_time' in data:
            if self.start_time is not None:
                runtime_seconds = int(data['current_time']) - self.start_time
                self.run_time.setText(str(datetime.timedelta(seconds=runtime_seconds)))
        if 'cycle_stats' in data:
            raw_cycle_stats = [int(i) for i in data['cycle_stats'].split(',')]
            cycle_runtime_seconds = raw_cycle_stats[-1] - raw_cycle_stats[0]
            self.last_completed_job_time.setText(str(datetime.timedelta(seconds=cycle_runtime_seconds)))

            cycle_stats = [(raw_cycle_stats[i + 1] - raw_cycle_stats[i])/60 for i in range(len(raw_cycle_stats) - 1)]
            self.printing_bar_set.append(cycle_stats[0])
            self.cooling_bar_set.append(cycle_stats[1])
            self.pick_and_place_bar_set.append(cycle_stats[2])

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
        self.start_time = None


app = QApplication(sys.argv)
app.setStyleSheet(GLOBAL_STYLE)

window = MainWindow()
window.show()

app.exec_()
