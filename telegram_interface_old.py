import telebot


class TelegramInterface:

    USERS = [182023875]
    TOKEN = '5609539827:AAFAaxW9yLc4VIL84yEkXFZmPJoJfkffu_o'

    def __init__(self):
        self.bot = telebot.TeleBot(self.TOKEN)
        self.register_handlers(self.bot)
        self.bot.polling(none_stop=True, interval=1)

    def register_handlers(self, bot):
        users = self.USERS

        @bot.message_handler(func=lambda message: message.chat.id not in users)
        def unregistered_user(message):
            bot.send_message(message.chat.id, "Access denied")

        @bot.callback_query_handler(func=lambda call: True)
        def callback_worker(call):
            if call.data == "ON":
                bot.send_message(call.message.chat.id, 'Boiler power on confirmed')
            if call.data == "OFF":
                bot.send_message(call.message.chat.id, 'Boiler power off confirmed')

        @bot.message_handler(content_types=['text'])
        def cmd_handler(message):
            if message.text == '/boiler':
                keyboard = telebot.types.InlineKeyboardMarkup()
                key_on = telebot.types.InlineKeyboardButton(text='Turn on', callback_data='ON')
                keyboard.add(key_on)
                key_off = telebot.types.InlineKeyboardButton(text='Turn off', callback_data='OFF')
                keyboard.add(key_off)
                bot.send_message(message.from_user.id, text='Set boiler power', reply_markup=keyboard)
            else:
                bot.send_message(message.from_user.id, 'Unknown cmd')


if __name__ == '__main__':

    ti = TelegramInterface()

    while True:
        pass
