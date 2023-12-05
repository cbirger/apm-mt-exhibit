import signal
import sys
import time
import threading

import rtde.rtde as rtde
import rtde.rtde_config as rtde_config


class GracefulKiller:
    kill_now = False

    def __init__(self, stop_event):
        self.stop_event = stop_event
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, *args):
        self.kill_now = True
        self.stop_event.set()
        print("GracefulKiller set to True")


# Connection Parameters for RTDE client

ROBOT_HOST = "192.168.0.20"
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
            self.con.send_output_setup(state_names, state_types)
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
        if not self.con.send_start():
            # TBD: change to exception
            sys.exit()

    def get_current_state(self):
        self.state = self.con.receive()
        if self.state is None:
            # TBD: change to exception
            sys.exit()

    def robot_requesting_pose(self):
        return self.state.output_int_register_0 == 1

    def robot_confirming_move(self):
        return self.state.output_int_register_0 == 0

    def target_q(self):
        return self.state.target_q

    def update_setpoint(self, setp_list):
        for i in range(0, 6):
            self.setpoint.__dict__["input_double_register_%i" % i] = setp_list[i]

    def setpoint_list(self):
        sp_list = []
        for i in range(0, 6):
            sp_list.append(self.setpoint.__dict__["input_double_register_%i" % i])
        return sp_list

    def send_robot_setpoint(self):
        self.con.send(self.setpoint)

    def update_watchdog_input(self, value):
        self.watchdog.input_int_register_0 = value

    def kick_watchdog(self):
        self.con.send(self.watchdog)


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
        time.sleep(sleep_time)
        # display a message
    print('kicker thread stopped')


def main():
    # Setpoints (lists) to move the robot between
    setp1_list = [-0.12, -0.43, 0.14, 0, 3.11, 0.04]
    setp2_list = [-0.12, -0.51, 0.21, 0, 3.11, 0.04]

    SETPOINT_FRESH = 1
    SETPOINT_STALE = 0

    # make client to talk to Cobot
    cobot_client = CobotClient()

    # create a kicker thread
    stop_event = threading.Event()
    kicker_thread = threading.Thread(target=kick_cobot_watchdog, args=(0.5, cobot_client, stop_event,))

    # start data synchronization
    cobot_client.start_data_synchronization()
    kicker_thread.start()

    # Main control loop
    killer = GracefulKiller(stop_event)
    move_completed = True

    while not killer.kill_now:

        cobot_client.get_current_state()

        # do something...
        if move_completed and cobot_client.robot_requesting_pose():
            move_completed = False
            new_setp_list = setp1_list if cobot_client.setpoint_list() == setp2_list else setp2_list
            cobot_client.update_setpoint(new_setp_list)
            print("New pose = " + str(new_setp_list))
            # send new setpoint
            cobot_client.send_robot_setpoint()
            cobot_client.update_watchdog_input(SETPOINT_FRESH)
        elif not move_completed and cobot_client.robot_confirming_move():
            print("Move to confirmed pose = " + str(cobot_client.target_q))
            move_completed = True
            cobot_client.update_watchdog_input(SETPOINT_STALE)

        # kick watchdog
        cobot_client.kick_watchdog()


if __name__ == "__main__":
    main()
