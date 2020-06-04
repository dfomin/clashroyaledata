from telegram.ext import Updater, CommandHandler

from private import token


class TelegramManager:
    def __init__(self):
        self.updater = Updater(token, use_context=True)
        self.updater.start_webhook(listen='127.0.0.1', port=5002, url_path=token)
        self.updater.bot.set_webhook(url=f"https://dfomin.com:443/{token}")

        start_handler = CommandHandler("start", self.start)
        self.updater.dispatcher.add_handler(start_handler)

    def start(self, update, context):
        context.bot.send_message(chat_id=update.effective_user.id, text="OK")

    def message(self, text):
        self.updater.bot.send_message(chat_id="@CRClanRussia", text=text)
