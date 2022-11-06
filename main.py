import json
import os

from telegram_interface import TelegramUI
import periphery


if __name__ == '__main__':

    with open(os.environ['SmartHome secrets']) as f:
        secrets = json.load(f)

    hw_interface = periphery.HWInterface()
    device_global = periphery.DeviceGlobal(hw_interface)
    boiler = periphery.Boiler(hw_interface)
    fito_lamp = periphery.FitoLamp(hw_interface, '1')

    devices = {
        'global':       device_global,
        'boiler':       boiler,
        'fito_lamp':    fito_lamp
    }

    ti = TelegramUI(secrets['SmartHome bot token'], devices)
