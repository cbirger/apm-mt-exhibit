#!/usr/bin/env python

import sys
import time
import signal
from threading import Thread, Event
import rtde.rtde as rtde
import rtde.rtde_config as rtde_config
from octorest import OctoRest
import logging

sys.path.append("..")


# logging.basicConfig(level=logging.INFO)

class GracefulKiller:
    kill_now = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, *args):
        self.kill_now = True


# Connection Parameters for OctoRest client
OCTOPRINT_APP_KEY = "7259930C9CB345D7852C7B937F6434A8"
OCTOPRINT_URL = "http://localhost"
PRINTER_BED_TEMP_THRESHOLD = 25
GCODE_FILENAME = 'demo_0.2mm_PLA_MK3S_5m.gcode'

# Connection Parameters for RTDE client
ROBOT_HOST = "34.72.56.243"
ROBOT_PORT = 30004
ROBOT_CONFIG_FILENAME = "control_loop_configuration.xml"


class CobotClient:

    def __init__(self):
        conf = rtde_config.ConfigFile(ROBOT_CONFIG_FILENAME)
        state_names, state_types = conf.get_recipe("state")
        setp_names, setp_types = conf.get_recipe("setp")
        watchdog_names, watchdog_types = conf.get_recipe("watchdog")
        self.state = None

        try:
            self.con = rtde.RTDE(ROBOT_HOST, ROBOT_PORT)
            self.con.connect()

            # log controller version
            print("Controller Version: {}".format(self.con.get_controller_version()))

            # setup recipes
            if not self.con.send_output_setup(state_names, state_types):
                print("Controller output setup failure")
            self.setpoint = self.con.send_input_setup(setp_names, setp_types)
            self.watchdog = self.con.send_input_setup(watchdog_names, watchdog_types)

            # initialize setpoint
            self.setpoint.input_double_register_0 = 0
            self.setpoint.input_double_register_1 = 0
            self.setpoint.input_double_register_2 = 0
            self.setpoint.input_double_register_3 = 0
            self.setpoint.input_double_register_4 = 0
            self.setpoint.input_double_register_5 = 0

            # The function "rtde_set_watchdog" in the "rtde_control_loop.urp" creates a 1 Hz watchdog
            self.watchdog.input_int_register_0 = 0
        except rtde.RTDEException as err:
            print("Error initializing rtde connection with cobot: {}".format(err))
            raise

    def start_data_synchronization(self):
        print("in start_data_synchronization")
        if not self.con.send_start():
            sys.exit()

    def send_setpoint(self, setpoint_list):
        for i in range(0, 6):
            self.setpoint.__dict__["input_double_register_%i" % i] = setpoint_list[i]
        try:
            self.con.send(self.setpoint)
        except BrokenPipeError:
            print("broken pipe error")
            self.con.disconnect()
            self.con.connect()
            self.start_data_synchronization()
            self.con.send(self.setpoint)


def cobot_setpoint_to_list(sp):
    sp_list = []
    for i in range(0, 6):
        sp_list.append(sp.__dict__["input_double_register_%i" % i])
    return sp_list


"""
def cobot_list_to_setpoint(sp, sp_list):
    for i in range(0, 6):
        sp.__dict__["input_double_register_%i" % i] = sp_list[i]
    return sp
"""


class PrinterClient:

    def __init__(self):

        try:
            self.con = OctoRest(url=OCTOPRINT_URL, apikey=OCTOPRINT_APP_KEY)
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
            sleep(0.1)

    def printer_cmd_wait_until(self, state):
        while self.con.state() != state:
            sleep(0.1)

    def printer_bed_temp_wait_until(self, threshold):
        print('waiting for bed to cool...')
        while self.con.printer()['temperature']['bed']['actual'] > threshold:
            sleep(1)


def sleep(seconds):
    time.sleep(seconds)


def kick_cobot_watchdog(sleep_time, cobot_client, stop_event):
    # block for a moment
    while not stop_event.is_set():
        try:
            cobot_client.state = cobot_client.con.receive()
            cobot_client.con.send(cobot_client.watchdog)
        except BrokenPipeError:
            print("broken pipe in kicker")
            cobot_client.con.disconnect()
            cobot_client.con.connect()
            cobot_client.start_data_synchronization()
        sleep(sleep_time)
        # display a message
    print('kicker thread stopped')


def main():
    # make client to talk to Cobot
    cobot_client = CobotClient()

    # create a kicker thread
    stop_event = Event()
    kicker_thread = Thread(target=kick_cobot_watchdog, args=(0.5, cobot_client, stop_event,))

    print("start data synchronization in main")
    cobot_client.start_data_synchronization()
    kicker_thread.start()

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
    sleep(1)
    selected_filename = printer_client.con.job_info()['job']['file']['name']
    assert selected_filename == GCODE_FILENAME
    assert printer_client.con.state() == 'Operational'

    # Setpoint lists to move the robot between
    setp1_list = [-0.12, -0.43, 0.14, 0, 3.11, 0.04]
    setp2_list = [-0.12, -0.51, 0.21, 0, 3.11, 0.04]

    # Main control loop
    killer = GracefulKiller()

    while not killer.kill_now:
        print('start new print job')
        printer_client.con.start()
        sleep(5)
        assert printer_client.con.state() == 'Printing'
        printer_client.printer_cmd_wait('Printing')
        printer_client.printer_bed_temp_wait_until(PRINTER_BED_TEMP_THRESHOLD)
        print("print job complete, state = {}".format(printer_client.con.state()))
        printer_client.printer_cmd_wait_until('Operational')

        # instruct robot arm to remove newly printed object from printer bed
        print("robot arm removing item from printer bed...")

        # example code to make sure can communicate with cobot
        move_completed = True
        keep_running = True

        count = 0
        while keep_running:

            if move_completed and cobot_client.state.output_int_register_0 == 1:
                move_completed = False
                new_setp_list = setp1_list if cobot_setpoint_to_list(
                    cobot_client.setpoint) == setp2_list else setp2_list
                print("New pose = " + str(new_setp_list))
                # send new setpoint
                cobot_client.send_setpoint(new_setp_list)
                cobot_client.watchdog.input_int_register_0 = 1
            elif not move_completed and cobot_client.state.output_int_register_0 == 0:
                print("Move to confirmed pose = " + str(cobot_client.state.target_q))
                move_completed = True
                count += 1
                cobot_client.watchdog.input_int_register_0 = 0
                if count > 2:
                    break
        print("item removed from printer bed")
    stop_event.set()


if __name__ == "__main__":
    main()
