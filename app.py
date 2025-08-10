from flask import Flask, request
import telegram
import asyncio

app = Flask(__name__)

async def handle_telegram_update(update):
    if update.message and update.message.text == '/start':
        await bot.send_message(chat_id=update.message.chat_id, text="Hi there! Tell me what kind of Telegram bot you need (e.g., 'Find a translation bot').")
    return "OK"

@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    update = telegram.Update.de_json(request.get_json(), bot)
    result = loop.run_until_complete(handle_telegram_update(update))
    return result

if __name__ == "__main__":
    with open('telegram_token.txt', 'r') as file:
        token = file.read().strip()
    global bot
    bot = telegram.Bot(token=token)
    app.run(host='0.0.0.0', port=7860)