from flask import Flask, request

app = Flask(__name__)

@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    print("Webhook hit!")
    print("Headers:", dict(request.headers))
    print("Body:", request.get_data(as_text=True))
    return "OK", 200

@app.route("/ping", methods=["GET"])
def ping():
    return "pong", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860)