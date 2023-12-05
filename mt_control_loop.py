import signal
import time
import sys
import threading
import rtde.rtde as rtde
import rtde.rtde_config as rtde_config
from octorest import OctoRest


class GracefulKiller:
    kill_now = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, *args):
        self.kill_now = True
        print("GracefulKiller set to True")


# Parameters for RTDE (Cobot) Client
ROBOT_HOST = "192.168.0.14"
ROBOT_PORT = 30004
ROBOT_CONFIG_FILENAME = "control_loop_configuration.xml"

# Parameters for OctoRest (Printer) Client
OCTOPRINT_API_KEY = "530800072D39492E981670EDB6F83617"
OCTOPRINT_URL = "http://127.0.0.1:5000"
GCODE_FILENAME = "Test_PLA_MK4_5m.gcode"
PRINTER_BED_TEMP_THRESHOLD = 25

PRINTER_STATUS_INITIALIZED = 0
PRINTER_STATUS_IDLE = 1
PRINTER_STATUS_PRINTING = 2

COBOT_STATUS_INITIALIZED = 0
COBOT_STATUS_IDLE = 1
COBOT_STATUS_PICKING = 2


class CobotClient:

    def __init__(self):
        conf = rtde_config.ConfigFile(ROBOT_CONFIG_FILENAME)
        state_names, state_types = conf.get_recipe("state")
        watchdog_names, watchdog_types = conf.get_recipe("watchdog")
        self.state = None

        try:
            self.con = rtde.RTDE(ROBOT_HOST, ROBOT_PORT)
            self.con.connect()

            # log controller version
            print("Controller Version: {}".format(self.con.get_controller_version()))

            # setup recipes
            self.con.send_output_setup(state_names, state_types)
            self.watchdog = self.con.send_input_setup(watchdog_names, watchdog_types)

            # The function "rtde_set_watchdog" in the "rtde_control_loop.urp" creates a 1 Hz watchdog
            self.update_printer_status_register(PRINTER_STATUS_INITIALIZED)

        except rtde.RTDEException as err:
            print("Error initializing rtde connection with cobot: {}".format(err))
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
        return self.state.output_int_register_0

    def update_printer_status_register(self, value):
        self.watchdog.input_int_register_0 = value
        # note: we rely on watchdog kicker thread to send this to cobot

    def send_printer_status(self):
        self.con.send(self.watchdog)


def kick_cobot_watchdog(sleep_time, cobot_client, stop_thread_event):
    # block for a moment
    while not stop_thread_event.is_set():
        try:
            cobot_client.state = cobot_client.con.receive()
            cobot_client.send_printer_status()
        except BrokenPipeError:
            print("broken pipe in kicker")
            cobot_client.con.disconnect()
            cobot_client.con.connect()
            cobot_client.start_data_synchronization()
        time.sleep(sleep_time)
        # display a message
    print('kicker thread stopped')


class PrinterClient:
    PRINTER_POLL_INTERVAL = 1

    def __init__(self):

        try:
            self.con = OctoRest(url=OCTOPRINT_URL, apikey=OCTOPRINT_API_KEY)
        except Exception as e:
            print(e)

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
            print(e)

    def printer_cmd_wait(self, state):
        while self.con.state() == state:
            time.sleep(self.PRINTER_POLL_INTERVAL)

    def printer_cmd_wait_until(self, state):
        while self.con.state() != state:
            time.sleep(self.PRINTER_POLL_INTERVAL)

    def printer_bed_temp_wait_until(self, threshold):
        print('waiting for bed to cool...')
        while self.con.printer()['temperature']['bed']['actual'] > threshold:
            time.sleep(self.PRINTER_POLL_INTERVAL)


def main():
    print("hello world")
    # make client to talk to Cobot
    cobot_client = CobotClient()

    # create signal handler
    stop_thread_event = threading.Event()
    killer = GracefulKiller()

    # create cobot watchdog kicker thread
    kicker_thread = threading.Thread(target=kick_cobot_watchdog, args=(0.5, cobot_client, stop_thread_event))

    # start data synchronization
    cobot_client.start_data_synchronization()
    kicker_thread.start()

    # ???
    while cobot_client.get_cobot_status() == COBOT_STATUS_PICKING:
        time.sleep(1)

    # make client to communicate with OctoPrint Server
    printer_client = PrinterClient()

    print(printer_client.get_server_version())

    # Verify that the print file (defined in the constant variable GCODE_FILENAME) has been
    # uploaded to the printer
    file_verified = False
    for k in printer_client.con.files()['files']:
        if k['name'] == GCODE_FILENAME:
            file_verified = True
            break
    assert file_verified

    # select file for printing
    printer_client.con.select(GCODE_FILENAME, print=False)
    time.sleep(1)
    selected_filename = printer_client.con.job_info()['job']['file']['name']
    assert selected_filename == GCODE_FILENAME
    assert printer_client.con.state() == 'Operational'

    while not killer.kill_now:

        print('start new print job')

        cobot_client.update_printer_status_register(PRINTER_STATUS_PRINTING)

        printer_client.con.start()
        time.sleep(5)
        assert printer_client.con.state() == 'Printing'
        printer_client.printer_cmd_wait('Printing')
        printer_client.printer_bed_temp_wait_until(PRINTER_BED_TEMP_THRESHOLD)
        print("print job complete, state = {}".format(printer_client.con.state()))
        printer_client.printer_cmd_wait_until('Operational')

        print("(a) Cobot Status: {}".format(cobot_client.get_cobot_status()))
        assert cobot_client.get_cobot_status() != COBOT_STATUS_PICKING
        cobot_client.update_printer_status_register(PRINTER_STATUS_IDLE)
        while cobot_client.get_cobot_status() != COBOT_STATUS_PICKING:
            time.sleep(1)

        # verify cobot status is picking
        print("(b) Cobot Status: {}".format(cobot_client.get_cobot_status()))
        assert cobot_client.get_cobot_status() == COBOT_STATUS_PICKING
        print("robot arm removing item from printer bed...")

        while cobot_client.get_cobot_status() == COBOT_STATUS_PICKING:
            time.sleep(1)

        # verify cobot status is idle

        print("(c) Cobot Status: {}".format(cobot_client.get_cobot_status()))
        assert cobot_client.get_cobot_status() == COBOT_STATUS_IDLE
        print("item removed from printer bed")

    stop_thread_event.set()


if __name__ == "__main__":
    main()
