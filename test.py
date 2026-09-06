from contextlib import ExitStack
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, call, patch

import nmea
import periphery
import telegram_interface


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

    def test_power_off_keeps_state_when_transmission_fails(self):
        self.interface.transmit_fm433.return_value = 'error'

        response = self.boiler.power_off()

        self.assertTrue(self.boiler.power)
        self.assertEqual(response, 'error')

    def test_power_on_sends_command_when_enabled(self):
        self.boiler.power = False

        response = self.boiler.power_on()

        self.assertTrue(self.boiler.power)
        self.assertEqual(response, 'ok')
        self.interface.transmit_fm433.assert_called_once_with(
            nmea.compose('SHBCC', 'ON')
        )

    def test_power_on_keeps_state_when_transmission_fails(self):
        self.boiler.power = False
        self.interface.transmit_fm433.return_value = 'error'

        response = self.boiler.power_on()

        self.assertFalse(self.boiler.power)
        self.assertEqual(response, 'error')

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


class HandlerRegistry:
    def __init__(self):
        self.callback_handlers = []

    def message_handler(self, *args, **kwargs):
        return lambda handler: handler

    def callback_query_handler(self, *args, **kwargs):
        def register(handler):
            self.callback_handlers.append(handler)
            return handler

        return register


class TelegramUIRunTests(unittest.TestCase):
    @patch('telegram_interface.executor.start_polling')
    def test_run_starts_polling(self, start_polling):
        ui = telegram_interface.TelegramUI.__new__(telegram_interface.TelegramUI)
        ui.dp = MagicMock()

        ui.run()

        start_polling.assert_called_once_with(
            ui.dp,
            skip_updates=True,
            relax=1,
        )


class TelegramUICallbackTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.boiler = MagicMock()
        self.ui = telegram_interface.TelegramUI.__new__(
            telegram_interface.TelegramUI
        )
        self.ui.device_global = MagicMock()
        self.ui.device_boiler = self.boiler
        self.ui.device_fito_lamp = MagicMock()
        self.bot = MagicMock()
        self.bot.send_message = AsyncMock()
        self.dispatcher = HandlerRegistry()
        self.ui.register_handlers(self.bot, self.dispatcher)
        self.boiler_callback = self.dispatcher.callback_handlers[0]

    def make_callback(self):
        callback = MagicMock()
        callback.data = 'boiler_disable'
        callback.from_user.id = 123
        return callback

    async def test_disable_reports_successful_power_off(self):
        self.boiler.power_off.return_value = 'ok'

        await self.boiler_callback(self.make_callback())

        self.assertFalse(self.boiler.enabled)
        self.boiler.power_off.assert_called_once_with()
        self.bot.send_message.assert_awaited_once_with(
            123,
            'Boiler disabled and powered off',
        )

    async def test_disable_reports_failed_power_off(self):
        self.boiler.power_off.return_value = 'error'

        await self.boiler_callback(self.make_callback())

        self.assertFalse(self.boiler.enabled)
        self.boiler.power_off.assert_called_once_with()
        self.bot.send_message.assert_awaited_once_with(
            123,
            "Boiler disabled, but power off failed: 'error'",
        )


class MainLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.hardware = MagicMock()
        self.hardware.com_port = object()
        self.global_device = MagicMock()
        self.boiler = MagicMock()
        self.fito_lamp = MagicMock()
        self.refresher = MagicMock()
        self.schedule = MagicMock()
        self.scheduler_factory = MagicMock(
            side_effect=[self.refresher, self.schedule]
        )
        self.ui = MagicMock()
        self.ui_class = MagicMock(return_value=self.ui)

    def run_main(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            secrets_path = Path(temp_dir) / 'secrets.json'
            secrets_path.write_text(
                '{"SmartHome bot token": "token"}',
                encoding='utf-8',
            )

            with ExitStack() as stack:
                stack.enter_context(
                    patch.dict(
                        os.environ,
                        {'SmartHome_secrets': str(secrets_path)},
                    )
                )
                stack.enter_context(
                    patch('periphery.HWInterface', return_value=self.hardware)
                )
                stack.enter_context(
                    patch(
                        'periphery.DeviceGlobal',
                        return_value=self.global_device,
                    )
                )
                stack.enter_context(
                    patch('periphery.Boiler', return_value=self.boiler)
                )
                stack.enter_context(
                    patch('periphery.FitoLamp', return_value=self.fito_lamp)
                )
                stack.enter_context(
                    patch(
                        'apscheduler.schedulers.asyncio.AsyncIOScheduler',
                        self.scheduler_factory,
                    )
                )
                stack.enter_context(
                    patch('telegram_interface.TelegramUI', self.ui_class)
                )
                return runpy.run_path(
                    str(Path(__file__).with_name('main.py')),
                    run_name='__main__',
                )

    def test_runs_polling_and_shuts_down_schedulers(self):
        self.run_main()

        self.ui.run.assert_called_once_with()
        self.refresher.shutdown.assert_called_once_with()
        self.schedule.shutdown.assert_called_once_with()
        self.schedule.add_job.assert_has_calls(
            [
                call(self.boiler.power_on, 'cron', hour=5),
                call(self.boiler.power_off, 'cron', hour=22),
            ]
        )

    def test_shuts_down_schedulers_when_polling_fails(self):
        self.ui.run.side_effect = RuntimeError('Polling failed')

        with self.assertRaisesRegex(RuntimeError, 'Polling failed'):
            self.run_main()

        self.refresher.shutdown.assert_called_once_with()
        self.schedule.shutdown.assert_called_once_with()

    def test_stops_before_starting_schedulers_without_hardware(self):
        self.hardware.com_port = None

        with self.assertRaises(SystemExit) as error:
            self.run_main()

        self.assertEqual(error.exception.code, 1)
        self.scheduler_factory.assert_not_called()
        self.ui_class.assert_not_called()


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
