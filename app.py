from flask import Flask, request
import telegram
import asyncio
import firebase_admin
from firebase_admin import db

app = Flask(__name__)

# Initialize Firebase
cred = firebase_admin.credentials.Certificate('firebasekey.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://botify-409-default-rtdb.firebaseio.com/'  # Verify this URL
})
ref = db.reference('bots')

async def handle_telegram_update(update):
    if update.message and update.message.text == '/start':
        bots = ref.get()
        if not bots:
            await update.message.reply_text("No bot data available yet. Please add data to Firebase.")
        else:
            await update.message.reply_text("Hi there! Tell me what kind of Telegram bot you need (e.g., 'Find translation').")

    elif update.message and update.message.text.lower().startswith('find '):
        query = update.message.text.lower().replace('find ', '').strip()
        bots = ref.get()

        if bots:
            if isinstance(bots, dict):
                bot_list = bots.values()
            elif isinstance(bots, list):
                bot_list = bots
            else:
                bot_list = []

            found = False
            for bot in bot_list:
                if bot.get('category') and query in bot['category'].lower():
                    response = (
                        f"Bot found!\n"
                        f"Name: {bot['name']}\n"
                        f"Description: {bot['description']}\n"
                        f"Link: {bot['link']}\n"
                        f"Rating: {bot['rating']}\n"
                        f"Tips: {bot['tips']}"
                    )
                    await update.message.reply_text(response)
                    found = True
                    break

            if not found:
                await update.message.reply_text("Sorry, no bot found for that category.")
        else:
            await update.message.reply_text("No bot data available yet.")
    return "OK"

@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    update = telegram.Update.de_json(request.get_json(), bot)
    result = loop.run_until_complete(handle_telegram_update(update))
    return result

@app.route("/", methods=["GET"])
def home():
    return "Telegram Bot API is running!"

if __name__ == "__main__":
    with open('telegram_token.txt', 'r') as file:
        token = file.read().strip()
    global bot
    bot = telegram.Bot(token=token)
    app.run(host='0.0.0.0', port=7860)