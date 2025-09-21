"""Chat endpoints: sessions, messages, summaries, and crisis resources."""

from flask import Blueprint, request, jsonify
from stressease.services.auth_service import token_required
from stressease.services.firebase_service import (
    get_chat_history, get_user_profile, save_chat_message,
    create_chat_session, update_session_summary_and_title
)
from stressease.services.gemini_service import (
    generate_chat_response, summarize_conversation, validate_gemini_response,
    start_chat_session, generate_chat_title
)
from datetime import datetime

# Create the chat blueprint
chat_bp = Blueprint('chat', __name__)


# ******************************************************************************
# * POST /api/chat/message - Send message (creates session implicitly if needed)
# ******************************************************************************
@chat_bp.route('/message', methods=['POST'])
@token_required
def send_chat_message(user_id):
    """
    Simplified endpoint for sending messages with implicit session creation.
    
    Expected JSON payload:
    {
        "message": "Hello, I'm feeling anxious today",
        "session_id": null  // null for new session, or existing session_id
    }
    
    Returns:
        JSON response with AI reply and session_id
    """
    try:
        # Get JSON data from request
        message_data = request.get_json()
        
        if not message_data:
            return jsonify({
                'success': False,
                'error': 'Invalid request',
                'message': 'JSON data is required'
            }), 400
        
        # Validate message
        user_message = message_data.get('message', '').strip()
        session_id = message_data.get('session_id')
        
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
        
        # Get user profile for context
        user_profile = get_user_profile(user_id)
        
        # Check if this is a new session (session_id is null/None)
        if not session_id:
            # IMPLICIT CREATE: First message in a new conversation
            
            # Create new session in Firestore
            session_id = create_chat_session(user_id)
            
            if not session_id:
                return jsonify({
                    'success': False,
                    'error': 'Session creation failed',
                    'message': 'Unable to create new chat session'
                }), 500
            
            # Start new ChatSession with Gemini (stateful conversation)
            chat_session = start_chat_session(user_profile or {})
            
            if not chat_session:
                return jsonify({
                    'success': False,
                    'error': 'AI session failed',
                    'message': 'Unable to initialize AI conversation'
                }), 500
            
            # Store the active session in memory cache
            from stressease.services.gemini_service import active_chat_sessions
            active_chat_sessions[session_id] = chat_session
            
        else:
            # ONGOING CONVERSATION: Use existing session
            from stressease.services.gemini_service import active_chat_sessions
            
            # Check if session exists in memory cache
            if session_id not in active_chat_sessions:
                return jsonify({
                    'success': False,
                    'error': 'Session not found',
                    'message': 'Chat session has expired or does not exist'
                }), 404
            
            chat_session = active_chat_sessions[session_id]
        
        # Generate AI response using the stateful ChatSession
        ai_response = generate_chat_response(chat_session, user_message)
        
        if not ai_response:
            return jsonify({
                'success': False,
                'error': 'AI response failed',
                'message': 'Unable to generate response at this time. Please try again.'
            }), 500
        
        # Validate AI response for safety
        if not validate_gemini_response(ai_response):
            ai_response = "I understand you're going through a difficult time. Please consider reaching out to a mental health professional or crisis helpline for immediate support."
        
        # Save user message to Firestore
        user_message_data = {
            'role': 'user',
            'content': user_message,
            'timestamp': datetime.utcnow()
        }
        
        success_user = save_chat_message(user_id, session_id, user_message_data)
        
        if not success_user:
            return jsonify({
                'success': False,
                'error': 'Database error',
                'message': 'Failed to save user message'
            }), 500
        
        # Save AI response to Firestore
        ai_message_data = {
            'role': 'assistant',
            'content': ai_response,
            'timestamp': datetime.utcnow()
        }
        
        success_ai = save_chat_message(user_id, session_id, ai_message_data)
        
        if not success_ai:
            return jsonify({
                'success': False,
                'error': 'Database error',
                'message': 'Failed to save AI response'
            }), 500
        
        # Return response with both reply and session_id
        return jsonify({
            'success': True,
            'reply': ai_response,
            'session_id': session_id,
            'timestamp': ai_message_data['timestamp'].isoformat()
        }), 201
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Server error',
            'message': str(e)
        }), 500


# ******************************************************************************
# * POST /api/chat/summarize - Generate session summary and cleanup
# ******************************************************************************
@chat_bp.route('/summarize', methods=['POST'])
@token_required
def summarize_chat_session(user_id):
    """
    Simplified endpoint for generating session summary and title at conversation end.
    
    Expected JSON payload:
    {
        "session_id": "a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6"
    }
    
    Returns:
        JSON response with generated title and summary
    """
    try:
        # Get JSON data from request
        request_data = request.get_json()
        
        if not request_data:
            return jsonify({
                'success': False,
                'error': 'Invalid request',
                'message': 'JSON data is required'
            }), 400
        
        session_id = request_data.get('session_id')
        
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'Missing session_id',
                'message': 'session_id is required'
            }), 400
        
        # Retrieve chat session from Firestore
        session_data = get_chat_history(user_id, session_id)
        
        if not session_data:
            return jsonify({
                'success': False,
                'error': 'Session not found',
                'message': 'Chat session not found or access denied'
            }), 404
        
        # Check if session has enough messages to summarize
        messages = session_data.get('messages', [])
        
        if len(messages) < 4:  # Need at least 4 messages (2 exchanges)
            return jsonify({
                'success': False,
                'error': 'Insufficient messages',
                'message': 'Session needs more messages to generate a meaningful summary'
            }), 400
        
        # Create transcript for AI processing
        transcript = "\n".join([
            f"{msg['role'].title()}: {msg['content']}"
            for msg in messages
        ])
        
        # Generate title and summary using Gemini AI
        title = generate_chat_title(transcript)
        summary = summarize_conversation(transcript)
        
        if not title or not summary:
            return jsonify({
                'success': False,
                'error': 'AI processing failed',
                'message': 'Unable to generate title and summary at this time'
            }), 500
        
        # Update session in Firestore with title, summary, and completion status
        success = update_session_summary_and_title(session_id, title, summary)
        
        if not success:
            return jsonify({
                'success': False,
                'error': 'Database error',
                'message': 'Failed to save session summary'
            }), 500
        
        # Clean up active session from memory cache
        from stressease.services.gemini_service import active_chat_sessions
        if session_id in active_chat_sessions:
            del active_chat_sessions[session_id]
        
        return jsonify({
            'success': True,
            'title': title,
            'summary': summary,
            'message': 'Session summarized and completed successfully'
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Server error',
            'message': str(e)
        }), 500


# Session management endpoints removed - Android app handles these directly with Firebase
# The app can query Firestore directly for better performance and real-time updates


# ******************************************************************************
# * GET /api/chat/crisis-resources - Get mental health helplines and resources
# ******************************************************************************
@chat_bp.route('/crisis-resources', methods=['GET'])
@token_required
def get_crisis_resources(user_id):
    """
    Get crisis support resources and emergency contacts.
    
    Returns:
        JSON response with crisis resources
    """
    try:
        # Get user's emergency contact if available
        user_profile = get_user_profile(user_id)
        emergency_contact = user_profile.get('emergency_contact') if user_profile else None
        
        # Standard crisis resources
        crisis_resources = {
            'emergency_services': {
                'number': '911',
                'description': 'For immediate life-threatening emergencies'
            },
            'crisis_hotlines': [
                {
                    'name': 'National Suicide Prevention Lifeline',
                    'number': '988',
                    'description': '24/7 crisis support',
                    'website': 'https://suicidepreventionlifeline.org'
                },
                {
                    'name': 'Crisis Text Line',
                    'number': 'Text HOME to 741741',
                    'description': '24/7 text-based crisis support',
                    'website': 'https://www.crisistextline.org'
                },
                {
                    'name': 'SAMHSA National Helpline',
                    'number': '1-800-662-4357',
                    'description': 'Treatment referral and information service',
                    'website': 'https://www.samhsa.gov/find-help/national-helpline'
                }
            ],
            'online_resources': [
                {
                    'name': 'Mental Health America',
                    'website': 'https://www.mhanational.org',
                    'description': 'Mental health resources and screening tools'
                },
                {
                    'name': 'National Alliance on Mental Illness (NAMI)',
                    'website': 'https://www.nami.org',
                    'description': 'Support groups and educational resources'
                }
            ]
        }
        
        response_data = {
            'success': True,
            'crisis_resources': crisis_resources
        }
        
        # Include user's emergency contact if available
        if emergency_contact:
            response_data['personal_emergency_contact'] = emergency_contact
        
        return jsonify(response_data), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve Crisis resources',
            'message': str(e)
        }), 500