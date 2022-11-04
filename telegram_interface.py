from aiogram import Bot, Dispatcher, executor, types


class TelegramUI:

    USERS = [182023875]
    API = dict()

    def __init__(self, ui_token, devices):
        self.device_global = devices['global']
        self.device_boiler = devices['boiler']
        self.bot = Bot(token=ui_token)
        self.dp = Dispatcher(self.bot)
        self.register_handlers(self.bot, self.dp)
        executor.start_polling(self.dp, skip_updates=True, relax=1)

    def register_handlers(self, bot, dp):
        users = self.USERS

        @dp.message_handler(lambda message: message.chat.id not in users)
        async def unregistered_user(message):
            await bot.send_message(message.chat.id, "Access denied")

        # Boiler
        @dp.message_handler(commands=['boiler'])
        async def cmd_handler(message: types.Message):
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            key_on = types.InlineKeyboardButton(text='Turn on', callback_data='boiler_on')
            key_off = types.InlineKeyboardButton(text='Turn off', callback_data='boiler_off')
            keyboard.add(key_on, key_off)
            await bot.send_message(message.from_user.id,
                                   text='Boiler power status: ' + str(self.device_boiler.power),
                                   reply_markup=keyboard)

        @dp.callback_query_handler(lambda c: c.data and c.data.startswith('boiler'))
        async def process_callback_boiler(callback_query: types.CallbackQuery):
            data = callback_query.data
            if data == "boiler_on":
                rsp = self.device_boiler.power_on()
                await bot.send_message(callback_query.from_user.id, f'Boiler power on: {rsp}')
            elif data == "boiler_off":
                rsp = self.device_boiler.power_off()
                await bot.send_message(callback_query.from_user.id, f'Boiler power off: {rsp}')

        # Global
        @dp.message_handler(commands=['global'])
        async def cmd_handler(message: types.Message):
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            key_on = types.InlineKeyboardButton(text='night light', callback_data='global_night_light')
            key_off = types.InlineKeyboardButton(text='day light', callback_data='global_day_light')
            keyboard.add(key_on, key_off)
            await bot.send_message(message.from_user.id, text='Global functions', reply_markup=keyboard)

        @dp.callback_query_handler(lambda c: c.data and c.data.startswith('global'))
        async def process_callback_boiler(callback_query: types.CallbackQuery):
            data = callback_query.data
            if data == "global_night_light":
                rsp = self.device_global.night_light()
                await bot.send_message(callback_query.from_user.id, f'Night light mode: {rsp}')
            elif data == "global_day_light":
                rsp = self.device_global.day_light()
                await bot.send_message(callback_query.from_user.id, f'Day light mode: {rsp}')




if __name__ == '__main__':

    pass
