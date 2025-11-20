import telegram
import asyncio

import os
import utils
from utils import get_env_variable


async def send_telegram_message(message_text, parse_mode):
    logger = utils.getLogger()
    BOT_TOKEN = get_env_variable("BOT_TOKEN")
    CHAT_ID = get_env_variable("CHAT_ID")

    bot = telegram.Bot(token=BOT_TOKEN)
    try:
        if parse_mode == 'HTML' or parse_mode == 'MarkdownV2':
            await bot.sendMessage(chat_id=CHAT_ID, text=message_text, parse_mode=parse_mode)
        else:
            await bot.sendMessage(chat_id=CHAT_ID, text=message_text)

        logger.info(f"Message sent successfully to chat ID {CHAT_ID}")
    except Exception as e:
        logger.info(f"Error sending message: {e}")


async def main():
    message_to_send = "Hi from Python Code"

    await send_telegram_message(message_to_send, None)


if __name__ == "__main__":
    os.environ['BOT_TOKEN'] = "80xxx"
    os.environ['CHAT_ID'] = "84xxx"
    
    asyncio.run(main())