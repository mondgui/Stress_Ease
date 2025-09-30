"""Firestore helpers for users and mood logs."""

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from typing import Dict, List, Optional, Any


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


def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get user profile data from Firestore.
    
    Args:
        user_id (str): The Firebase Auth user ID
        
    Returns:
        dict: User profile data, or None if not found
    """
    try:
        # Get user profile from users collection
        doc_ref = db.collection('users').document(user_id)
        doc = doc_ref.get()
        
        if doc.exists:
            return doc.to_dict()
        else:
            return None
            
    except Exception as e:
        print(f"Error getting user profile for {user_id}: {str(e)}")
        return None


# Mood Entry Operations
def save_mood_log(user_id: str, mood_data: Dict[str, Any]) -> Optional[str]:
    """
    Save a mood log entry to Firestore.
    
    Args:
        user_id (str): The Firebase Auth user ID
        mood_data (dict): Mood log data including analysis results
        
    Returns:
        str: Document ID of the saved mood entry, or None if failed
    """
    try:
        # Add metadata
        mood_data['user_id'] = user_id
        mood_data['created_at'] = datetime.utcnow()
        
        # Save to mood_entries collection
        doc_ref = db.collection('mood_entries').add(mood_data)
        return doc_ref[1].id  # Return the document ID
        
    except Exception as e:
        print(f"Error saving mood log for {user_id}: {str(e)}")
        return None


def get_mood_history(user_id: str, limit: int = 30) -> List[Dict[str, Any]]:
    """
    Retrieve mood history for a user.
    
    Args:
        user_id (str): The Firebase Auth user ID
        limit (int): Maximum number of entries to retrieve
        
    Returns:
        list: List of mood entries, ordered by creation date (newest first)
    """
    try:
        mood_entries = []
        
        # Query mood entries for the user, ordered by creation date
        query = (db.collection('mood_entries')
                .where('user_id', '==', user_id)
                .order_by('created_at', direction=firestore.Query.DESCENDING)
                .limit(limit))
        
        docs = query.stream()
        
        for doc in docs:
            entry = doc.to_dict()
            entry['id'] = doc.id
            mood_entries.append(entry)
        
        return mood_entries
        
    except Exception as e:
        print(f"Error retrieving mood history for {user_id}: {str(e)}")
        return []