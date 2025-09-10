"""
Health-Aware Voice Responses

Provides health-aware voice responses and interactions
based on real-time health data from Samsung Health and Whoop.
"""

import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
import re

from .health_data_sync import HealthDataSync, HealthAlert

logger = logging.getLogger(__name__)

@dataclass
class HealthContext:
    """Context information for health-aware responses."""
    current_heart_rate: Optional[int] = None
    recovery_score: Optional[float] = None
    strain_score: Optional[float] = None
    sleep_hours_last_night: Optional[float] = None
    stress_level: Optional[int] = None
    recent_workout_intensity: Optional[float] = None
    active_alerts: List[str] = None
    time_of_day: str = ""
    user_state: str = "normal"  # normal, fatigued, stressed, recovering, emergency

class HealthAwareResponses:
    """Manages health-aware voice responses and interactions."""

    def __init__(self, health_sync: HealthDataSync):
        self.health_sync = health_sync
        self.response_templates = self._load_response_templates()
        self.health_keywords = self._load_health_keywords()

    def _load_response_templates(self) -> Dict[str, List[str]]:
        """Load response templates for different health states."""
        return {
            "fatigued": [
                "I notice you might be feeling tired. Would you like me to help you find a quiet place to rest?",
                "Your recovery score suggests you need some rest. Should I help you schedule a break?",
                "You seem fatigued. Would you like me to dim the lights or play some calming music?"
            ],
            "stressed": [
                "I can sense you're feeling stressed. Would you like me to guide you through a breathing exercise?",
                "Your stress levels are elevated. Should I play some relaxing music or help you with stress management techniques?",
                "You might benefit from a short break. Would you like me to set a reminder for you?"
            ],
            "high_heart_rate": [
                "Your heart rate is elevated. Would you like me to help you find a comfortable place to sit down?",
                "I notice your heart rate has increased. Should I contact someone or help you with relaxation techniques?",
                "Please take a moment to breathe deeply. Would you like me to guide you through it?"
            ],
            "low_energy": [
                "You seem to have low energy today. Would you like me to help you with some energizing activities?",
                "Based on your recent activity, you might need to recharge. Should I suggest some light exercises?",
                "Your energy levels are low. Would you like me to prepare a healthy snack suggestion?"
            ],
            "good_recovery": [
                "Great! Your recovery score looks good today. You're ready for an active day!",
                "Your body is well-recovered. This is a good time for more intense activities if you wish.",
                "Excellent recovery! You're in a great state for productive work today."
            ],
            "emergency": [
                "EMERGENCY: Your vital signs indicate you need immediate assistance. I'm contacting emergency services.",
                "CRITICAL: Your health metrics are concerning. Please sit down and I'll call for help.",
                "URGENT: I detect a medical emergency. Stay where you are while I contact emergency services."
            ]
        }

    def _load_health_keywords(self) -> Dict[str, List[str]]:
        """Load keywords that trigger health-aware responses."""
        return {
            "health_check": [
                "how am i feeling", "how do i feel", "my health", "check my health",
                "how's my recovery", "what's my recovery score", "how's my heart rate",
                "check my vitals", "my current health status"
            ],
            "stress_relief": [
                "i'm stressed", "feeling stressed", "reduce stress", "stress relief",
                "relaxation", "breathing exercise", "calm down", "anxious"
            ],
            "energy_boost": [
                "i'm tired", "feeling tired", "need energy", "boost my energy",
                "wake me up", "feeling sluggish", "low energy"
            ],
            "workout_suggestion": [
                "should i work out", "exercise suggestion", "what workout",
                "fitness activity", "physical activity"
            ],
            "sleep_advice": [
                "sleep better", "improve sleep", "sleep quality", "sleep advice",
                "how to sleep better"
            ]
        }

    def get_current_health_context(self) -> HealthContext:
        """Get current health context from synced data."""
        health_status = self.health_sync.get_current_health_status()

        context = HealthContext()
        context.current_heart_rate = health_status.get('heart_rate')
        context.recovery_score = health_status.get('recovery_score')
        context.strain_score = health_status.get('strain_score')
        context.sleep_hours_last_night = health_status.get('sleep_hours')
        context.stress_level = health_status.get('stress_level')
        context.active_alerts = [
            alert['type'] for alert in health_status.get('active_alerts', [])
        ]

        # Determine time of day
        now = datetime.now()
        hour = now.hour
        if 6 <= hour < 12:
            context.time_of_day = "morning"
        elif 12 <= hour < 17:
            context.time_of_day = "afternoon"
        elif 17 <= hour < 22:
            context.time_of_day = "evening"
        else:
            context.time_of_day = "night"

        # Determine user state based on health metrics
        context.user_state = self._determine_user_state(context)

        return context

    def _determine_user_state(self, context: HealthContext) -> str:
        """Determine user's current health state."""
        # Check for emergency conditions
        if (context.current_heart_rate and context.current_heart_rate > 120) or \
           (context.stress_level and context.stress_level > 90):
            return "emergency"

        # Check for high strain
        if (context.strain_score and context.strain_score > 17) or \
           (context.recovery_score and context.recovery_score < 33):
            return "fatigued"

        # Check for stress
        if context.stress_level and context.stress_level > 70:
            return "stressed"

        # Check for low energy
        if (context.sleep_hours_last_night and context.sleep_hours_last_night < 6) or \
           (context.recovery_score and context.recovery_score < 50):
            return "low_energy"

        # Check for good recovery
        if context.recovery_score and context.recovery_score > 67:
            return "good_recovery"

        return "normal"

    def get_health_aware_response(self, user_input: str) -> Optional[str]:
        """Generate health-aware response based on user input and current health state."""
        context = self.get_current_health_context()

        # Check for health-related keywords
        health_topic = self._identify_health_topic(user_input)

        if health_topic:
            return self._generate_topic_response(health_topic, context)

        # Check for health state-based responses
        if context.user_state != "normal":
            return self._get_state_based_response(context)

        return None

    def _identify_health_topic(self, user_input: str) -> Optional[str]:
        """Identify health-related topics from user input."""
        user_input_lower = user_input.lower()

        for topic, keywords in self.health_keywords.items():
            for keyword in keywords:
                if keyword in user_input_lower:
                    return topic

        return None

    def _generate_topic_response(self, topic: str, context: HealthContext) -> str:
        """Generate response for specific health topic."""
        if topic == "health_check":
            return self._generate_health_summary(context)
        elif topic == "stress_relief":
            return self._generate_stress_relief_response(context)
        elif topic == "energy_boost":
            return self._generate_energy_boost_response(context)
        elif topic == "workout_suggestion":
            return self._generate_workout_suggestion(context)
        elif topic == "sleep_advice":
            return self._generate_sleep_advice(context)

        return "I can help you with health and wellness topics. What would you like to know?"

    def _generate_health_summary(self, context: HealthContext) -> str:
        """Generate comprehensive health summary."""
        summary_parts = []

        if context.current_heart_rate:
            summary_parts.append(f"Your heart rate is {context.current_heart_rate} bpm")

        if context.recovery_score:
            summary_parts.append(f"Your recovery score is {context.recovery_score:.1f}/100")

        if context.strain_score:
            summary_parts.append(f"Your strain score is {context.strain_score:.1f}")

        if context.sleep_hours_last_night:
            summary_parts.append(f"You slept {context.sleep_hours_last_night:.1f} hours last night")

        if context.stress_level:
            summary_parts.append(f"Your stress level is {context.stress_level}/100")

        if context.active_alerts:
            summary_parts.append(f"Active alerts: {', '.join(context.active_alerts)}")

        if summary_parts:
            summary = ". ".join(summary_parts)
            return f"Here's your current health status: {summary}. How can I help you today?"
        else:
            return "I don't have enough health data yet. Please make sure your Samsung Health and Whoop apps are connected."

    def _generate_stress_relief_response(self, context: HealthContext) -> str:
        """Generate stress relief response."""
        stress_level = context.stress_level or 50

        if stress_level > 80:
            return "I can see you're quite stressed. Let me guide you through a breathing exercise: Inhale for 4 counts, hold for 4, exhale for 4. Would you like me to continue guiding you?"
        elif stress_level > 60:
            return "You're feeling stressed. Try this quick technique: Place one hand on your chest and one on your belly. Take slow, deep breaths. Should I play some calming music to help?"
        else:
            return "For stress relief, try progressive muscle relaxation or deep breathing. Would you like me to walk you through a specific technique?"

    def _generate_energy_boost_response(self, context: HealthContext) -> str:
        """Generate energy boost response."""
        recovery_score = context.recovery_score or 50

        if recovery_score < 40:
            return "Your recovery score suggests you need more rest. Consider taking a short nap or doing some light stretching. Would you like me to set a reminder?"
        elif recovery_score < 60:
            return "You could use a little energy boost. Try drinking water, having a healthy snack, or taking a short walk. What sounds good to you?"
        else:
            return "For an energy boost, try some light exercise, listen to upbeat music, or have a nutritious snack. How can I help you get energized?"

    def _generate_workout_suggestion(self, context: HealthContext) -> str:
        """Generate workout suggestion based on current health state."""
        recovery_score = context.recovery_score or 50
        strain_score = context.strain_score or 10

        if recovery_score < 40:
            return "Based on your recovery score, I recommend light activity today like walking or gentle yoga. High-intensity workouts might not be ideal right now."
        elif strain_score > 15:
            return "Your strain score is high, so consider active recovery activities like swimming, yoga, or light cycling. Avoid heavy weight training today."
        elif recovery_score > 70:
            return "You're well-recovered! This is a great day for more intense workouts. Consider strength training, running, or high-intensity interval training."
        else:
            return "For today, moderate-intensity activities like brisk walking, cycling, or bodyweight exercises would be perfect. What type of workout interests you?"

    def _generate_sleep_advice(self, context: HealthContext) -> str:
        """Generate sleep improvement advice."""
        sleep_hours = context.sleep_hours_last_night or 7

        if sleep_hours < 6:
            return "You got less sleep than recommended. Try establishing a consistent sleep schedule, avoid screens before bed, and create a cool, dark sleeping environment."
        elif sleep_hours < 7:
            return "You could benefit from more sleep. Consider going to bed earlier tonight and avoiding caffeine after 2 PM. Would you like me to set a bedtime reminder?"
        else:
            return "Your sleep duration looks good! To improve sleep quality, maintain a consistent schedule, exercise regularly, and avoid heavy meals before bed."

    def _get_state_based_response(self, context: HealthContext) -> Optional[str]:
        """Get response based on current health state."""
        if context.user_state == "emergency":
            return "EMERGENCY: I detect concerning vital signs. Please sit down immediately. I'm preparing to contact emergency services. Stay calm and breathe deeply."

        templates = self.response_templates.get(context.user_state, [])
        if templates:
            return templates[0]  # Return first template for simplicity

        return None

    def should_modify_voice_parameters(self, context: HealthContext) -> Dict[str, Any]:
        """Determine if voice parameters should be modified based on health state."""
        modifications = {}

        if context.user_state == "emergency":
            modifications.update({
                "speed": "slow",
                "volume": "loud",
                "tone": "urgent",
                "repeat": True
            })
        elif context.user_state == "fatigued":
            modifications.update({
                "speed": "slow",
                "volume": "soft",
                "tone": "calm"
            })
        elif context.user_state == "stressed":
            modifications.update({
                "speed": "slow",
                "tone": "calm",
                "pause_length": "longer"
            })

        return modifications

    def get_health_tips(self, context: HealthContext) -> List[str]:
        """Get personalized health tips based on current state."""
        tips = []

        if context.recovery_score and context.recovery_score < 50:
            tips.append("Focus on recovery today - consider light walking or restorative yoga")

        if context.strain_score and context.strain_score > 15:
            tips.append("Your body is under strain - prioritize rest and recovery activities")

        if context.sleep_hours_last_night and context.sleep_hours_last_night < 7:
            tips.append("Aim for 7-9 hours of sleep tonight to improve recovery")

        if context.stress_level and context.stress_level > 60:
            tips.append("Try deep breathing or meditation to manage stress levels")

        if not tips:
            tips.append("Keep up the good work maintaining your health!")

        return tips

