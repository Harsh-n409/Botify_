from flask import Flask, request
import telegram
import asyncio
import firebase_admin
from firebase_admin import db
from transformers import pipeline  # For AI NLP

app = Flask(__name__)

# Initialize Firebase (local file path)
cred = firebase_admin.credentials.Certificate('firebasekey.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://botify-409-default-rtdb.firebaseio.com/'  # Verify URL
})
ref = db.reference('bots')

# Initialize AI model (e.g., for intent recognition)
classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

async def handle_telegram_update(update):
    if update.message and update.message.text == '/start':
        bots = ref.get()
        if not bots:
            await update.message.reply_text("No bot data available yet.")
        else:
            await update.message.reply_text("Hi there! Tell me what kind of Telegram bot you need (e.g., 'find translation').")

    elif update.message and update.message.text.lower().startswith('find '):
        query = update.message.text.lower().replace('find ', '').strip()
        # Use AI to classify intent
        candidate_labels = ["translation", "weather", "news", "games", "music", "education", "shopping", "social", "health"]
        result = classifier(query, candidate_labels)
        best_category = result['labels'][0]  # Most likely category

        bots = ref.get()
        if bots:
            if isinstance(bots, dict):
                bot_list = bots.values()
            elif isinstance(bots, list):
                bot_list = bots
            else:
                bot_list = []
            for bot in bot_list:
                if bot.get('category') and best_category.lower() in bot['category'].lower():
                    await update.message.reply_text(f"Bot found!\nName: {bot['name']}\nDescription: {bot['description']}\nLink: {bot['link']}\nRating: {bot['rating']}\nTips: {bot['tips']}")
                    break
            else:
                await update.message.reply_text("Sorry, no bot found for that intent.")
        else:
            await update.message.reply_text("No bot data available yet.")
    return "OK"

@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    data = request.get_json(force=True)

    # Case 1: Real Telegram Webhook
    if "update_id" in data:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        update = telegram.Update.de_json(data, bot)
        return loop.run_until_complete(handle_telegram_update(update))

    # Case 2: Flutter direct request
    elif "message" in data and "text" in data["message"]:
        text = data["message"]["text"]

        if text.lower().startswith("find "):
            query = text.lower().replace("find ", "").strip()
            candidate_labels = ["translation", "weather", "news", "games", "music", "education", "shopping", "social", "health"]
            result = classifier(query, candidate_labels)
            best_category = result['labels'][0]

            bots = ref.get()
            if bots:
                bot_list = bots.values() if isinstance(bots, dict) else bots
                for bot_info in bot_list:
                    if bot_info.get('category') and best_category.lower() in bot_info['category'].lower():
                        return {
                            "reply": f"Bot found!\nName: {bot_info['name']}\nDescription: {bot_info['description']}\nLink: {bot_info['link']}\nRating: {bot_info['rating']}\nTips: {bot_info['tips']}"
                        }
                return {"reply": "Sorry, no bot found for that intent."}
            else:
                return {"reply": "No bot data available yet."}

        elif text == "/start":
            return {"reply": "Hi there! Tell me what kind of Telegram bot you need (e.g., 'find translation')."}

        else:
            return {"reply": "Command not recognized."}

    # Case 3: Invalid request
    else:
        return {"error": "Invalid request format"}, 400


@app.route("/", methods=["GET"])
def home():
    return "Telegram Bot API with AI is running locally!"

if __name__ == "__main__":
    with open('telegram_token.txt', 'r') as file:
        token = file.read().strip()
    global bot
    bot = telegram.Bot(token=token)
    app.run(host='0.0.0.0', port=7860)