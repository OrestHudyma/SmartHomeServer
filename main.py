import serial
import time
import json
import os
from telegram_interface import TelegramUI

FM433_REPEAT_COUNT = 3
FM433_REPEAT_DELAY = 0.3

s = serial.Serial('COM8')
s.baudrate = 1200


def boiler_off():
    print('Boiler off')
    for _ in range(FM433_REPEAT_COUNT):
        s.write('$SHBCC,OFF,*16\n'.encode())
        time.sleep(FM433_REPEAT_DELAY)


def boiler_on():
    print('Boiler on')
    for _ in range(FM433_REPEAT_COUNT):
        s.write('$SHBCC,ON,*58\n'.encode())
        time.sleep(FM433_REPEAT_DELAY)


api = {'boiler_on':             boiler_on,
       'boiler_off':            boiler_off}

if __name__ == '__main__':

    with open(os.environ['SmartHome secrets']) as f:
        secrets = json.load(f)

    ti = TelegramUI(api, secrets['SmartHome bot token'])

    while True:
        pass
