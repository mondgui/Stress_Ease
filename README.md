# StressEase Backend

A Flask API that uses Firebase (Auth + Firestore) and Google Gemini for mood analysis and chat support. User authentication and profile management are handled directly by the Android app with Firebase.

## Requirements
- Python 3.8+
- Firebase project with Firestore enabled
- Google Gemini API key

## Setup
1) Create a virtual environment and activate it
   - Windows: `python -m venv venv` then `venv\Scripts\activate`
   - macOS/Linux: `python -m venv venv` then `source venv/bin/activate`
2) Install packages: `pip install -r requirements.txt`
3) Create a .env file with:
   - GEMINI_API_KEY=...
   - FIREBASE_CREDENTIALS_PATH=path/to/service-account.json
   - FLASK_SECRET_KEY=some-random-string
4) Make sure the Firebase service account JSON exists at the path you set.

## Run
- `python run.py`
- Base URL: http://localhost:5000
- Health check: GET /health

## API
Base prefix for feature routes: /api

**Note:** User authentication and profile management are handled directly by the Android app using Firebase Authentication and Firestore. The Flask backend only handles mood tracking and chat functionality.

### Mood (/api/mood)
- POST /log — submit quiz and store AI analysis
- GET /history — recent mood entries
- GET /trends?days=30 — basic stats over a period
- GET /insights — quick tips based on recent history

### Chat (/api/chat)
- POST /message — send a message (creates session implicitly if session_id is null)
  - Includes integrated crisis detection with immediate support resources
- POST /end-session — end chat session and cleanup resources
- GET /crisis-resources — helplines and emergency resources

**Note:** Chat session listing, details, and deletion are handled directly by the Android app interacting with Firebase Firestore for better performance and real-time updates.

## Authentication
All API endpoints require a Firebase ID Token in the Authorization header:
```
Authorization: Bearer <firebase_id_token>
```

The Android app handles:
- User registration and login with Firebase Authentication
- User profile creation and management with Firestore
- Emergency contact management with Firestore

## Tests
- `python test_backend.py` runs a quick check for imports, config, and structure.

## Notes
- Keep your service account JSON and API keys out of version control.
- Configure Firestore rules for production to ensure users can only access their own data.
- For production, use a WSGI server (e.g., Gunicorn) and HTTPS.
- Crisis detection is centralized in the Gemini service for consistent handling across all interactions.