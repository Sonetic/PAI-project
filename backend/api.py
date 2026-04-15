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
# STRIPE CONFIG
# =========================
stripe.api_key = "sk_test_51TMPjfB8svdwFzvVPv3WdYKNoyR2gs89fhA3f9opKyiiiiDDBIbGcN3EGqHE9QnOFBxp9LX2TTKQrZnevFiXBiPb00vnnPLAq3"

PRICE = 201  # 50 zł

# =========================
# CSV (opcjonalnie)
# =========================
df = pd.read_csv("unique_streets.csv")


# =========================
# CREATE STRIPE SESSION
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
        success_url="http://127.0.0.1:5500/success.html?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="http://127.0.0.1:5500/predykcja.html",
        metadata={
            "ulica": data.get("ulica"),
            "numer": data.get("numer"),
        }
    )

    return jsonify({"url": session.url})


# =========================
# PREDYKCJA (BLOCKED BY STRIPE)
# =========================
@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json()

    session_id = data.get("session_id")

    if not session_id:
        return jsonify({"error": "Brak płatności"}), 403

    # sprawdzenie Stripe
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception:
        return jsonify({"error": "Nieprawidłowa sesja"}), 403

    if session.payment_status != "paid":
        return jsonify({"error": "Nieopłacone"}), 403


    # =========================
    # TWOJA LOGIKA ML
    # =========================
    result = predict_price(
        data["ulica"],
        data["numer"],
        data["powierzchnia"],
        data["pietro"],
        data["liczba_pokoi"]
    )

    # =========================
    # CSV GENERATION
    # =========================
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

    # =========================
    # ZIP IN MEMORY
    # =========================
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
# START SERVER
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)