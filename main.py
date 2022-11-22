import json
import os
import asyncio
import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from telegram_interface import TelegramUI
import periphery

DEVICE_REFRESH_INTERVAL = 1


if __name__ == '__main__':

    with open(os.environ['SmartHome_secrets']) as f:
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

    # Refresh schedule
    refresh_api = [
        boiler.refresh
    ]

    def refresh_job(api):
        for func in api:
            func()
            time.sleep(1)

    refresher = AsyncIOScheduler()
    refresher.add_job(refresh_job, 'interval', args=refresh_api, hours=DEVICE_REFRESH_INTERVAL)
    refresher.start()

    # Main schedule
    schedule = AsyncIOScheduler()
    schedule.add_job(boiler.power_on, 'cron', hour=5)
    schedule.add_job(boiler.power_off, 'cron', hour=23)
    print(schedule.print_jobs())
    schedule.start()

    ti = TelegramUI(secrets['SmartHome bot token'], devices)

    try:
        while True:
            asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        refresher.shutdown()
