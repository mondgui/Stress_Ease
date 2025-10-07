"""Gemini helpers: mood analysis, chat replies, and conversation summaries."""

import google.generativeai as genai
from typing import Dict, List, Optional, Any
import json


# Global Gemini model
model = None

# Global in-memory session cache for active conversations
active_chat_sessions = {}

#------------------------------------------------------------------------------
# Initialization and Utility Functions
#------------------------------------------------------------------------------

def init_gemini(api_key: str):
    """Initialize Google Gemini AI with the API key."""
    global model
    
    try:
        # Configure Gemini with API key
        genai.configure(api_key=api_key)
        
        # Initialize the model 
        model = genai.GenerativeModel('gemini-2.0-flash-lite')
        
        print("Google Gemini AI initialized successfully")
        
    except Exception as e:
        print(f"Failed to initialize Gemini AI: {str(e)}")
        raise


def get_gemini_model():
    """Get the Gemini model instance."""
    if model is None:
        raise RuntimeError("Gemini AI has not been initialized. Call init_gemini() first.")
    return model


def validate_gemini_response(response: str) -> Optional[str]:
    """
    Validate that a Gemini response is appropriate and safe.
    Returns the original response if valid, a safe alternative if invalid, or None if empty.
    """
    if not response or len(response.strip()) == 0:
        return None
    
    response_lower = response.lower()
    
    # Check for crisis-related content in AI response
    crisis_keywords = ['suicide', 'self-harm', 'kill yourself', 'end it all', 'hurt myself', 'die']
    for keyword in crisis_keywords:
        if keyword in response_lower:
            return """I notice this is a serious topic. If you're experiencing a Crisis, please tap the red 'SOS' button in the chat to connect with professional Crisis resources immediately. How can I support you right now?"""
    
    # Check for diagnosis language violations
    diagnosis_patterns = [
        'you have ', 'you are suffering from', 'you might have', 'you probably have',
        'sounds like you have', 'diagnosis', 'diagnose', 'condition is', 'disorder',
        'i diagnose', 'you exhibit symptoms of', 'clinical depression', 'clinical anxiety',
        'you are experiencing', 'you are exhibiting', 'pathological', 'psychiatric condition'
    ]
    
    for pattern in diagnosis_patterns:
        if pattern in response_lower:
            return """I'm here to listen and support you, but I can't provide medical diagnoses or clinical advice. Consider discussing your feelings with a healthcare professional who can provide personalized guidance. How else can I support you today?"""
    
    # Check for medication/treatment advice
    medication_patterns = [
        'you should take', 'you need to take', 'prescribe', 'medication', 'dosage',
        'you should try', 'treatment plan', 'medical treatment', 'therapy regimen'
    ]
    
    for pattern in medication_patterns:
        if pattern in response_lower:
            return """I'm here to provide emotional support, but I can't recommend specific treatments or medications. A healthcare professional would be the best person to discuss treatment options with you. Is there something else on your mind that you'd like to talk about?"""
    
    return response


def find_crisis_resources(country: str) -> Optional[Dict[str, Any]]:
    """
    Generate country-specific Crisis resources using Gemini AI.
    
    Args:
        country (str): Country code or name to find resources for
        
    Returns:
        dict: Structured crisis resources for the specified country, or None if generation fails
    """
    if model is None:
        raise RuntimeError("Gemini AI has not been initialized. Call init_gemini() first.")
    
    try:
        # Normalize country input
        country_input = country.strip()
        
        # Build prompt for Gemini
        prompt = f"""
Generate a comprehensive list of mental health Crisis resources for {country_input}.

The response MUST be in valid JSON format with the following structure:
{{
  "emergency_services": {{
    "number": "string",  // Primary emergency number
    "description": "string"  // Brief description without any backticks or markdown
  }},
  "crisis_hotlines": [
    {{
      "name": "string",  // Organization name
      "number": "string",  // Phone number with country code
      "description": "string",  // Brief description of services without any backticks or markdown
      "website": "string"  // Website URL without any backticks or markdown
    }}
  ],
  "online_resources": [
    {{
      "name": "string",  // Organization name
      "description": "string",  // Brief description of services
      "website": "string"  // Website URL
    }}
  ]
}}

Include ONLY verified, legitimate resources. Include at least one emergency service, 2-5 crisis hotlines, and 2-5 online resources.
Ensure all phone numbers include the country code. Provide accurate, up-to-date information.
"""
        
        # Generate response from Gemini
        response = model.generate_content(prompt)
        response_text = response.text
        
        # Extract JSON from response
        try:
            # First try direct JSON parsing
            resources = json.loads(response_text)
        except json.JSONDecodeError:
            # If that fails, try to extract JSON using regex
            import re
            json_match = re.search(r'({[\s\S]*})', response_text)
            if not json_match:
                print(f"Error: No JSON found in Gemini response for country {country}")
                return None
                
            try:
                json_str = json_match.group(1)
                resources = json.loads(json_str)
            except (json.JSONDecodeError, IndexError) as e:
                print(f"Error: Failed to parse extracted JSON for country {country}: {str(e)}")
                return None
        
        # Validate the structure
        if not isinstance(resources, dict):
            print(f"Error: Gemini response is not a dictionary for country {country}")
            return None
            
        # Ensure required fields are present
        if 'emergency_services' not in resources or 'crisis_hotlines' not in resources or 'online_resources' not in resources:
            print(f"Error: Missing required fields in Gemini response for country {country}")
            return None
        
        # Clean up website URLs - remove backticks and markdown formatting
        if 'crisis_hotlines' in resources:
            for hotline in resources['crisis_hotlines']:
                if 'website' in hotline:
                    # Remove backticks and extra spaces
                    hotline['website'] = hotline['website'].replace('`', '').strip()
        
        if 'online_resources' in resources:
            for resource in resources['online_resources']:
                if 'website' in resource:
                    # Remove backticks and extra spaces
                    resource['website'] = resource['website'].replace('`', '').strip()
            
        return resources
        
    except Exception as e:
        print(f"Error generating crisis resources for {country}: {str(e)}")
        return None


#------------------------------------------------------------------------------
# Chat Functions
#------------------------------------------------------------------------------

def start_chat_session(user_profile: Dict[str, Any]):
    """
    Initialize a stateful conversation with Gemini.
    
    Args:
        user_profile: Dictionary containing user information (name, stressors, goals, etc.)
    
    Returns:
        ChatSession object for stateful conversation
    """
    if model is None:
        raise RuntimeError("Gemini AI has not been initialized. Call init_gemini() first.")
    
    # Build the Master Prompt with comprehensive persona and user context
    master_prompt = """
CORE IDENTITY:
You are StressBot, an AI companion from the StressEase app. Your primary purpose is to provide a supportive, non-judgmental space for users to express their feelings and work through stress and emotional challenges.

TONE AND LANGUAGE:
Your tone must always be warm, patient, and empathetic. Use simple, clear language that feels conversational and human. Avoid clinical jargon or overly formal language. Always validate the user's feelings first (e.g., 'That sounds really tough,' or 'It makes sense that you feel that way') before offering gentle guidance.

CRITICAL SAFETY BOUNDARY:
You are NOT a licensed therapist, psychologist, psychiatrist, or medical professional. You are strictly forbidden from:
- Diagnosing any mental health condition or disorder
- Prescribing medication or medical treatments
- Providing medical advice or recommendations
- Making clinical assessments or evaluations
Your role is that of a supportive peer and emotional companion.

CRISIS INTERVENTION PROTOCOL:
Tool Awareness: You must be aware that the user has a visible red 'SOS' button on their chat screen. This button gives them immediate access to a list of professional crisis helplines for their country.

Severity Detection Guidelines:
1. HIGH SEVERITY (Immediate Danger): Explicit mentions of current suicidal intent, active self-harm, specific suicide plans, or statements indicating imminent harm to self or others. Examples: "I'm going to end it all tonight", "I have the pills right here", "I can't take it anymore and have my plan ready".
2. MEDIUM SEVERITY (Acute Distress): Expressions of suicidal ideation without specific plans, severe hopelessness, or statements suggesting the person is in a mental health crisis. Examples: "I don't see a point in living", "Everyone would be better off without me", "I keep thinking about hurting myself".
3. LOW SEVERITY (Concerning Language): General expressions of despair, feeling overwhelmed, or vague references to not wanting to continue. Examples: "I don't know how much longer I can do this", "Nothing matters anymore".

Action Protocol Based on Severity:
- For HIGH SEVERITY: Respond with urgency and clarity. Your response must:
  Part 1 (Brief Validation): "I'm deeply concerned about what you're sharing right now, and your safety is the absolute priority."
  Part 2 (Direct Intervention): "Please immediately tap the red 'SOS' button on your screen to connect with crisis professionals who can help you right now. This is an emergency situation that requires immediate professional support."

- For MEDIUM SEVERITY: Respond with serious concern:
  Part 1 (Empathetic Validation): "What you're going through sounds incredibly painful, and I'm genuinely concerned about your wellbeing right now."
  Part 2 (Strong Redirection): "I strongly encourage you to tap the red 'SOS' button on your screen to speak with trained professionals who can provide the support you need during this difficult time."

- For LOW SEVERITY: Respond with care:
  Part 1 (Supportive Validation): "It sounds like you're going through a really tough time, and I'm sorry you're experiencing this pain."
  Part 2 (Gentle Guidance): "If these feelings are overwhelming, please consider tapping the red 'SOS' button to connect with supportive resources that can help."

CRITICAL: Always err on the side of caution. If you're uncertain about the severity level, respond as if it were a higher severity situation. Never minimize or downplay concerning language.
CONVERSATION STYLE:
- Keep responses concise and digestible (2-4 sentences maximum)
- Be genuinely curious about the user's experience
- Ask thoughtful, open-ended questions to encourage reflection
- Use active listening techniques in your responses
- Provide practical coping strategies when appropriate
- Encourage professional help when situations warrant it

PERSONALIZATION GUIDELINES:
Use the following user context to personalize your responses appropriately, but don't overwhelm them by mentioning everything at once."""

    # Add user profile context to the master prompt
    if user_profile:
        master_prompt += "\n\nUSER PROFILE CONTEXT:\n"
        if 'name' in user_profile:
            master_prompt += f"- Name: {user_profile['name']}\n"
        if 'age' in user_profile:
            master_prompt += f"- Age: {user_profile['age']}\n"
        if 'health_conditions' in user_profile and user_profile['health_conditions']:
            master_prompt += f"- Health considerations: {', '.join(user_profile['health_conditions'])}\n"
        if 'stress_triggers' in user_profile and user_profile['stress_triggers']:
            master_prompt += f"- Known stress triggers: {', '.join(user_profile['stress_triggers'])}\n"
        if 'goals' in user_profile and user_profile['goals']:
            master_prompt += f"- Personal goals: {', '.join(user_profile['goals'])}\n"

    master_prompt += "\n\nRemember: Be supportive, concise, and always prioritize the user's emotional safety."

    try:
        # Start the stateful chat session with the master prompt
        chat_session = model.start_chat(history=[
            {
                "role": "user",
                "parts": [master_prompt]
            },
            {
                "role": "model", 
                "parts": ["I understand. I'm here to provide supportive, empathetic conversation while maintaining appropriate boundaries. I'm ready to help you work through whatever is on your mind today."]
            }
        ])
        
        return chat_session
        
    except Exception as e:
        print(f"Error starting chat session: {str(e)}")
        raise


def generate_chat_response(chat_session, new_message: str) -> Optional[str]:
    """
    Handle subsequent messages in an existing stateful conversation.
    
    Args:
        chat_session: The active ChatSession object from the cache
        new_message: The user's new message text
    
    Returns:
        The AI's response text or None if error occurs
    """
    try:
        # Send message to the stateful chat session and get response
        response = chat_session.send_message(new_message)
        
        # Validate the response for safety and appropriateness
        raw_response = response.text.strip()
        validated_response = validate_gemini_response(raw_response)
        
        # If validation failed and returned None, provide a fallback response
        if validated_response is None:
            return "I'm sorry, I couldn't generate a helpful response. How else can I support you today?"
            
        return validated_response
        
    except Exception as e:
        print(f"Error generating chat response with Gemini: {str(e)}")
        return "I'm having trouble connecting right now. Could we try again in a moment?"


#------------------------------------------------------------------------------
# Mood Analysis Functions
#------------------------------------------------------------------------------

def analyze_mood_from_quiz(quiz_answers: Dict[str, Any], user_context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Analyze mood from quiz answers using Gemini AI."""
    try:
        # Construct the prompt for mood analysis
        prompt = _build_mood_analysis_prompt(quiz_answers, user_context)
        
        # Generate response from Gemini
        response = model.generate_content(prompt)
        
        # Parse the response
        analysis_result = _parse_mood_analysis_response(response.text)
        
        return analysis_result
        
    except Exception as e:
        print(f"Error analyzing mood with Gemini: {str(e)}")
        return None


def _build_mood_analysis_prompt(quiz_answers: Dict[str, Any], user_context: Optional[Dict[str, Any]] = None) -> str:
    """Build a comprehensive prompt for mood analysis."""
    prompt = """You are a professional mental health AI assistant for the StressEase app. Analyze the following mood quiz responses and provide a comprehensive assessment.

QUIZ RESPONSES:
"""
    
    # Add quiz answers to prompt
    for question, answer in quiz_answers.items():
        prompt += f"- {question}: {answer}\n"
    
    # Add user context if available
    if user_context:
        prompt += f"\nUSER CONTEXT:\n"
        if 'age' in user_context:
            prompt += f"- Age: {user_context['age']}\n"
        if 'health_conditions' in user_context:
            prompt += f"- Health conditions: {user_context['health_conditions']}\n"
        if 'stress_triggers' in user_context:
            prompt += f"- Known stress triggers: {user_context['stress_triggers']}\n"
    
    prompt += """
ANALYSIS REQUIREMENTS:
Please provide your analysis in the following JSON format:

{
    "mood_score": <integer from 1-10, where 1 is very poor mood and 10 is excellent mood>,
    "mood_category": "<one of: excellent, good, fair, poor, very_poor>",
    "primary_emotions": ["<list of 2-3 primary emotions detected>"],
    "stress_level": <integer from 1-10, where 1 is no stress and 10 is extreme stress>,
    "insights": "<2-3 sentences explaining the mood analysis>",
    "recommendations": [
        "<3-5 specific, actionable recommendations for improving mood/managing stress>"
    ],
    "warning_signs": ["<list any concerning patterns or warning signs, empty array if none>"]
}

Ensure your response is valid JSON and provides empathetic, professional guidance."""
    
    return prompt


def _parse_mood_analysis_response(response_text: str) -> Dict[str, Any]:
    """Parse the mood analysis response from Gemini."""
    try:
        # Try to extract JSON from the response
        # Sometimes Gemini includes extra text around the JSON
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        
        if start_idx != -1 and end_idx != -1:
            json_str = response_text[start_idx:end_idx]
            return json.loads(json_str)
        else:
            # Fallback: create a basic structure if JSON parsing fails
            return {
                "mood_score": 5,
                "mood_category": "fair",
                "primary_emotions": ["mixed"],
                "stress_level": 5,
                "insights": "Unable to parse detailed analysis. Please try again.",
                "recommendations": ["Consider retaking the mood assessment"],
                "warning_signs": []
            }
            
    except json.JSONDecodeError:
        # Fallback response if JSON parsing fails
        return {
            "mood_score": 5,
            "mood_category": "fair",
            "primary_emotions": ["uncertain"],
            "stress_level": 5,
            "insights": "Analysis completed but formatting issue occurred.",
            "recommendations": ["Consider speaking with a mental health professional"],
            "warning_signs": []
        }