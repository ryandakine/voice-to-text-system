"""
Health Data Integration Module

This module handles integration with Samsung Health and Whoop APIs
to provide real-time health monitoring and health-aware voice responses.
"""

__version__ = "1.0.0"
__author__ = "Voice-to-Text System"

from .samsung_health_api import SamsungHealthAPI
from .whoop_api import WhoopAPI
from .health_data_sync import HealthDataSync, HealthMetrics, HealthAlert
from .health_aware_responses import HealthAwareResponses, HealthContext
from .secure_storage import SecureStorage
from .health_monitor import HealthMonitor

__all__ = [
    "SamsungHealthAPI",
    "WhoopAPI",
    "HealthDataSync",
    "HealthMetrics",
    "HealthAlert",
    "HealthAwareResponses",
    "HealthContext",
    "SecureStorage",
    "HealthMonitor"
]
