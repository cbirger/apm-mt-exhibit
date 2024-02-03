import signal
import time
import sys
import threading
import os
import json
from collections import namedtuple
import rtde.rtde as rtde
import rtde.rtde_config as rtde_config
from octorest import OctoRest

# Default Parameters for RTDE (Cobot) Client
ROBOT_HOST = "192.168.0.30"
ROBOT_PORT = 30004

# Default Parameters for OctoRest (Printer) Client
OCTOPRINT_API_KEY = "530800072D39492E981670EDB6F83617"
OCTOPRINT_URL = "http://127.0.0.1:5000"
GCODE_WITH_PRIME_LINE = "MT_prime_line.gcode"
GCODE_NO_PRIME_LINE = "MT_no_prime_line.gcode"
PRINTER_BED_TEMP_THRESHOLD = 40

class AppConfig:
    def __init__(self, app_config_json, rtde_config_xml):

        config_data_from_json = json.load(open(app_config_json))
        print_to_stderr("App Configuration from json: \n{0}".format(str(config_data_from_json)))

        self.cobot_ip_address = config_data_from_json.get('cobot_ip_address', ROBOT_HOST )
        self.rtde_config_file = rtde_config_xml
        self.max_print_jobs = config_data_from_json.get('max_jobs', 1)
        self.octoprint_api_key = config_data_from_json.get('octoprint_api_key', OCTOPRINT_API_KEY)
        self.octoprint_url = config_data_from_json.get('octoprint_url', OCTOPRINT_URL)
        self.printer_bed_pick_temp = config_data_from_json.get('printer_bed_pick_temp', PRINTER_BED_TEMP_THRESHOLD)
        self.gcode_with_prime_line = config_data_from_json.get('gcode_filename', GCODE_WITH_PRIME_LINE)
        self.gcode_no_prime_line = config_data_from_json.get('gcode_no_prime_filename', GCODE_NO_PRIME_LINE)


def print_to_stderr(message):
    sys.stderr.write(message)
    sys.stderr.write('\n')
    sys.stderr.flush()
    time.sleep(0.5)


def print_to_stdout(message):
    sys.stdout.write(message)
    sys.stdout.write('\n')
    sys.stdout.flush()
    time.sleep(0.5)


class GracefulKiller:
    kill_now = False

    def __init__(self, cobot_client, printer_client):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)
        self.cobot_client = cobot_client
        self.printer_client = printer_client

    def exit_gracefully(self, *args):
        self.kill_now = True
        print_to_stderr("GracefulKiller set to True")

    def exit_immediately(self, *args):
        self.kill_now = True
        self.printer_client.printer_stop()





class CobotClient:
    COBOT_STATUS_INITIALIZED = 0
    COBOT_STATUS_IDLE = 1
    COBOT_STATUS_PICKING = 2
    COBOT_STATUS_INT_TO_TEXT = ["INITIALIZED", "IDLE", "PICKING"]

    PRINTER_STATUS_INITIALIZED = 0
    PRINTER_STATUS_IDLE = 1
    PRINTER_STATUS_PRINTING = 2
    PRINTER_STATUS_INT_TO_TEXT = ["INITIALIZED", "IDLE", "PRINTING"]

    def __init__(self, app_config):

        print_to_stderr("Initializing Cobot Client Connection")
        conf = rtde_config.ConfigFile(app_config.rtde_config_file)
        state_names, state_types = conf.get_recipe("state")
        watchdog_names, watchdog_types = conf.get_recipe("watchdog")
        self.state = None

        try:
            self.con = rtde.RTDE(app_config.cobot_ip_address, ROBOT_PORT)
            self.con.connect()

            # log controller version
            print_to_stderr("UR Controller Version: {}".format(self.con.get_controller_version()))

            # setup recipes
            self.con.send_output_setup(state_names, state_types)
            self.watchdog = self.con.send_input_setup(watchdog_names, watchdog_types)

            # The function "rtde_set_watchdog" in the "rtde_control_loop.urp" creates a 1 Hz watchdog
            self.update_printer_status_register(CobotClient.PRINTER_STATUS_INITIALIZED)

        except rtde.RTDEException as err:
            print_to_stderr("Error initializing rtde connection with cobot: {}".format(err))
            raise

    def start_data_synchronization(self):
        if not self.con.send_start():
            # TBD: change to exception
            sys.exit()

    def get_cobot_status(self):
        self.state = self.con.receive()
        if self.state is None:
            # TBD fix this
            sys.exit()
        CobotStatus = namedtuple('CobotStatus', ['int', 'txt'])
        return CobotStatus(int=self.state.output_int_register_0,
                           txt=self.COBOT_STATUS_INT_TO_TEXT[self.state.output_int_register_0])

    def update_printer_status_register(self, value):
        self.watchdog.input_int_register_0 = value
        # note: we rely on watchdog kicker thread to send this to cobot

    def send_printer_status(self):
        self.con.send(self.watchdog)


def kick_cobot_watchdog(sleep_time, cobot_client, stop_thread_event, run_with_gui):
    # block for a moment
    while not stop_thread_event.is_set():
        try:
            cobot_client.state = cobot_client.con.receive()
            cobot_client.send_printer_status()
            if run_with_gui:
                print_to_stdout("current_time={0}".format(int(time.time())))
        except BrokenPipeError:
            print_to_stderr("broken pipe in kicker")
            cobot_client.con.disconnect()
            cobot_client.con.connect()
            cobot_client.start_data_synchronization()
        time.sleep(sleep_time)
        # display a message
    print_to_stderr('Cobot watchdog thread stopped')


class PrinterClient:
    PRINTER_POLL_INTERVAL = 1

    def __init__(self, app_config):
        print_to_stderr("Initializing OctoPrint Client Connection")

        try:
            self.con = OctoRest(url=app_config.octoprint_url, apikey=app_config.octoprint_api_key)
            self.con.connect()
            print_to_stderr("Octoprint Version: {0}".format(self.get_server_version()))
        except Exception as e:
            print_to_stderr(e)

    def get_server_version(self):
        message = "You are using OctoPrint v" + self.con.version['server'] + "\n"
        return message

    def get_printer_info(self):
        try:
            message = ""
            message += str(self.con.version) + "\n"
            message += str(self.con.job_info()) + "\n"
            printing = self.con.printer()['state']['flags']['printing']
            if printing:
                message += "Currently printing!\n"
            else:
                message += "Not currently printing...\n"
            return message
        except Exception as e:
            print_to_stderr(e)

    def printer_cmd_wait(self, state):
        while self.con.state() == state:
            time.sleep(self.PRINTER_POLL_INTERVAL)

    def printer_cmd_wait_until(self, state):
        while self.con.state() != state:
            time.sleep(self.PRINTER_POLL_INTERVAL)

    def printer_bed_temp_wait_until(self, threshold):
        while self.con.printer()['temperature']['bed']['actual'] > threshold:
            time.sleep(self.PRINTER_POLL_INTERVAL)

    def printer_stop(self):
        self.con.cancel()


class ControlLoop:

    def __init__(self, app_config):
        self.app_config = app_config

    def launch(self, run_with_gui):

        # need to set up logging to stdout and stderr

        print_to_stderr("initializing mt control loop")
        # make client to talk to Cobot
        cobot_client = CobotClient(self.app_config)

        # make client to communicate with OctoPrint Server
        printer_client = PrinterClient(self.app_config)

        # create signal handler
        killer = GracefulKiller(cobot_client, printer_client)

        # create cobot watchdog kicker thread
        stop_thread_event = threading.Event()
        kicker_thread = threading.Thread(target=kick_cobot_watchdog,
                                         args=(0.5, cobot_client, stop_thread_event, run_with_gui))

        # start data synchronization
        print_to_stderr("Start data synchronization with UR Cobot")
        cobot_client.start_data_synchronization()
        kicker_thread.start()

        # Verify that the two print files (defined in the constant variables GCODE_WITH_PRIME_LINE and
        # GCODE_WITHOUT_PRIME_LINE) have been uploaded to the Octoprint Server

        file_names = {k['name'] for k in printer_client.con.files('local')['files']}
        if (self.app_config.gcode_with_prime_line in file_names) and (self.app_config.gcode_no_prime_line in file_names):
            print_to_stderr("verified gcode files uploaded to Octoprint Server")
        else:
            print_to_stderr("gcode files missing from Octoprint Server")
            exit()

        if printer_client.con.state() == 'Operational':

            print_job_count = 0
            print_to_stderr("start machine tending control loop")
            if run_with_gui:
                print_to_stdout("start_time={0}".format(int(time.time())))

            while not killer.kill_now:

                if print_job_count == 0:
                    if run_with_gui:
                        print_to_stdout("print_job_count={0}".format(print_job_count))
                    # select print job for first pass
                    printer_client.con.select(GCODE_WITH_PRIME_LINE, print=False)
                    time.sleep(1)
                    selected_filename = printer_client.con.job_info()['job']['file']['name']
                    assert selected_filename == GCODE_WITH_PRIME_LINE

                print_to_stderr('start new print job')

                cobot_client.update_printer_status_register(CobotClient.PRINTER_STATUS_PRINTING)

                printer_client.con.start()
                time.sleep(5)
                assert printer_client.con.state() == "Printing"
                printer_client.printer_cmd_wait('Printing')
                print_to_stderr("print job complete")
                print_to_stderr('waiting for bed to cool...')
                printer_client.printer_bed_temp_wait_until(self.app_config.printer_bed_pick_temp)
                printer_client.printer_cmd_wait_until('Operational')

                if print_job_count == 0:
                    # select print job for subsequent passes
                    printer_client.con.select(GCODE_NO_PRIME_LINE, print=False)
                    time.sleep(1)
                    selected_filename = printer_client.con.job_info()['job']['file']['name']
                    assert selected_filename == GCODE_NO_PRIME_LINE

                cobot_status = cobot_client.get_cobot_status()
                assert cobot_status.int != CobotClient.COBOT_STATUS_PICKING
                cobot_client.update_printer_status_register(CobotClient.PRINTER_STATUS_IDLE)
                while cobot_client.get_cobot_status().int != CobotClient.COBOT_STATUS_PICKING:
                    time.sleep(1)

                # verify cobot status is picking
                cobot_status = cobot_client.get_cobot_status()
                assert cobot_status.int == CobotClient.COBOT_STATUS_PICKING
                print_to_stderr("robot arm removing item from printer bed...")

                while cobot_client.get_cobot_status().int == CobotClient.COBOT_STATUS_PICKING:
                    time.sleep(1)

                # verify cobot status is idle

                cobot_status = cobot_client.get_cobot_status()
                assert cobot_status.int == CobotClient.COBOT_STATUS_IDLE
                print_to_stderr("item removed from printer bed")

                print_job_count += 1
                if run_with_gui:
                    print_to_stdout("print_job_count={0}".format(print_job_count))

                if print_job_count == self.app_config.max_print_jobs:
                    break

        else:

            print_to_stderr("Printer busy, cannot start control loop")

        stop_thread_event.set()


def main():
    args = sys.argv[1:]
    app_config = AppConfig(args[0], args[1])
    control_loop = ControlLoop(app_config)
    control_loop.launch(args[2] == 'True')


if __name__ == "__main__":
    main()
