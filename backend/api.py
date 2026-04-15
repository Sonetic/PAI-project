from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd
import io
import zipfile
import stripe
import os

from predykcja import predict_price

app = Flask(__name__)
CORS(app)

# =========================
# STRIPE CONFIG (RENDER SAFE)
# =========================
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

PRICE = 201  # 2.01 PLN / 50 PLN zależnie jak ustawisz

# pamięć (na start MVP)
paid_sessions = set()

# =========================
# CREATE CHECKOUT SESSION
# =========================
@app.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    data = request.get_json()

    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": "pln",
                    "product_data": {
                        "name": "Raport cen mieszkań Warszawa",
                    },
                    "unit_amount": PRICE,
                },
                "quantity": 1,
            }
        ],

        # 🔥 TWOJE FRONTEND URL (RENDER)
        success_url="https://wwacenyrenderplatnoscistatic.onrender.com/success.html?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="https://wwacenyrenderplatnoscistatic.onrender.com/predykcja.html",

        metadata={
            "ulica": data.get("ulica"),
            "numer": data.get("numer"),
        }
    )

    return jsonify({"url": session.url})


# =========================
# WEBHOOK STRIPE (KLUCZOWE)
# =========================
@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            WEBHOOK_SECRET
        )
    except Exception as e:
        return str(e), 400

    # 🔥 PAYMENT CONFIRMED
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        paid_sessions.add(session["id"])
        print("PAYMENT OK:", session["id"])

    return "ok", 200


# =========================
# PREDICTION (PROTECTED)
# =========================
@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json()
    session_id = data.get("session_id")

    if not session_id:
        return jsonify({"error": "Brak session_id"}), 403

    # 🔥 webhook-based check
    if session_id not in paid_sessions:
        return jsonify({"error": "Nieopłacone"}), 403

    result = predict_price(
        data["ulica"],
        data["numer"],
        data["powierzchnia"],
        data["pietro"],
        data["liczba_pokoi"]
    )

    pred_csv = io.StringIO()
    pd.DataFrame([result[0]]).to_csv(pred_csv, index=False)

    okolica_csv = io.StringIO()
    result[1].to_csv(okolica_csv, index=False)

    ulica_csv = None
    budynek_csv = None

    if len(result) > 2:
        ulica_csv = io.StringIO()
        result[2].to_csv(ulica_csv, index=False)

    if len(result) > 3:
        budynek_csv = io.StringIO()
        result[3].to_csv(budynek_csv, index=False)

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("predykcja.csv", pred_csv.getvalue())
        zf.writestr("okolica.csv", okolica_csv.getvalue())

        if ulica_csv:
            zf.writestr("ulica.csv", ulica_csv.getvalue())

        if budynek_csv:
            zf.writestr("budynek.csv", budynek_csv.getvalue())

    zip_buffer.seek(0)

    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name="wyniki.zip"
    )


# =========================
# START (RENDER)
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)