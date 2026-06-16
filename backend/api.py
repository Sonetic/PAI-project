from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd
import io
import zipfile
import stripe
from flask_sqlalchemy import SQLAlchemy
import os
import sys
from predykcja import predict_price
from datetime import datetime, timedelta, timezone
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_jwt_extended import JWTManager
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
from flask_jwt_extended import jwt_required, get_jwt_identity
from dotenv import load_dotenv
load_dotenv()


# =========================
# APP
# =========================
app = Flask(__name__)

app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
jwt = JWTManager(app)

CORS(
    app,
    resources={r"/*": {"origins": [
        "http://localhost:8080"
    ]}}
)



# =========================
# ENV
# =========================
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/warszawskieceny"
)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

PRICE = 200  # grosze

# =========================
# MODEL
# =========================

class User(db.Model):
    __tablename__ = "users"

    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.String, primary_key=True)
    paid = db.Column(db.Boolean, default=False)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)


with app.app_context():
    db.create_all()


@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Brak danych"}), 400

    existing = User.query.filter_by(email=email).first()
    if existing:
        return jsonify({"error": "Użytkownik istnieje"}), 409

    hashed_password = generate_password_hash(password)

    user = User(email=email, password=hashed_password)
    db.session.add(user)
    db.session.commit()

    return jsonify({"message": "Konto utworzone"}), 201

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Brak danych"}), 400

    user = User.query.filter_by(email=email).first()

    if not user or not check_password_hash(user.password, password):
        return jsonify({"error": "Nieprawidłowe dane"}), 401

    token = create_access_token(identity=str(user.user_id))
    print("LOGIN SUCCESS:", user.user_id, flush=True)
    print("TOKEN:", token, flush=True)

    return jsonify({
        "token": token,
        "user_id": user.user_id
    }), 200

# =========================
# CREATE PAYMENT SESSION
# =========================
@app.route("/create-checkout-session", methods=["POST"])
@jwt_required()
def create_checkout_session():
    data = request.get_json()
    print("JWT KEY:", app.config["JWT_SECRET_KEY"], flush=True)
    user_id = get_jwt_identity()
    print("USER:", user_id)

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
        success_url="http://localhost:8080/success.html?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="http://localhost:8080/predykcja.html",
        metadata={
            "ulica": data.get("ulica"),
            "numer": data.get("numer"),
        }
    )

    return jsonify({"url": session.url})


# =========================
# STRIPE WEBHOOK
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

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        session_id = session["id"]

        payment = Payment(
            id=session_id,
            paid=True,
            used=False,
            created_at=datetime.utcnow()
        )

        db.session.merge(payment)
        db.session.commit()

        print("PAYMENT SAVED:", session_id)

    return "ok", 200


# =========================
# LIMITER
# =========================
limiter = Limiter(get_remote_address, app=app)

# =========================
# PREDICTION
# =========================
@app.route("/predict", methods=["POST"])
@limiter.limit("7 per 10 seconds")
def predict():
    data = request.get_json()
    session_id = data.get("session_id")

    if not session_id:
        return jsonify({"error": "Brak session_id"}), 400

    payment = Payment.query.filter_by(id=session_id).first()

    if not payment:
        return jsonify({"error": "Brak płatności"}), 403

    if not payment.paid:
        return jsonify({"error": "Nieopłacone"}), 402

    now = datetime.now(timezone.utc)

    if not payment.used:
        payment.used = True
        payment.expires_at = now + timedelta(hours=1)
        db.session.commit()
    else:
        if not payment.expires_at:
            return jsonify({"error": "Błąd danych"}), 500

        expires_at = payment.expires_at

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if now > expires_at:
            return jsonify({"error": "Dostęp wygasł"}), 403

    # =========================
    # ML LOGIC
    # =========================
    result = predict_price(
        data["ulica"],
        data["numer"],
        data["powierzchnia"],
        data["pietro"],
        data["liczba_pokoi"]
    )

    # =========================
    # CSV OUTPUT
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
    # ZIP RESPONSE
    # =========================
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("predykcja.csv", pred_csv.getvalue())

        if budynek_csv:
            zf.writestr("dane z budynku.csv", budynek_csv.getvalue())

        if ulica_csv:
            zf.writestr("dane z ulicy.csv", ulica_csv.getvalue())

        zf.writestr("dane z okolicy.csv", okolica_csv.getvalue())

    zip_buffer.seek(0)

    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name="wyniki.zip"
    )


@app.route("/ping", methods=["GET"])
@limiter.limit("3 per 4 minutes")
def ping():
    return jsonify({"status": "alive"}), 200



# =========================
# START
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)