import unittest
from unittest.mock import MagicMock, call, patch

import nmea
import periphery


class NmeaTests(unittest.TestCase):
    def test_checksum_matches_known_nmea_sentence(self):
        sentence = (
            '$GPGGA,123519,4807.038,N,01131.000,E,1,08,'
            '0.9,545.4,M,46.9,M,,*47'
        )

        self.assertEqual(nmea.checksum(sentence), '47')

    def test_add_checksum_appends_separator_and_checksum(self):
        sentence = '$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,'

        self.assertEqual(nmea.add_checksum(sentence), sentence + '*47')

    def test_compose_formats_parameters_and_line_ending(self):
        sentence = nmea.compose('SHFTL', 'ON', ['1'])

        self.assertEqual(sentence, nmea.add_checksum('$SHFTL,ON,1,') + '\n')


class BoilerTests(unittest.TestCase):
    def setUp(self):
        self.interface = MagicMock()
        self.interface.transmit_fm433.return_value = 'ok'
        self.boiler = periphery.Boiler(self.interface)

    def test_power_off_updates_state_and_sends_command(self):
        response = self.boiler.power_off()

        self.assertFalse(self.boiler.power)
        self.assertEqual(response, 'ok')
        self.interface.transmit_fm433.assert_called_once_with(
            nmea.compose('SHBCC', 'OFF')
        )

    def test_power_on_sends_command_when_enabled(self):
        self.boiler.power = False

        response = self.boiler.power_on()

        self.assertTrue(self.boiler.power)
        self.assertEqual(response, 'ok')
        self.interface.transmit_fm433.assert_called_once_with(
            nmea.compose('SHBCC', 'ON')
        )

    def test_power_on_does_not_send_command_when_disabled(self):
        self.boiler.power = False
        self.boiler.enabled = False

        response = self.boiler.power_on()

        self.assertFalse(self.boiler.power)
        self.assertEqual(response, 'Cannot complete. Boiler disabled.')
        self.interface.transmit_fm433.assert_not_called()


class FitoLampTests(unittest.TestCase):
    def test_fast_power_commands_include_device_id(self):
        interface = MagicMock()
        interface.transmit_fm433.return_value = 'ok'
        lamp = periphery.FitoLamp(interface, '7')

        lamp.power_off_fast()
        lamp.power_on_fast()

        self.assertTrue(lamp.power)
        self.assertEqual(
            interface.transmit_fm433.call_args_list,
            [
                call(nmea.compose('SHFTL', 'FOFF', ['7'])),
                call(nmea.compose('SHFTL', 'FON', ['7'])),
            ],
        )


class HWInterfaceTests(unittest.TestCase):
    def setUp(self):
        self.previous_class_port = periphery.HWInterface.com_port
        periphery.HWInterface.com_port = None

    def tearDown(self):
        periphery.HWInterface.com_port = self.previous_class_port

    @patch.object(periphery.HWInterface, 'test', side_effect=[False, True])
    @patch('periphery.serial.Serial')
    @patch('periphery.list_ports.comports')
    def test_selects_matching_port_and_closes_rejected_port(
        self,
        comports,
        serial_port,
        test_port,
    ):
        comports.return_value = [
            ('COM1', 'First port', 'HWID1'),
            ('COM2', 'Second port', 'HWID2'),
        ]
        rejected_port = MagicMock()
        matching_port = MagicMock()
        serial_port.side_effect = [rejected_port, matching_port]

        interface = periphery.HWInterface()

        self.assertIs(interface.com_port, matching_port)
        rejected_port.close.assert_called_once_with()
        matching_port.close.assert_not_called()
        self.assertEqual(test_port.call_count, 2)

    @patch.object(periphery.HWInterface, 'test', return_value=True)
    @patch('periphery.serial.Serial')
    @patch('periphery.list_ports.comports')
    def test_continues_after_port_open_error(
        self,
        comports,
        serial_port,
        test_port,
    ):
        comports.return_value = [
            ('COM1', 'Busy port', 'HWID1'),
            ('COM2', 'Matching port', 'HWID2'),
        ]
        matching_port = MagicMock()
        serial_port.side_effect = [
            periphery.serial.SerialException('Port is busy'),
            matching_port,
        ]

        interface = periphery.HWInterface()

        self.assertIs(interface.com_port, matching_port)
        test_port.assert_called_once_with(matching_port)
        matching_port.close.assert_not_called()

    @patch.object(periphery.HWInterface, 'test', return_value=False)
    @patch('periphery.serial.Serial')
    @patch('periphery.list_ports.comports')
    def test_closes_port_when_no_hardware_matches(
        self,
        comports,
        serial_port,
        _test_port,
    ):
        comports.return_value = [('COM1', 'Other device', 'HWID1')]
        rejected_port = MagicMock()
        serial_port.return_value = rejected_port

        interface = periphery.HWInterface()

        self.assertIsNone(interface.com_port)
        rejected_port.close.assert_called_once_with()

    def test_accepts_ok_response_with_crlf(self):
        interface = periphery.HWInterface.__new__(periphery.HWInterface)
        serial_port = MagicMock()
        serial_port.readline.return_value = b'ok\r\n'

        result = interface.test(serial_port)

        self.assertTrue(result)
        serial_port.write.assert_called_once_with(
            (nmea.add_checksum('$SHHWI,test,') + '\n').encode()
        )

    def test_rejects_response_that_only_contains_ok(self):
        interface = periphery.HWInterface.__new__(periphery.HWInterface)
        serial_port = MagicMock()
        serial_port.readline.return_value = b'not ok\r\n'

        self.assertFalse(interface.test(serial_port))

    @patch('periphery.time.sleep')
    def test_transmit_repeats_successful_command(self, sleep):
        interface = periphery.HWInterface.__new__(periphery.HWInterface)
        interface.com_port = MagicMock()
        interface.com_port.readline.side_effect = [b'ok\r\n'] * 3

        response = interface.transmit_fm433('payload')

        self.assertEqual(response, 'ok')
        self.assertEqual(
            interface.com_port.write.call_args_list,
            [call(b'payload')] * interface.FM433_REPEAT_COUNT,
        )
        self.assertEqual(sleep.call_count, interface.FM433_REPEAT_COUNT)

    @patch('periphery.time.sleep')
    def test_transmit_stops_on_first_error(self, sleep):
        interface = periphery.HWInterface.__new__(periphery.HWInterface)
        interface.com_port = MagicMock()
        interface.com_port.readline.side_effect = [b'ok\r\n', b'error\r\n']

        response = interface.transmit_fm433('payload')

        self.assertEqual(response, 'error')
        self.assertEqual(interface.com_port.write.call_count, 2)
        sleep.assert_called_once_with(interface.FM433_REPEAT_DELAY)


if __name__ == '__main__':
    unittest.main()
