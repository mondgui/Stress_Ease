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
        
        # Initialize the model (using gemini-pro for text generation)
        model = genai.GenerativeModel('gemini-pro')
        
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
    
    # Check for crisis-related content
    crisis_keywords = ['suicide', 'self-harm', 'kill yourself', 'end it all', 'hurt myself', 'die']
    for keyword in crisis_keywords:
        if keyword in response_lower:
            return """I notice you're mentioning something serious. If you're experiencing a crisis, please reach out to a professional immediately. The National Suicide Prevention Lifeline is available 24/7 at 988 or 1-800-273-8255. Would you like me to provide more resources that might help?"""
    
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
If a user expresses thoughts of self-harm, suicide, or mentions being in immediate danger, you must immediately and gently pivot the conversation to recommend professional help. Your response should include: 'It sounds like you are going through a lot right now, and it's brave of you to share that. For immediate support, I strongly encourage you to connect with a crisis hotline or mental health professional. You can access crisis resources through the app's crisis support section.'

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


def generate_chat_title(transcript: str) -> Optional[str]:
    """
    Create a short, descriptive title for a chat session.
    
    Args:
        transcript: The full conversation transcript as a string
    
    Returns:
        A short title (3-5 words) or None if error occurs
    """
    if model is None:
        raise RuntimeError("Gemini AI has not been initialized. Call init_gemini() first.")
    
    try:
        # Build specific prompt for title generation
        prompt = f"""Read this conversation and generate a short, descriptive title (3-5 words max). 
Examples: 'Struggling with Work Stress', 'A Positive Day', 'Managing Anxiety Today', 'Family Relationship Issues'.
Respond with only the title, no quotes or additional text.

Conversation:
{transcript}

Title:"""

        # Generate title with focused configuration
        generation_config = {
            "max_output_tokens": 20,   # Very short response
            "temperature": 0.3,        # More focused/consistent
            "top_p": 0.8,             # Less randomness
            "top_k": 20               # Fewer token choices
        }
        
        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        title = response.text.strip()
        
        # Basic validation - ensure it's not too long and remove quotes if present
        if len(title) > 50:  # Fallback if too long
            title = title[:47] + "..."
        
        # Remove quotes if AI added them
        title = title.strip('"\'')
        
        return title if title else "Chat Session"
        
    except Exception as e:
        print(f"Error generating chat title: {str(e)}")
        return "Chat Session"


def _build_chat_response_prompt(user_message: str, chat_history: List[Dict[str, str]], user_context: Optional[Dict[str, Any]] = None) -> str:
    """Build a prompt for generating contextual chat responses."""
    prompt = """
CORE IDENTITY:
You are StressBot, an AI companion from the StressEase app. Your primary purpose is to provide a supportive, non-judgmental space for users to express their feelings.

TONE AND LANGUAGE:
Your tone must always be warm, patient, and empathetic. Use simple, clear language. Avoid clinical jargon. Validate the user's feelings first (e.g., 'That sounds really tough,' or 'It makes sense that you feel that way') before offering gentle guidance.

CRITICAL SAFETY BOUNDARY:
You are NOT a licensed therapist or a medical professional. You are strictly forbidden from diagnosing any condition, prescribing medication, or giving medical advice. Your role is that of a supportive peer.

CRISIS INTERVENTION PROTOCOL:
If a user expresses thoughts of self-harm or mentions being in a crisis, you must immediately and gently pivot the conversation to recommend professional help. Your response in this case should be a variation of: 'It sounds like you are going through a lot right now, and it's brave of you to share that. For immediate support, I strongly encourage you to connect with a crisis hotline or a mental health professional.' You will then provide the resources.

BREVITY AND ENGAGEMENT:
Keep your responses concise and easy to digest. Aim for 2-4 sentences.
To encourage the user to reflect and share more, end your responses with a gentle, open-ended question when appropriate. For example, instead of 'Did you have a bad day?', ask 'What was on your mind today?'

PRACTICAL GUIDANCE:
- Provide practical coping strategies and mental health tips when appropriate
- Encourage professional help when needed
- Use a conversational, supportive tone
"""
    
    # Add user context if available
    if user_context:
        prompt += "\nUSER CONTEXT:\n"
        if 'name' in user_context:
            prompt += f"- Name: {user_context['name']}\n"
        if 'age' in user_context:
            prompt += f"- Age: {user_context['age']}\n"
        if 'health_conditions' in user_context:
            prompt += f"- Health conditions: {user_context['health_conditions']}\n"
        if 'stress_triggers' in user_context:
            prompt += f"- Known stress triggers: {user_context['stress_triggers']}\n"
        if 'goals' in user_context:
            prompt += f"- Personal goals: {user_context['goals']}\n"
    
    # Add chat history for context
    if chat_history:
        prompt += "\nCONVERSATION HISTORY:\n"
        for message in chat_history[-5:]:  # Include last 5 messages for context
            role = message.get('role', 'user')
            content = message.get('content', '')
            prompt += f"{role.capitalize()}: {content}\n"
    
    prompt += f"\nUSER'S CURRENT MESSAGE: {user_message}\n\n"
    prompt += "Please provide a supportive and helpful response:"
    
    return prompt


def summarize_conversation(transcript: str) -> Optional[str]:
    """
    Generate a detailed summary of a conversation using Gemini AI.
    
    Args:
        transcript: The full conversation transcript as a string
    
    Returns:
        A detailed paragraph summary or None if error occurs
    """
    if model is None:
        raise RuntimeError("Gemini AI has not been initialized. Call init_gemini() first.")
    
    try:
        # Build specific prompt for detailed summarization
        prompt = f"""Summarize this mental health conversation. Detail the key topics, the user's primary emotions, and any strategies that were discussed.

Provide a comprehensive paragraph that captures:
- Main concerns or issues the user shared
- Emotional state and progression throughout the conversation
- Coping strategies, advice, or insights that were discussed
- Overall tone and outcome of the conversation

Conversation:
{transcript}

Summary:"""

        # Generate summary with appropriate configuration
        generation_config = {
            "max_output_tokens": 300,  # Allow for detailed summary
            "temperature": 0.5,        # Balanced creativity for good summarization
            "top_p": 0.9,             # Good token diversity
            "top_k": 40               # Reasonable variety
        }
        
        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        return response.text.strip()
        
    except Exception as e:
        print(f"Error summarizing conversation with Gemini: {str(e)}")
        return None


def _build_summarization_prompt(chat_messages: List[Dict[str, str]]) -> str:
    """Build a prompt for conversation summarization."""
    prompt = """You are tasked with summarizing a mental health support conversation from the StressEase app. Create a concise summary that captures:

1. Main topics discussed
2. User's primary concerns or emotions
3. Key advice or strategies provided
4. Overall tone and progression of the conversation

CONVERSATION TO SUMMARIZE:
"""
    
    for message in chat_messages:
        role = message.get('role', 'user')
        content = message.get('content', '')
        prompt += f"{role.capitalize()}: {content}\n"
    
    prompt += """
Please provide a summary in 2-3 sentences that would be useful for future reference. Focus on the most important aspects of the conversation."""
    
    return prompt


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