"""Firestore helpers for users, mood logs, and crisis resources."""

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Union


# Global Firestore client
db = None


def init_firebase(credentials_path: str):
    """
    Initialize Firebase Admin SDK with service account credentials.
    
    Args:
        credentials_path (str): Path to the Firebase service account JSON file
        
    Raises:
        Exception: If Firebase initialization fails
    """
    global db
    
    try:
        # Initialize Firebase Admin SDK
        cred = credentials.Certificate(credentials_path)
        firebase_admin.initialize_app(cred)
        
        # Get Firestore client
        db = firestore.client()
        
        print("Firebase Admin SDK initialized successfully")
        
    except Exception as e:
        print(f"Failed to initialize Firebase: {str(e)}")
        raise


def get_firestore_client():
    """
    Get the Firestore client instance.
    
    Returns:
        firestore.Client: The Firestore client
        
    Raises:
        RuntimeError: If Firebase hasn't been initialized
    """
    if db is None:
        raise RuntimeError("Firebase has not been initialized. Call init_firebase() first.")
    return db


# (Removed legacy user profile and mood history helpers to focus on daily/weekly quiz logic)


# -----------------------------------------------------------------------------
# Mood Quiz (Daily & Weekly) Operations
# -----------------------------------------------------------------------------
def save_daily_mood_log(user_id: str, daily_log: Dict[str, Any]) -> Optional[str]:
    """
    Save a structured daily mood quiz log to Firestore.

    Collection: user_mood_logs

    Args:
        user_id (str): Firebase Auth user ID
        daily_log (dict): Structured daily log payload

    Returns:
        Optional[str]: Document ID if saved successfully, else None
    """
    if db is None:
        raise RuntimeError("Firebase has not been initialized. Call init_firebase() first.")

    try:
        daily_log['user_id'] = user_id
        # Default date if not provided
        if 'date' not in daily_log or not daily_log['date']:
            daily_log['date'] = date.today().isoformat()
        # Server-side timestamp
        daily_log['submitted_at'] = datetime.utcnow()

        doc_ref = db.collection('user_mood_logs').add(daily_log)
        return doc_ref[1].id
    except Exception as e:
        print(f"Error saving daily mood log for {user_id}: {str(e)}")
        return None


def get_last_daily_mood_logs(user_id: str, limit: int = 7) -> List[Dict[str, Any]]:
    """
    Retrieve the most recent daily mood quiz logs for a user.

    Args:
        user_id (str): Firebase Auth user ID
        limit (int): Number of entries to retrieve (default: 7)

    Returns:
        List[Dict[str, Any]]: List of daily mood logs (newest first)
    """
    if db is None:
        raise RuntimeError("Firebase has not been initialized. Call init_firebase() first.")

    try:
        logs = []
        query = (
            db.collection('user_mood_logs')
              .where('user_id', '==', user_id)
              .order_by('submitted_at', direction=firestore.Query.DESCENDING)
              .limit(limit)
        )
        docs = query.stream()
        for doc in docs:
            entry = doc.to_dict()
            entry['id'] = doc.id
            logs.append(entry)
        return logs
    except Exception as e:
        print(f"Error retrieving last daily mood logs for {user_id}: {str(e)}")
        return []


def get_daily_mood_logs_count(user_id: str) -> int:
    """
    Count total number of daily mood logs for a user.

    Args:
        user_id (str): Firebase Auth user ID

    Returns:
        int: Total count of documents in user_mood_logs for the user
    """
    if db is None:
        raise RuntimeError("Firebase has not been initialized. Call init_firebase() first.")

    try:
        query = db.collection('user_mood_logs').where('user_id', '==', user_id)
        count = 0
        for _ in query.stream():
            count += 1
        return count
    except Exception as e:
        print(f"Error counting daily mood logs for {user_id}: {str(e)}")
        return 0


def weekly_dass_exists(user_id: str, week_start: str, week_end: str) -> bool:
    """
    Check if a weekly DASS record already exists for the given user and week.

    Args:
        user_id (str): Firebase Auth user ID
        week_start (str): ISO date string for week start
        week_end (str): ISO date string for week end

    Returns:
        bool: True if a record exists, False otherwise
    """
    if db is None:
        raise RuntimeError("Firebase has not been initialized. Call init_firebase() first.")

    try:
        query = (
            db.collection('user_weekly_dass')
              .where('user_id', '==', user_id)
              .where('week_start', '==', week_start)
              .where('week_end', '==', week_end)
        )
        docs = query.stream()
        for _ in docs:
            return True
        return False
    except Exception as e:
        print(f"Error checking weekly DASS existence for {user_id}: {str(e)}")
        return False


def save_weekly_dass_totals(user_id: str, week_start: str, week_end: str,
                             depression_total: int, anxiety_total: int, stress_total: int) -> Optional[str]:
    """
    Save weekly DASS-21 totals to Firestore.

    Collection: user_weekly_dass

    Args:
        user_id (str): Firebase Auth user ID
        week_start (str): ISO date string for week start
        week_end (str): ISO date string for week end
        depression_total (int): Scaled total (DASS-21 x2)
        anxiety_total (int): Scaled total (DASS-21 x2)
        stress_total (int): Scaled total (DASS-21 x2)

    Returns:
        Optional[str]: Document ID if saved successfully, else None
    """
    if db is None:
        raise RuntimeError("Firebase has not been initialized. Call init_firebase() first.")

    try:
        data = {
            'user_id': user_id,
            'week_start': week_start,
            'week_end': week_end,
            'depression_total': depression_total,
            'anxiety_total': anxiety_total,
            'stress_total': stress_total,
            'calculated_at': datetime.utcnow(),
        }

        doc_ref = db.collection('user_weekly_dass').add(data)
        return doc_ref[1].id
    except Exception as e:
        print(f"Error saving weekly DASS totals for {user_id}: {str(e)}")
        return None


def get_cached_crisis_resources(country: str) -> Optional[Dict[str, Any]]:
    """
    Get cached crisis resources for a specific country.
    Works with both country codes (e.g., 'US') and country names (e.g., 'United States').
    
    Args:
        country (str): Country code or name to get resources for
        
    Returns:
        dict: Crisis resources data, or None if not found in cache
    """
    if db is None:
        raise RuntimeError("Firebase has not been initialized. Call init_firebase() first.")
    
    if not country or not country.strip():
        print("Warning: Attempted to get cached crisis resources with an empty country parameter.")
        return None

    try:
        # Normalize country input (uppercase for codes, title case for names)
        country_id = country.strip()
        if len(country_id) <= 3:  # Likely a country code
            country_id = country_id.upper()
        else:  # Likely a country name
            country_id = country_id.title()
        
        # Try to get document with country code/name as ID
        doc_ref = db.collection('crisis_resources').document(country_id)
        doc = doc_ref.get()
        
        if doc.exists:
            return doc.to_dict()
        
        # If not found by exact match and it's a country name, try to find by country field
        if len(country_id) > 3:
            query = db.collection('crisis_resources').where('country', '==', country_id)
            docs = query.stream()
            for doc in docs:
                return doc.to_dict()
        
        return None
            
    except Exception as e:
        print(f"Error getting cached crisis resources for {country}: {str(e)}")
        return None


def cache_crisis_resources(country: str, resources: Dict[str, Any]) -> bool:
    """
    Cache crisis resources for a specific country.
    
    Args:
        country (str): Country code or name to cache resources for
        resources (dict): Crisis resources data to cache
        
    Returns:
        bool: True if successful, False otherwise
    """
    if db is None:
        raise RuntimeError("Firebase has not been initialized. Call init_firebase() first.")
    
    if not country or not country.strip():
        print("Warning: Attempted to cache crisis resources with an empty country parameter.")
        return False

    try:
        # Normalize country input (uppercase for codes, title case for names)
        country_id = country.strip()
        if len(country_id) <= 3:  # Likely a country code
            country_id = country_id.upper()
        else:  # Likely a country name
            country_id = country_id.title()
        
        # Add country field to resources for querying
        resources['country'] = country_id
        resources['cached_at'] = datetime.utcnow()
        
        # Save to crisis_resources collection with country as document ID
        db.collection('crisis_resources').document(country_id).set(resources)
        return True
        
    except Exception as e:
        print(f"Error caching crisis resources for {country}: {str(e)}")
        return False