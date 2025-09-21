"""Firestore helpers for users, mood logs, and chat sessions."""

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


# Note: User profile operations are now handled directly by the Android app with Firebase
# The Flask backend only handles chat and mood-related operations


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


# Chat Session Operations
def save_chat_message(user_id: str, session_id: str, message_data: Dict[str, Any]) -> bool:
    """
    Save a chat message to a session.
    
    Args:
        user_id (str): The Firebase Auth user ID
        session_id (str): The chat session ID
        message_data (dict): Message data (role, content, timestamp)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Reference to the chat session document
        session_ref = db.collection('chat_sessions').document(session_id)
        
        # Check if session exists, create if not
        session_doc = session_ref.get()
        if not session_doc.exists:
            # Create new session
            session_data = {
                'user_id': user_id,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'messages': []
            }
            session_ref.set(session_data)
        
        # Add timestamp to message
        message_data['timestamp'] = datetime.utcnow()
        
        # Add message to the session
        session_ref.update({
            'messages': firestore.ArrayUnion([message_data]),
            'updated_at': datetime.utcnow()
        })
        
        return True
        
    except Exception as e:
        print(f"Error saving chat message for session {session_id}: {str(e)}")
        return False


def get_chat_history(user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve chat history for a specific session.
    
    Args:
        user_id (str): The Firebase Auth user ID
        session_id (str): The chat session ID
        
    Returns:
        dict: Chat session data with messages, or None if not found
    """
    try:
        session_ref = db.collection('chat_sessions').document(session_id)
        session_doc = session_ref.get()
        
        if session_doc.exists:
            session_data = session_doc.to_dict()
            
            # Verify the session belongs to the user
            if session_data.get('user_id') == user_id:
                return session_data
            else:
                print(f"Access denied: Session {session_id} does not belong to user {user_id}")
                return None
        else:
            return None
            
    except Exception as e:
        print(f"Error retrieving chat history for session {session_id}: {str(e)}")
        return None


def get_user_chat_sessions(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Retrieve all chat sessions for a user.
    
    Args:
        user_id (str): The Firebase Auth user ID
        limit (int): Maximum number of sessions to retrieve
        
    Returns:
        list: List of chat sessions, ordered by last update (newest first)
    """
    try:
        sessions = []
        
        # Query chat sessions for the user
        query = (db.collection('chat_sessions')
                .where('user_id', '==', user_id)
                .order_by('updated_at', direction=firestore.Query.DESCENDING)
                .limit(limit))
        
        docs = query.stream()
        
        for doc in docs:
            session = doc.to_dict()
            session['id'] = doc.id
            # Don't include full message history in the list view
            if 'messages' in session:
                session['message_count'] = len(session['messages'])
                del session['messages']
            sessions.append(session)
        
        return sessions
        
    except Exception as e:
        print(f"Error retrieving chat sessions for {user_id}: {str(e)}")
        return []


def create_chat_session(user_id: str) -> Optional[str]:
    """
    Create a new chat session document in Firestore.
    
    Args:
        user_id (str): The Firebase Auth user ID
        
    Returns:
        str: The session_id of the newly created document, or None if error occurs
    """
    if db is None:
        raise RuntimeError("Firebase has not been initialized. Call init_firebase() first.")
    
    try:
        # Create new session document with initial data
        session_data = {
            'user_id': user_id,
            'start_time': datetime.utcnow(),
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'messages': [],  # Will store message history
            'status': 'active'
        }
        
        # Add the document to Firestore and get the auto-generated ID
        doc_ref = db.collection('chat_sessions').add(session_data)
        session_id = doc_ref[1].id  # doc_ref is a tuple (timestamp, DocumentReference)
        
        print(f"Created new chat session {session_id} for user {user_id}")
        return session_id
        
    except Exception as e:
        print(f"Error creating chat session for {user_id}: {str(e)}")
        return None


def update_session_summary_and_title(session_id: str, title: str, summary: str) -> bool:
    """
    Update the AI-generated title and summary for a chat session at the end of the session.
    
    Args:
        session_id (str): The chat session ID
        title (str): The AI-generated short title for the session
        summary (str): The AI-generated detailed summary of the conversation
        
    Returns:
        bool: True if successful, False otherwise
    """
    if db is None:
        raise RuntimeError("Firebase has not been initialized. Call init_firebase() first.")
    
    try:
        # Update the session document with title, summary, and end time
        update_data = {
            'title': title,
            'summary': summary,
            'end_time': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'status': 'completed'
        }
        
        db.collection('chat_sessions').document(session_id).update(update_data)
        
        print(f"Updated session {session_id} with title and summary")
        return True
        
    except Exception as e:
        print(f"Error updating session summary for {session_id}: {str(e)}")
        return False


def update_chat_summary(session_id: str, summary: str) -> bool:
    """
    Update the AI-generated summary for a chat session.
    
    Args:
        session_id (str): The chat session ID
        summary (str): AI-generated summary of the conversation
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        session_ref = db.collection('chat_sessions').document(session_id)
        session_ref.update({
            'summary': summary,
            'summary_updated_at': datetime.utcnow()
        })
        return True
        
    except Exception as e:
        print(f"Error updating chat summary for session {session_id}: {str(e)}")
        return False


def delete_chat_session(user_id: str, session_id: str) -> bool:
    """
    Delete a chat session (with user verification).
    
    Args:
        user_id (str): The Firebase Auth user ID
        session_id (str): The chat session ID to delete
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        session_ref = db.collection('chat_sessions').document(session_id)
        session_doc = session_ref.get()
        
        if session_doc.exists:
            session_data = session_doc.to_dict()
            
            # Verify the session belongs to the user
            if session_data.get('user_id') == user_id:
                session_ref.delete()
                return True
            else:
                print(f"Access denied: Cannot delete session {session_id} for user {user_id}")
                return False
        else:
            print(f"Session {session_id} not found")
            return False
            
    except Exception as e:
        print(f"Error deleting chat session {session_id}: {str(e)}")
        return False