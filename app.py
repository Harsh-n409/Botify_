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
        # Initialize bot data in Firebase
        bot_data = [
            {
                "category": "translation",
                "description": "Translates messages to other languages",
                "id": "1",
                "link": "t.me/YandexTranslate",
                "name": "@YandexTranslate",
                "rating": 4.5,
                "tips": "Say 'translate to Spanish: Hello' to translate."
            },
            {
                "category": "utilities",
                "description": "Provides various utility functions",
                "id": "2",
                "link": "t.me/UtilityBot",
                "name": "@UtilityBot",
                "rating": 4.0,
                "tips": "Use '/help' for commands."
            },
            {
                "category": "weather",
                "description": "Provides weather updates",
                "id": "3",
                "link": "t.me/WeatherBot",
                "name": "@WeatherBot",
                "rating": 4.2,
                "tips": "Type '/weather city' for updates."
            },
            {
                "category": "news",
                "description": "Delivers latest news",
                "id": "4",
                "link": "t.me/NewsBot",
                "name": "@NewsBot",
                "rating": 4.1,
                "tips": "Say '/news' to get updates."
            },
            {
                "category": "games",
                "description": "Offers fun games",
                "id": "5",
                "link": "t.me/GameBot",
                "name": "@GameBot",
                "rating": 4.3,
                "tips": "Type '/play' to start."
            },
            {
                "category": "music",
                "description": "Streams music",
                "id": "6",
                "link": "t.me/MusicBot",
                "name": "@MusicBot",
                "rating": 4.4,
                "tips": "Use '/song name' to play."
            },
            {
                "category": "education",
                "description": "Provides learning resources",
                "id": "7",
                "link": "t.me/EduBot",
                "name": "@EduBot",
                "rating": 4.0,
                "tips": "Say '/learn topic' for lessons."
            },
            {
                "category": "shopping",
                "description": "Helps with online shopping",
                "id": "8",
                "link": "t.me/ShopBot",
                "name": "@ShopBot",
                "rating": 4.1,
                "tips": "Type '/buy item' to shop."
            },
            {
                "category": "social",
                "description": "Manages social interactions",
                "id": "9",
                "link": "t.me/SocialBot",
                "name": "@SocialBot",
                "rating": 4.2,
                "tips": "Use '/connect' to link."
            },
            {
                "category": "health",
                "description": "Offers health tips",
                "id": "10",
                "link": "t.me/HealthBot",
                "name": "@HealthBot",
                "rating": 4.3,
                "tips": "Say '/health tip' for advice."
            }
        ]
        ref.set(bot_data)
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