import serial
from serial.tools.list_ports import comports
import time
import nmea


class Device:
    def __init__(self, interface):
        self.interface = interface


class Boiler(Device):

    def __init__(self, interface):
        self.power = True
        super().__init__(interface)

    def power_off(self):
        self.power = False
        sentence = nmea.add_checksum('$SHBCC,OFF,') + '\n'
        rsp = self.interface.transmit_fm433(sentence)
        print('Boiler power off: ' + rsp)
        return rsp

    def power_on(self):
        self.power = True
        sentence = nmea.add_checksum('$SHBCC,ON,') + '\n'
        rsp = self.interface.transmit_fm433(sentence)
        print('Boiler power on: ' + rsp)
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
        ports = comports()
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
