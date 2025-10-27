import logging
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler
from src.config import config
from src import handlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    if not config.TELEGRAM_TOKEN:
        logger.error("Set TELEGRAM_BOT_TOKEN in .env")
        return
    updater = Updater(config.TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", handlers.start))
    dp.add_handler(CommandHandler("setkey", handlers.setkey))
    dp.add_handler(CommandHandler("check", handlers.check_contract))
    dp.add_handler(CommandHandler("buy", handlers.buy_command))

    # simple callback query handler
    def callback_query(update, context):
        query = update.callback_query
        data = query.data
        if data and data.startswith("buy:"):
            token = data.split(":", 1)[1]
            query.answer(text=f"To buy, send /buy {token} <amount_native>")

    dp.add_handler(CallbackQueryHandler(callback_query))

    updater.start_polling()
    logger.info("Bot started. Polling...")
    updater.idle()

if __name__ == "__main__":
    main()