# Architektura Aplikacji - warszawskieceny.pl

## Ogólny Przegląd Systemu

```
┌─────────────────────────────────────────────────────────┐
│                   FRONTEND (HTML/CSS/JS)                │
│                     (localhost:8080)                    │
│                                                         │
│  • index.html - Strona główna                           │
│  • login.html - Logowanie użytkownika                   │
│  • register.html - Rejestracja użytkownika              │
│  • predykcja.html - Formularz predykcji cen             │
│  • success.html - Strona potwierdzenia płatności        │ 
│                                                         │
└──────────────────────┬──────────────────────────────────┘
                       │
                       │ HTTP/REST API
                       │ (JSON)
                       │
┌──────────────────────v──────────────────────────────────┐
│                BACKEND (Flask - Python)                 │
│              (localhost:10000)                          │
│                                                         │
│  Endpointy:                                             │
│  ├─ POST /register - Rejestracja użytkownika            │
│  ├─ POST /login - Logowanie, zwraca JWT token           │
│  ├─ POST /create-checkout-session - Tworzenie sesji     │
│  │       płatności Stripe                               │
│  ├─ POST /webhook - Callback od Stripe (do ngroka)      │
│  ├─ POST /predict - Predykcja cen (wymaga płatności)    │
│  └─ GET /ping - Health check                            │
│                                                         │
│  Funkcjonalności:                                       │
│  • JWT Authentication                                   │
│  • Rate Limiting (7 req/10s na /predict)                │
│  • ML Price Prediction                                  │<─────────────────┐
│  • Payment Processing                                   │                  │   
│  • Caching (Redis)                                      │                  │   
└──────────┬──────────────────┬──────────────┬────────────┘                  │
           │                  │              │                               │   
           │ SQL              │ HTTPS        │ Cache/TTL                     │   
           │ (port 5432)      │ (REST)       │ (port 6379)                   │
           │                  │              │                               │   
    ┌──────v────────────┐  ┌──v──────────┐ ┌─v─────────────┐                 │   
    │   PostgreSQL DB   │  │ Stripe API  │ │    Redis      │                 │   
    │                   │  │  (External) │ │   (Cache)     │                 │   
    │                   │  │             │ │               │                 │   
    │ Tabele:           │  │ • Sessions  │ │ • Wyniki ZIP  │        ┌─────────────────┐
    │ • users           │  │ • Webhook   │ │               │        │      ngrok      │  
    │ • payments        │  │ • Events    │ │               │        │    (port 4040)  │  
    │ • predictions     │  │             │ │               │        │                 │  
    └───────────────────┘  └─────────────┘ └───────────────┘        └────/\───────────┘         
                                   │                                     │   
                                   │                                     │   
                                   └─────────────────────────────────────┘ 


```

---

## Proces Rejestracji i Logowania

```mermaid
    1. User przekazuje email i hasło
    2. następuje wywołanie endpointu POST /register
    3. Następuje hashowanie hasła
    4. Zapisanie emailu i hasła w bazie danych
    6. Redirect do login.html 
```

---

## Proces Płatności i Predykcji

```mermaid
    1. Zalogowany User Wypełnia formularz
    2. JWT Token zostaje sprawdzony a następnie wywolujemy endpoint POST /create-checkout-session
    3. Przekierowanie do stripe
    4. Create Session na Stripe
    5. Płatność
    6. POST /webhook ze strony Stripe w celu zapisania session_id do identyfikacji zapłaty
    7. INSERT w tablicy payments
    8. Przekierowanie na strone success.html
    9. Wygenerowanie wyniku za pomocą wywołania endpointu GET /predict
    10. Sprawdzenie JWT_key oraz session_id
    11. Predykcja ceny
    12. Sprawdzenie Cache
    13. Wypisanie wyników
```

---

## Bezpieczeństwo

| Komponent | Zabezpieczenie                         |
|-----------|----------------------------------------|
| **Hasła** | hashowanie hasła                       |
| **Autoryzacja** | JWT tokens (flask-jwt-extended)        |
| **Stripe Webhook** | HMAC-SHA256 signature validation       |
| **Rate Limiting** | 7 requests na 10 sekund dla `/predict` |
| **CORS** | Ograniczony do `localhost:8080`        |

---



---

## Technologie

| Warstwa | Technologia                    | Port | Opis |
|---------|--------------------------------|---|---|
| **Frontend** | HTML5, CSS, Vanilla JavaScript | 8080 | Aplikacja webowa |
| **Backend** | Flask (Python)                 | 10000 | REST API |
| **Database** | PostgreSQL                     | 5432 | Baza danych |
| **Cache** | Redis                          | 6379 | Cachowanie wyników |
| **Payment** | Stripe API                     | HTTPS | Przetwarzanie płatności |
| **Auth** | JWT (flask-jwt-extended)       | - | Autoryzacja |
| **ML** | linear regression (model.py)   | - | Model predykcji cen |

---

## Proces Predykcji - Szczegóły

```
1. User loguje się -> Otrzymuje JWT token
2. User przechodzi do /predykcja.html
3. User wypełnia:
   - ulica 
   - numer 
   - powierzchnia
   - piętro
   - liczba pokoi
4. User tworzy sesję płatności -> Płaci na Stripe
5. Stripe wysyła webhook /webhook do ngroka
6. Backend zapisuje Payment(paid=True) w PostgreSQL
7. User woła /predict z session_id
8. Backend waliduje:
   - Czy sesja exists?
   - Czy paid=True?
   - Czy dostęp nie wygasł? (1 godzina)
9. Backend szuka w Redis cache
10. Jeśli cache hit -> zwraca cached ZIP
11. Jeśli cache miss -> 
    - Uruchamia ML model (predict_price)
    - Generuje 4 CSVy:
      • predykcja.csv (wynik modelu)
      • dane z budynku.csv
      • dane z ulicy.csv
      • dane z okolicy.csv
12. Upakowanie w ZIP
13. Cache do Redis
14. Zwrot ZIP do frontendu
15. User pobiera plik
```

---



---

## Podsumowanie Architektury

- **Frontend**: Aplikacja HTML/CSS/JS 
- **Backend**: Flask REST API z autoryzacją JWT
- **Baza danych**: PostgreSQL dla danych użytkowników i płatności
- **Cache**: Redis dla szybkiego dostępu do wyników predykcji
- **Płatności**: Integracja ze Stripe API z webhook validation
- **ML**: Model regresji liniowej do predykcji cen mieszkań
- **Rate Limiting**: Ochrona przed nadużyciem API
- **Security**: Hash haseł, JWT tokens, Stripe signature validation

