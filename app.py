import os
import json
import requests
from flask import Flask, request, jsonify
import telegram
import asyncio
import firebase_admin
from firebase_admin import db, credentials, auth
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import logging
from dotenv import load_dotenv

# Load Environment Variables
if not os.getenv("RENDER"):
    load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
HF_API_TOKEN = os.getenv("HF_API_TOKEN")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "x-ai/grok-2")

if not OPENROUTER_API_KEY:
    raise ValueError("⚠️ Missing OPENROUTER_API_KEY")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("⚠️ Missing TELEGRAM_BOT_TOKEN")
if not HF_API_TOKEN:
    raise ValueError("⚠️ Missing HF_API_TOKEN")

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

# Firebase Initialization
try:
    cred_dict = json.loads(os.getenv('FIREBASE_CREDENTIALS'))
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://botify-409-default-rtdb.firebaseio.com/'
    })
except Exception as e:
    logging.error(f"Firebase initialization failed: {e}")
    raise

ref = db.reference('bots')
user_searches_ref = db.reference('user_searches')
favorites_ref = db.reference('user_favorites')
ratings_ref = db.reference('bot_ratings')

# Telegram Bot Initialization
bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)

# Hugging Face Inference API
HF_API_URL = "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2"
HF_HEADERS = {"Authorization": f"Bearer {HF_API_TOKEN}"}

def get_embedding(text):
    try:
        payload = {"inputs": text}
        response = requests.post(HF_API_URL, headers=HF_HEADERS, json=payload, timeout=10)
        response.raise_for_status()
        # Hugging Face API returns a list of embeddings; convert to numpy array
        embedding = np.array(response.json(), dtype=np.float32)
        return embedding
    except Exception as e:
        logging.error(f"Hugging Face API error: {e}")
        return np.zeros(384)  # Fallback: return zero vector (dimension of all-MiniLM-L6-v2)

# Verify Firebase Token
def verify_firebase_token(token):
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token['uid']
    except Exception as e:
        logging.error(f"Token verification failed: {e}")
        return None

# OpenRouter API (unchanged)
def generate_openrouter_response(query):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that recommends Telegram bots."},
            {"role": "user", "content": query}
        ]
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"⚠️ OpenRouter error: {str(e)}"

# Telegram Handler
async def handle_telegram_update(data):
    reply_text = "No matching bot found."
    query = None
    user_id = None

    # Verify Firebase token
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        user_id = verify_firebase_token(token)
    if not user_id:
        user_id = data.get('user_id', 'flutter_user')

    if 'update_id' in data and 'message' in data and 'date' in data.get('message', {}):
        update = telegram.Update.de_json(data, bot)
        if update.message and update.message.text:
            query = update.message.text.lower()
            user_id = str(update.message.chat.id)
    elif 'message' in data and 'text' in data.get('message', {}):
        query = data['message']['text'].lower()
        user_id = "flutter_user"
    else:
        return {"reply": "Invalid request format."}

    # Save search history
    searches = user_searches_ref.child(user_id).get() or []
    searches.append(query)
    user_searches_ref.child(user_id).set(searches[-5:])
    query = query.strip()

    # Load bot data
    bots = ref.get() or {}
    bot_list = list(bots.values()) if isinstance(bots, dict) else bots

    # Precompute embeddings if not cached
    embeddings_ref = db.reference('bot_embeddings')
    bot_embeddings = embeddings_ref.get() or {}
    if not bot_embeddings:
        for i, bot_data in enumerate(bot_list):
            if str(i) not in bot_embeddings:
                bot_embeddings[str(i)] = get_embedding(bot_data.get('description', '')).tolist()
        embeddings_ref.set(bot_embeddings)

    # Keyword Search
    matching_bots = []
    for bot_data in bot_list:
        name = bot_data.get('name', '').lower()
        description = bot_data.get('description', '').lower()
        if query in name or query in description:
            matching_bots.append(bot_data)

    if matching_bots:
        best_match = matching_bots[0]
        reply_text = f"Best match: {best_match.get('name', 'Unknown')}\nDescription: {best_match.get('description', 'No description')}\nLink: {best_match.get('link', 'No link')}"

    # Category Filter
    if query.startswith("/filter"):
        category = query.replace("/filter", "").strip().lower()
        filtered_bots = [b for b in bot_list if b.get('category', '').lower() == category]
        if filtered_bots:
            reply_text = "Matching bots:\n" + "\n".join(
                f"{b.get('name', 'Unknown')}\nDescription: {b.get('description', 'No description')}\nLink: {b.get('link', 'No link')}\n"
                for b in filtered_bots
            )
        else:
            reply_text = f"No bots found in category '{category}'."

    # Semantic Search
    if reply_text == "No matching bot found.":
        query_embedding = get_embedding(query)
        similarities = {}

        for i, bot_data in enumerate(bot_list):
            if isinstance(bot_embeddings, dict):
                embedding = np.array(bot_embeddings.get(str(i), get_embedding(bot_data.get('description', ''))))
            elif isinstance(bot_embeddings, list):
                try:
                    embedding = np.array(bot_embeddings[i])
                except (IndexError, TypeError):
                    embedding = np.array(get_embedding(bot_data.get('description', '')))
            else:
                embedding = np.array(get_embedding(bot_data.get('description', '')))

            similarity = cosine_similarity([query_embedding], [embedding])[0][0]
            similarities[i] = similarity

        best_match_idx = max(similarities, key=similarities.get, default=None)
        if best_match_idx is not None and similarities[best_match_idx] > 0.3:
            best_match = bot_list[best_match_idx]
            reply_text = f"Best match: {best_match.get('name', 'Unknown')}\nDescription: {best_match.get('description', 'No description')}\nLink: {best_match.get('link', 'No link')}"
        else:
            reply_text = generate_openrouter_response(query)

    # Send reply to Telegram
    if 'update_id' in data and user_id:
        await bot.send_message(chat_id=user_id, text=reply_text)

    return {"reply": reply_text}

# Favorites and Ratings APIs (unchanged)
@app.route('/favorite', methods=['POST'])
def handle_favorite():
    data = request.get_json()
    auth_header = request.headers.get('Authorization')
    user_id = None
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        user_id = verify_firebase_token(token)
    if not user_id:
        user_id = data.get('user_id', 'flutter_user')

    bot_name = data.get('bot_name')
    action = data.get('action')

    favorites = favorites_ref.child(user_id).get() or []
    bots = ref.get() or {}
    bot_list = list(bots.values()) if isinstance(bots, dict) else bots

    if action == 'add' and bot_name:
        bot_data = next((b for b in bot_list if b.get('name') == bot_name), None)
        if bot_data and bot_name not in [f.get('name') for f in favorites]:
            favorites.append(bot_data)
            favorites_ref.child(user_id).set(favorites)
            return jsonify({"status": "added", "count": len(favorites)})
    elif action == 'remove' and bot_name:
        favorites = [f for f in favorites if f.get('name') != bot_name]
        favorites_ref.child(user_id).set(favorites)
        return jsonify({"status": "removed", "count": len(favorites)})
    elif action == 'count':
        return jsonify({"status": "count", "count": len(favorites)})
    return jsonify({"status": "no change", "count": len(favorites)})

@app.route('/rate', methods=['POST'])
def handle_rate():
    data = request.get_json()
    auth_header = request.headers.get('Authorization')
    user_id = None
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        user_id = verify_firebase_token(token)
    if not user_id:
        user_id = data.get('user_id', 'flutter_user')

    bot_name = data.get('bot_name')
    action = data.get('action')
    value = data.get('value')

    snapshot = ratings_ref.child(bot_name).get()
    ratings = {'ratings': [], 'likes': 0, 'liked_by': [], 'avg_rating': 0.0}
    if snapshot is not None and isinstance(snapshot, dict):
        ratings.update(snapshot)

    if action == 'rate' and isinstance(value, (int, float)):
        if 1 <= value <= 5:
            ratings['ratings'].append(float(value))
            avg_rating = sum(ratings['ratings']) / len(ratings['ratings'])
            ratings['avg_rating'] = round(avg_rating, 1)
            ratings_ref.child(bot_name).update(ratings)
            return jsonify({"status": "rated", "avg_rating": ratings['avg_rating'], "like_count": ratings['likes']})
        return jsonify({"status": "invalid", "avg_rating": ratings['avg_rating'], "like_count": ratings['likes']})

    elif action == 'like' and isinstance(value, bool):
        liked_by = ratings.get('liked_by', [])
        if value and user_id not in liked_by:
            ratings['likes'] += 1
            liked_by.append(user_id)
        elif not value and user_id in liked_by:
            ratings['likes'] -= 1
            liked_by.remove(user_id)
        ratings['liked_by'] = liked_by
        ratings_ref.child(bot_name).update(ratings)
        avg_rating = sum(ratings['ratings']) / len(ratings['ratings']) if ratings['ratings'] else 0.0
        return jsonify({"status": "liked", "avg_rating": round(avg_rating, 1), "like_count": ratings['likes']})

    elif action == 'get':
        avg_rating = sum(ratings['ratings']) / len(ratings['ratings']) if ratings['ratings'] else 0.0
        ratings['avg_rating'] = round(avg_rating, 1)
        ratings_ref.child(bot_name).update(ratings)
        return jsonify({"status": "fetched", "avg_rating": ratings['avg_rating'], "like_count": ratings['likes']})

    return jsonify({"status": "no change", "avg_rating": ratings['avg_rating'], "like_count": ratings['likes']})

# Telegram Webhook
@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    try:
        data = request.get_json()
        logging.debug(f"Received data: {data}")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        response = loop.run_until_complete(handle_telegram_update(data))
        return jsonify(response)
    except Exception as e:
        logging.error(f"Telegram webhook error: {e}")
        return jsonify({"error": str(e)}), 500

# Health Check Endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route("/")
def home():
    return "Botify backend is running 🚀"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    logging.info(f"Starting Gunicorn on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)