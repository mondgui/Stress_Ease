"""Mood endpoints: log, history, trends, and insights."""

from flask import Blueprint, request, jsonify
from stressease.services.auth_service import token_required
from stressease.services.firebase_service import save_mood_log, get_mood_history, get_user_profile
from stressease.services.gemini_service import analyze_mood_from_quiz
from datetime import datetime, date

# Create the mood blueprint
mood_bp = Blueprint('mood', __name__)


# ******************************************************************************
# * POST /api/mood/log - Submit mood quiz and get AI analysis
# ******************************************************************************
@mood_bp.route('/log', methods=['POST'])
@token_required
def log_mood(user_id):
    """
    Submit a mood quiz and get AI analysis.
    
    Expected JSON payload:
    {
        "quiz_answers": {
            "How are you feeling today?": "anxious",
            "Rate your stress level (1-10)": 7,
            "How well did you sleep last night?": "poorly",
            "What's your energy level?": "low",
            "Any specific concerns today?": "work deadline"
        },
        "additional_notes": "Had a difficult meeting today"
    }
    
    Returns:
        JSON response with mood analysis and log entry ID
    """
    try:
        # Get JSON data from request
        mood_data = request.get_json()
        
        if not mood_data:
            return jsonify({
                'success': False,
                'error': 'Invalid request',
                'message': 'JSON data is required'
            }), 400
        
        # Validate required fields
        if 'quiz_answers' not in mood_data:
            return jsonify({
                'success': False,
                'error': 'Missing required field',
                'message': 'quiz_answers is required'
            }), 400
        
        quiz_answers = mood_data['quiz_answers']
        
        if not isinstance(quiz_answers, dict) or len(quiz_answers) == 0:
            return jsonify({
                'success': False,
                'error': 'Invalid quiz_answers',
                'message': 'quiz_answers must be a non-empty object'
            }), 400
        
        # Get user's health context for personalized analysis
        user_profile = get_user_profile(user_id)
        user_context = None
        
        if user_profile:
            user_context = {
                'age': user_profile.get('age'),
                'health_conditions': user_profile.get('health_conditions', []),
                'stress_triggers': user_profile.get('stress_triggers', []),
                'goals': user_profile.get('goals', [])
            }
        
        # Analyze mood using Gemini AI
        analysis_result = analyze_mood_from_quiz(quiz_answers, user_context)
        
        if not analysis_result:
            return jsonify({
                'success': False,
                'error': 'Analysis failed',
                'message': 'Unable to analyze mood at this time. Please try again.'
            }), 500
        
        # Prepare mood log data
        mood_log_data = {
            'quiz_answers': quiz_answers,
            'analysis': analysis_result,
            'date': date.today().isoformat(),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Add additional notes if provided
        if 'additional_notes' in mood_data and mood_data['additional_notes']:
            mood_log_data['additional_notes'] = mood_data['additional_notes']
        
        # Save mood log to Firestore
        log_id = save_mood_log(user_id, mood_log_data)
        
        if log_id:
            return jsonify({
                'success': True,
                'message': 'Mood logged successfully',
                'log_id': log_id,
                'analysis': analysis_result
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'Database error',
                'message': 'Failed to save mood log'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Server error',
            'message': str(e)
        }), 500


# ******************************************************************************
# * GET /api/mood/history - Get recent mood entries
# ******************************************************************************
@mood_bp.route('/history', methods=['GET'])
@token_required
def get_history(user_id):
    """
    Get the user's mood history.
    
    Query parameters:
    - limit: Number of entries to retrieve (default: 30, max: 100)
    
    Returns:
        JSON response with mood history entries
    """
    try:
        # Get limit from query parameters
        limit = request.args.get('limit', 30, type=int)
        
        # Validate limit
        if limit < 1:
            limit = 30
        elif limit > 100:
            limit = 100
        
        # Retrieve mood history from Firestore
        mood_entries = get_mood_history(user_id, limit)
        
        return jsonify({
            'success': True,
            'mood_history': mood_entries,
            'count': len(mood_entries)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve mood history',
            'message': str(e)
        }), 500


# ******************************************************************************
# * GET /api/mood/trends - Get mood trends and statistics over time
# ******************************************************************************
@mood_bp.route('/trends', methods=['GET'])
@token_required
def get_mood_trends(user_id):
    """
    Get mood trends and statistics for the user.
    
    Query parameters:
    - days: Number of days to analyze (default: 30, max: 90)
    
    Returns:
        JSON response with mood trends and statistics
    """
    try:
        # Get days from query parameters
        days = request.args.get('days', 30, type=int)
        
        # Validate days
        if days < 7:
            days = 7
        elif days > 90:
            days = 90
        
        # Retrieve mood history
        mood_entries = get_mood_history(user_id, days)
        
        if not mood_entries:
            return jsonify({
                'success': True,
                'message': 'No mood data available for trend analysis',
                'trends': None
            }), 200
        
        # Calculate trends and statistics
        trends = _calculate_mood_trends(mood_entries, days)
        
        return jsonify({
            'success': True,
            'trends': trends,
            'period_days': days,
            'entries_analyzed': len(mood_entries)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Failed to calculate mood trends',
            'message': str(e)
        }), 500


# ******************************************************************************
# * GET /api/mood/insights - Get AI-powered mood insights and tips
# ******************************************************************************
@mood_bp.route('/insights', methods=['GET'])
@token_required
def get_mood_insights(user_id):
    """
    Get personalized mood insights based on recent history.
    
    Returns:
        JSON response with personalized insights and recommendations
    """
    try:
        # Retrieve recent mood history (last 14 days)
        recent_entries = get_mood_history(user_id, 14)
        
        if not recent_entries:
            return jsonify({
                'success': True,
                'message': 'No recent mood data available for insights',
                'insights': None
            }), 200
        
        # Generate insights
        insights = _generate_mood_insights(recent_entries)
        
        return jsonify({
            'success': True,
            'insights': insights
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Failed to generate mood insights',
            'message': str(e)
        }), 500


def _calculate_mood_trends(mood_entries, days):
    """
    Calculate mood trends and statistics from mood entries.
    
    Args:
        mood_entries (list): List of mood log entries
        days (int): Number of days being analyzed
        
    Returns:
        dict: Trends and statistics
    """
    if not mood_entries:
        return None
    
    # Extract mood scores and stress levels
    mood_scores = []
    stress_levels = []
    mood_categories = []
    primary_emotions = []
    
    for entry in mood_entries:
        analysis = entry.get('analysis', {})
        
        if 'mood_score' in analysis:
            mood_scores.append(analysis['mood_score'])
        
        if 'stress_level' in analysis:
            stress_levels.append(analysis['stress_level'])
        
        if 'mood_category' in analysis:
            mood_categories.append(analysis['mood_category'])
        
        if 'primary_emotions' in analysis:
            primary_emotions.extend(analysis['primary_emotions'])
    
    # Calculate averages
    avg_mood_score = sum(mood_scores) / len(mood_scores) if mood_scores else 0
    avg_stress_level = sum(stress_levels) / len(stress_levels) if stress_levels else 0
    
    # Calculate mood category distribution
    mood_category_counts = {}
    for category in mood_categories:
        mood_category_counts[category] = mood_category_counts.get(category, 0) + 1
    
    # Calculate most common emotions
    emotion_counts = {}
    for emotion in primary_emotions:
        emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
    
    # Sort emotions by frequency
    top_emotions = sorted(emotion_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Calculate trend direction (comparing first half vs second half)
    if len(mood_scores) >= 4:
        mid_point = len(mood_scores) // 2
        first_half_avg = sum(mood_scores[:mid_point]) / mid_point
        second_half_avg = sum(mood_scores[mid_point:]) / (len(mood_scores) - mid_point)
        
        if second_half_avg > first_half_avg + 0.5:
            trend_direction = 'improving'
        elif second_half_avg < first_half_avg - 0.5:
            trend_direction = 'declining'
        else:
            trend_direction = 'stable'
    else:
        trend_direction = 'insufficient_data'
    
    return {
        'average_mood_score': round(avg_mood_score, 1),
        'average_stress_level': round(avg_stress_level, 1),
        'trend_direction': trend_direction,
        'mood_category_distribution': mood_category_counts,
        'top_emotions': [{'emotion': emotion, 'count': count} for emotion, count in top_emotions],
        'total_entries': len(mood_entries),
        'analysis_period': f'{days} days'
    }


def _generate_mood_insights(recent_entries):
    """
    Generate personalized insights from recent mood entries.
    
    Args:
        recent_entries (list): Recent mood log entries
        
    Returns:
        dict: Personalized insights and recommendations
    """
    if not recent_entries:
        return None
    
    # Analyze recent patterns
    recent_mood_scores = []
    recent_stress_levels = []
    warning_signs = []
    
    for entry in recent_entries:
        analysis = entry.get('analysis', {})
        
        if 'mood_score' in analysis:
            recent_mood_scores.append(analysis['mood_score'])
        
        if 'stress_level' in analysis:
            recent_stress_levels.append(analysis['stress_level'])
        
        if 'warning_signs' in analysis and analysis['warning_signs']:
            warning_signs.extend(analysis['warning_signs'])
    
    # Generate insights
    insights = []
    recommendations = []
    
    # Mood score insights
    if recent_mood_scores:
        avg_recent_mood = sum(recent_mood_scores) / len(recent_mood_scores)
        
        if avg_recent_mood >= 7:
            insights.append("Your mood has been consistently positive recently. Keep up the great work!")
        elif avg_recent_mood >= 5:
            insights.append("Your mood has been fairly stable. Consider focusing on activities that bring you joy.")
        else:
            insights.append("Your mood has been lower than usual. It might be helpful to reach out for support.")
            recommendations.append("Consider speaking with a mental health professional")
    
    # Stress level insights
    if recent_stress_levels:
        avg_recent_stress = sum(recent_stress_levels) / len(recent_stress_levels)
        
        if avg_recent_stress >= 7:
            insights.append("Your stress levels have been high recently. Prioritizing stress management is important.")
            recommendations.extend([
                "Practice deep breathing exercises",
                "Try progressive muscle relaxation",
                "Consider reducing your workload if possible"
            ])
        elif avg_recent_stress >= 4:
            insights.append("Your stress levels are moderate. Regular stress management can help maintain balance.")
            recommendations.extend([
                "Maintain a regular exercise routine",
                "Practice mindfulness or meditation"
            ])
    
    # Warning signs
    if warning_signs:
        unique_warnings = list(set(warning_signs))
        insights.append(f"Some concerning patterns have been noted: {', '.join(unique_warnings)}")
        recommendations.append("Consider reaching out to a mental health professional for support")
    
    # General recommendations
    if not recommendations:
        recommendations = [
            "Continue monitoring your mood regularly",
            "Maintain healthy sleep habits",
            "Stay connected with supportive friends and family"
        ]
    
    return {
        'insights': insights,
        'recommendations': recommendations[:5],  # Limit to 5 recommendations
        'based_on_entries': len(recent_entries),
        'generated_at': datetime.utcnow().isoformat()
    }