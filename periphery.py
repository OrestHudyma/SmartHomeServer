import serial
from serial.tools import list_ports
import time
import nmea


class Device:
    def __init__(self, interface):
        self.interface = interface


class DeviceGlobal(Device):
    def __init__(self, interface):
        super().__init__(interface)

    def night_light(self):
        sentence = nmea.compose('SHGLB', 'NIGHT')
        rsp = self.interface.transmit_fm433(sentence)
        print('Global night light: ' + rsp)
        return rsp

    def day_light(self):
        sentence = nmea.compose('SHGLB', 'DAY')
        rsp = self.interface.transmit_fm433(sentence)
        print('Global day light: ' + rsp)
        return rsp


class Boiler(Device):
    DEADLINE_DELAY = 36000

    def __init__(self, interface):
        self.power = True
        super().__init__(interface)

    def power_off(self):
        self.power = False
        sentence = nmea.compose('SHBCC', 'OFF')
        rsp = self.interface.transmit_fm433(sentence)
        print('Boiler power off: ' + rsp)
        return rsp

    def power_on(self):
        self.power = True
        sentence = nmea.compose('SHBCC', 'ON')
        rsp = self.interface.transmit_fm433(sentence)
        print('Boiler power on: ' + rsp)
        return rsp

    def refresh(self):
        if self.power:
            self.power_on()
        else:
            self.power_off()


class FitoLamp(Device):
    def __init__(self, interface, device_id):
        self.power = True
        self.device_id = device_id
        super().__init__(interface)

    def power_off(self):
        self.power = False
        sentence = nmea.compose('SHFTL', 'OFF', [self.device_id])
        rsp = self.interface.transmit_fm433(sentence)
        print('Fito lamp power off: ' + rsp)
        return rsp

    def power_on(self):
        self.power = True
        sentence = nmea.compose('SHFTL', 'ON', [self.device_id])
        rsp = self.interface.transmit_fm433(sentence)
        print('Fito lamp power on: ' + rsp)
        return rsp

    def power_off_fast(self):
        self.power = False
        sentence = nmea.compose('SHFTL', 'FOFF', [self.device_id])
        rsp = self.interface.transmit_fm433(sentence)
        print('Fito lamp power off: ' + rsp)
        return rsp

    def power_on_fast(self):
        self.power = True
        sentence = nmea.compose('SHFTL', 'FON', [self.device_id])
        rsp = self.interface.transmit_fm433(sentence)
        print('Fito lamp power on: ' + rsp)
        return rsp

    def refresh(self):
        if self.power:
            self.power_on()
        else:
            self.power_off()


class HWInterface:

    FM433_REPEAT_COUNT = 3
    FM433_REPEAT_DELAY = 0.1
    BOUDRATE = 9600
    TIMEOUT = 1
    com_port = None

    def __init__(self):
        ports = list_ports.comports()
        print('Available ports:')
        for port, desc, hwid in sorted(ports):
            print("{}: {} [{}]".format(port, desc, hwid))
        for port, _, _ in sorted(ports):
            print('Check port ' + port)
            try:
                com_port = serial.Serial(port, baudrate=self.BOUDRATE, timeout=self.TIMEOUT)
            except (OSError, serial.SerialException) as err:
                print(err)
            else:
                if self.test(com_port):
                    print('Hardware connection established with port ' + port)
                    self.com_port = com_port
        if self.com_port is None:
            print('Error connecting to hardware')

    def test(self, com_port=None):
        if com_port is None:
            com_port = self.com_port
        com_port.write((nmea.add_checksum('$SHHWI,test,') + '\n').encode())
        rsp = com_port.readline().decode().strip('\n')
        print('Response to test command: ' + rsp)
        return 'ok' in rsp

    def transmit_fm433(self, data):
        rsp = ''
        for _ in range(self.FM433_REPEAT_COUNT):
            self.com_port.write(data.encode())
            rsp = self.com_port.readline().decode().strip('\n')
            if rsp != 'ok':
                print(f'FM433 transmission error (response {rsp})')
                return rsp
            time.sleep(self.FM433_REPEAT_DELAY)
        return rsp
