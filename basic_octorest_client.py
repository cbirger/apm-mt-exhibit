import signal

from octorest import OctoRest
import time

OCTOPRINT_API_KEY = "530800072D39492E981670EDB6F83617"
OCTOPRINT_URL = "http://127.0.0.1:5000"
GCODE_FILENAME = "Test_PLA_MK4_5m.gcode"
PRINTER_BED_TEMP_THRESHOLD = 25


def sleep(seconds):
    """
    If recording, sleep for a given amount of seconds
    """
    # if 'RECORD' in os.environ:
    time.sleep(seconds)


class GracefulKiller:
    kill_now = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, *args):
        self.kill_now = True
        print("GracefulKiller set to True")


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
            sleep(self.PRINTER_POLL_INTERVAL)

    def printer_cmd_wait_until(self, state):
        while self.con.state() != state:
            sleep(self.PRINTER_POLL_INTERVAL)

    def printer_bed_temp_wait_until(self, threshold):
        print('waiting for bed to cool...')
        while self.con.printer()['temperature']['bed']['actual'] > threshold:
            sleep(self.PRINTER_POLL_INTERVAL)


def main():
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

        sleep(5)
        print("item removed from printer bed")


if __name__ == "__main__":
    main()
