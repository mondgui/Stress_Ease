"""Chat endpoints: sessions and messages with local storage on Android."""

from flask import Blueprint, request, jsonify
from stressease.services.auth_service import token_required
from stressease.services.gemini_service import (
    generate_chat_response, start_chat_session, find_crisis_resources
)
from stressease.services.firebase_service import (
    get_cached_crisis_resources, cache_crisis_resources
)
from datetime import datetime
import uuid

# Create the chat blueprint
chat_bp = Blueprint('chat', __name__)

#------------------------------------------------------------------------------
# CRISIS SUPPORT ENDPOINTS
#------------------------------------------------------------------------------


@chat_bp.route('/crisis-resources', methods=['GET' , 'POST'])
@token_required
def get_crisis_resources(user_id):
    """
    Endpoint for getting country-specific Crisis resources.
    Triggered when user selects a country from dropdown in the SOS section.
    
    Query Parameters:
        country (str): Country name selected from dropdown
    
    Returns:
        JSON response with country-specific crisis resources
    """
    try:
        # Get country from query parameter - Android app sends from dropdown
        country = request.args.get('country', '').strip()
        
        # Set default country if somehow not provided (fallback only)
        if not country:
            country = 'India'
        
        # Step 1: Check cache first
        cached_resources = get_cached_crisis_resources(country)
        
        # Step 2: Cache hit - return cached resources
        if cached_resources:
            response = jsonify({
                'success': True,
                'message': 'Crisis resources retrieved from cache',
                'resources': cached_resources,
                'source': 'cache'
            })
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response, 200
        
        # Step 3: Cache miss - generate new resources using Gemini
        resources = find_crisis_resources(country)
        if not resources:
            response = jsonify({
                'success': False,
                'message': f'Could not find Crisis resources for {country}'
            })
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response, 404
        
        # Step 4: Cache the new resources in Firebase
        cache_success = cache_crisis_resources(country, resources)
        
        # Step 5: Return the resources
        response = jsonify({
            'success': True,
            'message': 'Crisis resources generated using AI',
            'resources': resources,
            'source': 'generated',
            'cached': cache_success
        })
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response, 200
        
    except Exception as e:
        response = jsonify({
            'success': False,
            'message': f'Error retrieving crisis resources: {str(e)}'
        })
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response, 500


# Dictionary to store active chat sessions
active_chat_sessions = {}


# Endpoint: POST /api/chat/message
# Purpose:  Send message and create session implicitly if needed
#------------------------------------------------------------------------------
@chat_bp.route('/message', methods=['POST'])
@token_required
def send_chat_message(user_id):
    """
    Endpoint for sending messages with implicit session creation.
    Chat history is stored locally on Android device.
    
    Expected JSON payload:
    {
        "message": "Hello, I'm feeling anxious today",
        "session_id": null  // null for new session, or existing session_id
    }
    
    Returns:
        JSON response with AI reply and session_id for local storage
    """
    try:
        # Get and validate JSON data
        message_data = request.get_json()
        if not message_data:
            return jsonify({
                'success': False,
                'error': 'Invalid request',
                'message': 'JSON data is required'
            }), 400
        
        # Extract and validate message
        user_message = message_data.get('message', '').strip()
        session_id = message_data.get('session_id')
        
        # Input validation - optimized with early returns
        if not user_message:
            return jsonify({
                'success': False,
                'error': 'Invalid message',
                'message': 'Message cannot be empty'
            }), 400
        
        if len(user_message) > 1000:
            return jsonify({
                'success': False,
                'error': 'Message too long',
                'message': 'Message must be 1000 characters or less'
            }), 400
        
        # Create timestamp once for efficiency
        timestamp = datetime.utcnow().isoformat()
        
        # Get or create session
        session_id, chat_session = _get_or_create_session(session_id)
        if not chat_session:
            return jsonify({
                'success': False,
                'error': 'Session not found',
                'message': 'Chat session has expired or does not exist'
            }), 404
        
        # Generate AI response (validation is already done inside generate_chat_response)
        ai_response = generate_chat_response(chat_session, user_message)
        
        # Return standard response structure
        return jsonify({
            'success': True,
            'user_message': {
                'content': user_message,
                'timestamp': timestamp,
                'role': 'user'
            },
            'ai_response': {
                'content': ai_response,
                'timestamp': timestamp,
                'role': 'assistant'
            },
            'session_id': session_id
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Failed to process message',
            'message': str(e)
        }), 500


def _get_or_create_session(session_id):
    """
    Optimized helper function to get existing session or create new one.
    
    Args:
        session_id (str): Session ID or None
        
    Returns:
        tuple: (session_id, chat_session) or (None, None) if failed
    """
    try:
        if not session_id:
            # Create new session
            session_id = str(uuid.uuid4())
            chat_session = start_chat_session({})
            active_chat_sessions[session_id] = chat_session
            return session_id, chat_session
        
        # Check if session exists
        if session_id in active_chat_sessions:
            return session_id, active_chat_sessions[session_id]
        
        # Session not found
        return None, None
        
    except Exception:
        return None, None





# Endpoint: POST /api/chat/end-session
# Purpose:  End chat session and cleanup server resources
@chat_bp.route('/end-session', methods=['POST'])
@token_required
def end_chat_session(user_id):
    """
    Optimized endpoint to end a chat session and clean up server-side resources.
    The complete chat history is stored locally on the Android device.
    
    Expected JSON payload:
    {
        "session_id": "a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6"
    }
    
    Returns:
        JSON response confirming session cleanup
    """
    try:
        # Get and validate JSON data
        request_data = request.get_json()
        if not request_data:
            return jsonify({
                'success': False,
                'error': 'Invalid request',
                'message': 'JSON data is required'
            }), 400
        
        # Extract and validate session_id
        session_id = request_data.get('session_id', '').strip()
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'Missing session_id',
                'message': 'session_id is required'
            }), 400
        
        # Optimized cleanup - batch operations
        cleanup_count = 0
        
        # Clean up active session from memory cache
        if session_id in active_chat_sessions:
            del active_chat_sessions[session_id]
            cleanup_count += 1
            
        # No need to clean up Crisis resources tracking anymore
            
        return jsonify({
            'success': True,
            'message': 'Session ended successfully',
            'cleanup_count': cleanup_count
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Failed to end session',
            'message': str(e)
        }), 500

