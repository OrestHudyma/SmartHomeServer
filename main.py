import json
import os

from telegram_interface import TelegramUI
import periphery


if __name__ == '__main__':

    with open(os.environ['SmartHome secrets']) as f:
        secrets = json.load(f)

    hw_interface = periphery.HWInterface()
    boiler = periphery.Boiler(hw_interface)

    devices = {
        'boiler':       boiler
    }

    api = {'boiler_on':     boiler.power_on,
           'boiler_off':    boiler.power_off}

    ti = TelegramUI(secrets['SmartHome bot token'], devices)

    while True:
        pass
