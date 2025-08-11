from flask import Flask, request
import telegram
import asyncio
import firebase_admin
from firebase_admin import db

app = Flask(__name__)

# Initialize Firebase
cred = firebase_admin.credentials.Certificate('firebasekey.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://botify-409-default-rtdb.firebaseio.com/'  # Replace with your URL
})
ref = db.reference('bots')

async def handle_telegram_update(update):
    if update.message and update.message.text == '/start':
        # No hardcoded data; rely on existing Firebase data
        bots = ref.get()
        if not bots:
            await update.message.reply_text("No bot data available yet. Please add data to Firebase.")
        else:
            await update.message.reply_text("Hi there! Tell me what kind of Telegram bot you need (e.g., 'Find a translation bot').")
    elif update.message and update.message.text.lower().startswith('find a '):
        query = update.message.text.lower().replace('find a ', '').strip()
        bots = ref.get()
        if bots:
            for bot in bots:
                if bot.get('category') and bot['category'].lower() == query:
                    response = f"Bot found!\nName: {bot['name']}\nDescription: {bot['description']}\nLink: {bot['link']}\nRating: {bot['rating']}\nTips: {bot['tips']}"
                    await update.message.reply_text(response)
                    break
            else:
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

if __name__ == "__main__":
    with open('telegram_token.txt', 'r') as file:
        token = file.read().strip()
    global bot
    bot = telegram.Bot(token=token)
    app.run(host='0.0.0.0', port=7860)