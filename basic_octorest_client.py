from octorest import OctoRest
import time

API_KEY = "7259930C9CB345D7852C7B937F6434A8"
OCTOREST_URL = "http://localhost"

def make_client():
    try:
        client = OctoRest(url=OCTOREST_URL, apikey=API_KEY)
        return client
    except Exception as e:
        print(e)

def get_version():
    client = make_client()
    message = "You are using OctoPrint v" + client.version['server'] + "\n"
    return message

def get_printer_info():
    try:
        client = OctoRest(url=OCTOREST_URL, apikey=API_KEY)
        #client = OctoRest(url="http://octopi.local", apikey="YouShallNotPass")
        message = ""
        message += str(client.version) + "\n"
        message += str(client.job_info()) + "\n"
        printing = client.printer()['state']['flags']['printing']
        if printing:
            message += "Currently printing!\n"
        else:
            message += "Not currently printing...\n"
        return message
    except Exception as e:
        print(e)


def sleep(seconds):
    '''
    If recording, sleep for a given amount of seconds
    '''
    # if 'RECORD' in os.environ:
    time.sleep(seconds)


def cmd_wait(client, state):
    while client.state() == state:
        sleep(0.1)


def cmd_wait_until(client, state):
    while client.state() != state:
        sleep(0.1)

def main():
    #print(get_version())
    #print(get_printer_info())

    #client = make_client()
    #client.upload()

    file_to_print = None
    c = make_client()
    for k in c.files()['files']:
        file_to_print = k

    print(file_to_print['name'])
    print(file_to_print)
    c.select(file_to_print['name'], print=True)
    sleep(1)
    selected = c.job_info()['job']['file']['name']
    assert selected == file_to_print['name']
    assert c.state() == 'Printing'
    cmd_wait(c, 'Printing')
    print("print job complete, state = {}".format(c.state()))
    cmd_wait(c, 'Finishing')
    print('state = {}'.format(c.state()))
    printer = c.printer()
    print(printer['temperature'])



if __name__ == "__main__":
    main()