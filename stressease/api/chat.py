"""Chat endpoints: sessions and messages with local storage on Android."""

from flask import Blueprint, request, jsonify
from stressease.services.auth_service import token_required
from stressease.services.gemini_service import (
    generate_chat_response, validate_gemini_response,
    start_chat_session
)
from datetime import datetime
import uuid
import re

# Create the chat blueprint
chat_bp = Blueprint('chat', __name__)

#------------------------------------------------------------------------------
# CRISIS SUPPORT ENDPOINT
#------------------------------------------------------------------------------
@chat_bp.route('/crisis-contacts', methods=['GET'])
@token_required
def get_crisis_contacts(user_id):
    """
    Endpoint for getting crisis support contact information.
    Triggered when user clicks the "Help/Crisis Support" button in the app.
    
    Returns:
        JSON response with crisis contact information
    """
    try:
        return jsonify({
            'success': True,
            'message': 'Crisis support contacts retrieved successfully',
            'contacts': CRISIS_CONTACTS
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve crisis contacts',
            'message': str(e)
        }), 500

#------------------------------------------------------------------------------
# SHARED DATA STRUCTURES
#------------------------------------------------------------------------------

# Dictionary to store active chat sessions
active_chat_sessions = {}

# Dictionary to track if Crisis resources have been offered to a session
crisis_resources_offered = {}

#------------------------------------------------------------------------------
# SECTION 1: CHAT SESSION MANAGEMENT
#------------------------------------------------------------------------------
# * POST /api/chat/message - Send message (creates session implicitly if needed)
# ******************************************************************************
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
        
        # Crisis detection - optimized to return tuple
        is_crisis, crisis_category = detect_crisis_message(user_message)
        
        # Handle crisis messages with optimized flow
        if is_crisis and (not session_id or session_id not in crisis_resources_offered):
            return _handle_crisis_message(user_message, session_id, timestamp, crisis_category)
        
        # Handle crisis confirmation responses
        if session_id in crisis_resources_offered and not crisis_resources_offered[session_id]:
            return _handle_crisis_confirmation(user_message, session_id, timestamp)
        
        # Handle regular chat messages - optimized session management
        session_id, chat_session = _get_or_create_session(session_id)
        if not chat_session:
            return jsonify({
                'success': False,
                'error': 'Session not found',
                'message': 'Chat session has expired or does not exist'
            }), 404
        
        # Generate AI response with validation
        ai_response = generate_chat_response(chat_session, user_message)
        
        # Validate AI response
        if not validate_gemini_response(ai_response):
            ai_response = "I apologize, but I'm having trouble generating a proper response right now. Could you please rephrase your message?"
        
        # Return optimized response structure
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


def _handle_crisis_message(user_message, session_id, timestamp, crisis_category):
    """
    Optimized helper function to handle Crisis messages.
    
    Args:
        user_message (str): The user's message
        session_id (str): Session ID or None
        timestamp (str): ISO timestamp
        crisis_category (str): Type of crisis detected
        
    Returns:
        Flask response for Crisis message
    """
    # Generate crisis-specific response
    ai_response = generate_crisis_response(user_message)
    
    # Get or create session
    session_id, chat_session = _get_or_create_session(session_id)
    if not chat_session:
        return jsonify({
            'success': False,
            'error': 'Session creation failed',
            'message': 'Unable to create chat session'
        }), 500
    
    # Mark crisis detection but not resources offered yet
    crisis_resources_offered[session_id] = False
    
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
        'session_id': session_id,
        'crisis_detected': True,
        'crisis_category': crisis_category,
        'confirmation_required': True,
        'confirmation_message': "Would you like emergency contact information?"
    }), 201


def _handle_crisis_confirmation(user_message, session_id, timestamp):
    """
    Optimized helper function to handle Crisis confirmation responses.
    
    Args:
        user_message (str): The user's response
        session_id (str): Session ID
        timestamp (str): ISO timestamp
        
    Returns:
        Flask response for Crisis confirmation
    """
    # Optimized pattern matching for yes/no responses
    positive_patterns = r'\b(yes|sure|okay|ok|please|help|need)\b'
    negative_patterns = r'\b(no|not|don\'t|dont|later|maybe)\b'
    
    user_lower = user_message.lower()
    
    if re.search(positive_patterns, user_lower):
        ai_response = "I'm glad you're open to resources. Here are some contacts that can provide immediate support."
        crisis_resources_offered[session_id] = True
        
        # Use the direct contact information stored in the file
        crisis_resources = CRISIS_CONTACTS
        
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
            'session_id': session_id,
             'crisis_detected': True,
             'show_resources': True,
             'crisis_resources': crisis_resources
        }), 201
        
    elif re.search(negative_patterns, user_lower):
        ai_response = "I understand you may not want resources right now, but I care about your wellbeing. Here are the support contacts in case you need them later."
        crisis_resources_offered[session_id] = True
        
        # Use the direct contact information stored in the file
        crisis_resources = CRISIS_CONTACTS
        
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
            'session_id': session_id,
            'crisis_detected': True,
            'show_resources': True,
            'crisis_resources': crisis_resources
        }), 201
    
    # If response is unclear, ask for clarification
    ai_response = "I want to make sure I understand - would you like me to share some emergency contact information that might be helpful?"
    
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
        'session_id': session_id,
        'crisis_detected': True,
        'confirmation_required': True,
        'confirmation_message': "Please respond with 'yes' or 'no'"
    }), 201


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


def _format_crisis_resources(crisis_contacts):
    """
    Convert database crisis contacts to expected API format.
    
    Args:
        crisis_contacts (list): List of crisis contacts from database
        
    Returns:
        dict: Formatted crisis resources
    """
    formatted = {
        'emergency_services': {},
        'crisis_hotlines': [],
        'online_resources': []
    }
    
    for contact in crisis_contacts:
        contact_type = contact.get('type', 'online_resource')
        
        if contact_type == 'emergency':
            formatted['emergency_services'] = {
                'number': contact.get('number'),
                'description': contact.get('description')
            }
        elif contact_type == 'crisis_hotline':
            hotline = {
                'name': contact.get('name'),
                'number': contact.get('number'),
                'description': contact.get('description')
            }
            if contact.get('website'):
                hotline['website'] = contact.get('website')
            formatted['crisis_hotlines'].append(hotline)
        else:
            resource = {
                'name': contact.get('name'),
                'description': contact.get('description')
            }
            if contact.get('website'):
                resource['website'] = contact.get('website')
            formatted['online_resources'].append(resource)
    
    return formatted

#------------------------------------------------------------------------------
# SECTION 2: END MESSAGE RELATED CODE
#------------------------------------------------------------------------------
# ******************************************************************************
# * POST /api/chat/end-session - End chat session and cleanup server resources
# ******************************************************************************
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
            
        # Clean up crisis resources tracking
        if session_id in crisis_resources_offered:
            del Crisis_resources_offered[session_id]
            cleanup_count += 1
            
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


# ******************************************************************************
# * POST /api/chat/crisis-response - Handle crisis messages with confirmation
# ******************************************************************************
@chat_bp.route('/crisis-response', methods=['POST'])
@token_required
def handle_crisis_response(user_id):
    """
    Handle crisis messages with appropriate responses and resources.
    
    Expected JSON payload:
    {
        "message": "I want to die",
        "session_id": "a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6",
        "confirmation_response": null  // null for initial message, "yes"/"no" for confirmation
    }
    
    Returns:
        JSON response with AI reply, Crisis resources, and confirmation request
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
        
        # Extract message and session data
        user_message = request_data.get('message', '').strip()
        session_id = request_data.get('session_id')
        confirmation_response = request_data.get('confirmation_response')
        
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'Invalid session',
                'message': 'Session ID is required'
            }), 400
        
        # Check if this is a confirmation response
        if confirmation_response is not None:
            # User has responded to the confirmation request
            timestamp = datetime.utcnow().isoformat()
            
            if confirmation_response.lower() == 'yes':
                ai_response = "I'm glad you're open to resources. Here are some contacts that can provide immediate support."
            else:
                ai_response = "I understand you may not want resources right now, but I care about your wellbeing. I'm sharing some contacts that might be helpful when you're ready."
            
            # Mark that resources have been provided for this session
            crisis_resources_offered[session_id] = True
            
            return jsonify({
                'success': True,
                'user_message': {
                    'content': confirmation_response,
                    'timestamp': timestamp,
                    'role': 'user'
                },
                'ai_response': {
                    'content': ai_response,
                    'timestamp': timestamp,
                    'role': 'assistant'
                },
                'session_id': session_id,
                'crisis_detected': True,
                'show_resources': True,
                'crisis_resources': INDIA_CRISIS_RESOURCES
            }), 200
        
        # This is an initial Crisis message
        # Generate an appropriate AI response for the Crisis message
        ai_response = generate_crisis_response(user_message)
        
        # Mark that we've offered resources for this session
        crisis_resources_offered[session_id] = True
        
        timestamp = datetime.utcnow().isoformat()
        
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
            'session_id': session_id,
            'crisis_detected': True,
            'confirmation_required': True,
            'confirmation_message': "Would you like emergency contact information?"
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Server error',
            'message': str(e)
        }), 500





#------------------------------------------------------------------------------
# SECTION 3: CRISIS SUPPORT RELATED CODE
#------------------------------------------------------------------------------

# Crisis detection keywords - grouped by category for better maintainability
CRISIS_KEYWORDS = {
    'suicide': [r'\bsuicide\b', r'\bkill myself\b', r'\bend my life\b', r'\bwant to die\b'],
    'self_harm': [r'\bharming myself\b', r'\bself-harm\b', r'\bself harm\b', r'\bhurt myself\b'],
    'general': [r'\bemergency\b', r'\bhelp me\b', r'\bhopeless\b', r'\bno reason to live\b',
               r'\bcan\'t go on\b', r'\bwant to end it\b', r'\bgive up\b']
}

# India-specific Crisis resources
INDIA_CRISIS_RESOURCES = {
    'emergency_services': {
        'number': '112',
        'description': 'National Emergency Number for immediate emergencies'
    },
    'crisis_hotlines': [
        {
            'name': 'AASRA',
            'number': '91-9820466726',
            'description': '24/7 crisis support and suicide prevention',
            'website': 'http://www.aasra.info/'
        },
        {
            'name': 'Vandrevala Foundation',
            'number': '1860-2662-345 / 1800-2333-330',
            'description': '24/7 helpline for mental health emergencies',
            'website': 'https://www.vandrevalafoundation.com/'
        },
        {
            'name': 'NIMHANS Psychosocial Support Helpline',
            'number': '080-46110007',
            'description': 'Mental health support and counseling',
            'website': 'https://nimhans.ac.in/'
        },
        {
            'name': 'iCall Helpline',
            'number': '022-25521111',
            'description': 'Psychosocial helpline (Mon-Sat, 8 AM to 10 PM)',
            'website': 'https://icallhelpline.org/'
        }
    ],
    'online_resources': [
        {
            'name': 'The Live Love Laugh Foundation',
            'website': 'https://www.thelivelovelaughfoundation.org/',
            'description': 'Mental health resources and support'
        },
        {
            'name': 'YourDost',
            'website': 'https://yourdost.com/',
            'description': 'Online counseling and emotional wellness platform'
        }
    ]
}

# Crisis response templates - centralized for easier maintenance
CRISIS_RESPONSES = {
    'suicide': ("I'm deeply concerned about what you're sharing. Your life matters, and these feelings, " 
               "while overwhelming, can be addressed with proper support. Please know that help is available, " 
               "and many people have overcome similar feelings with professional assistance. " 
               "Would you be willing to reach out to a Crisis helpline right now?"),
    
    'self_harm': ("I understand you're in a lot of pain right now. Self-harm is often a way to cope with " 
                 "emotional distress, but there are healthier alternatives that can help. Professional support " 
                 "can provide immediate relief and long-term strategies. Your wellbeing matters, and " 
                 "recovery is possible with the right help."),
    
    'general': ("I'm concerned about what you're sharing and want you to know that support is available. " 
               "While I'm here to listen, connecting with mental health professionals can provide the " 
               "specialized help you deserve. You don't have to face these feelings alone, and " 
               "reaching out is a sign of strength, not weakness.")
}

def detect_crisis_message(message):
    """
    Detect if a message contains Crisis-related keywords.
    
    Args:
        message (str): The user message to check
        
    Returns:
        tuple: (bool, str) - (is_crisis, category)
    """
    message = message.lower()
    
    # Check each category of keywords
    for category, patterns in CRISIS_KEYWORDS.items():
        for pattern in patterns:
            if re.search(pattern, message):
                return True, category
    
    return False, None

def generate_crisis_response(message):
    """
    Generate a supportive response for Crisis messages.
    
    Args:
        message (str): The user's crisis message
        
    Returns:
        str: A supportive response
    """
    # Detect the specific Crisis category
    is_crisis, category = detect_crisis_message(message)
    
    if not is_crisis:
        return CRISIS_RESPONSES['general']
    
    # Return the appropriate response based on the category
    return CRISIS_RESPONSES.get(category, CRISIS_RESPONSES['general'])


# Crisis contact information stored directly in the file
CRISIS_CONTACTS = [
    {
        'id': 'emergency_112',
        'type': 'emergency',
        'name': 'National Emergency Number',
        'number': '112',
        'description': 'National Emergency Number for immediate emergencies',
        'availability': '24/7',
        'country': 'India',
        'priority': 1
    },
    {
        'id': 'aasra',
        'type': 'crisis_hotline',
        'name': 'AASRA',
        'number': '91-9820466726',
        'description': '24/7 crisis support and suicide prevention',
        'website': 'http://www.aasra.info/',
        'availability': '24/7',
        'country': 'India',
        'priority': 2
    },
    {
        'id': 'vandrevala',
        'type': 'crisis_hotline',
        'name': 'Vandrevala Foundation',
        'number': '1860-2662-345 / 1800-2333-330',
        'description': '24/7 helpline for mental health emergencies',
        'website': 'https://www.vandrevalafoundation.com/',
        'availability': '24/7',
        'country': 'India',
        'priority': 3
    },
    {
        'id': 'nimhans',
        'type': 'crisis_hotline',
        'name': 'NIMHANS Psychosocial Support Helpline',
        'number': '080-46110007',
        'description': 'Mental health support and counseling',
        'website': 'https://nimhans.ac.in/',
        'availability': 'Business hours',
        'country': 'India',
        'priority': 4
    },
    {
        'id': 'icall',
        'type': 'crisis_hotline',
        'name': 'iCall Helpline',
        'number': '022-25521111',
        'description': 'Psychosocial helpline (Mon-Sat, 8 AM to 10 PM)',
        'website': 'https://icallhelpline.org/',
        'availability': 'Mon-Sat, 8 AM to 10 PM',
        'country': 'India',
        'priority': 5
    }
]