"""
Health Data Synchronization and Processing

Combines data from Samsung Health and Whoop APIs,
processes it, and provides unified health insights.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
import threading
import time

from .samsung_health_api import SamsungHealthAPI
from .whoop_api import WhoopAPI

logger = logging.getLogger(__name__)

@dataclass
class HealthMetrics:
    """Unified health metrics from all sources."""
    timestamp: datetime
    heart_rate: Optional[int] = None
    hrv: Optional[int] = None
    steps: Optional[int] = None
    sleep_hours: Optional[float] = None
    sleep_quality: Optional[float] = None
    recovery_score: Optional[float] = None
    strain_score: Optional[float] = None
    stress_level: Optional[int] = None
    blood_pressure_systolic: Optional[int] = None
    blood_pressure_diastolic: Optional[int] = None
    workout_intensity: Optional[float] = None
    energy_level: Optional[float] = None

@dataclass
class HealthAlert:
    """Health alert configuration and state."""
    alert_type: str
    condition: str
    threshold: Union[int, float]
    message: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    enabled: bool = True
    last_triggered: Optional[datetime] = None

class HealthDataSync:
    """Manages synchronization of health data from multiple sources."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.samsung_api: Optional[SamsungHealthAPI] = None
        self.whoop_api: Optional[WhoopAPI] = None
        self.health_data: List[HealthMetrics] = []
        self.alerts: List[HealthAlert] = []
        self.sync_interval = config.get('sync_interval', 300)  # 5 minutes default
        self.is_syncing = False
        self.last_sync: Optional[datetime] = None

    def initialize_apis(self) -> None:
        """Initialize API connections."""
        # Initialize Samsung Health API
        samsung_config = self.config.get('samsung_health', {})
        if samsung_config.get('enabled', False):
            try:
                self.samsung_api = SamsungHealthAPI(
                    client_id=samsung_config['client_id'],
                    client_secret=samsung_config['client_secret'],
                    redirect_uri=samsung_config['redirect_uri']
                )
                # Load existing tokens if available
                if samsung_config.get('access_token'):
                    self.samsung_api.access_token = samsung_config['access_token']
                    self.samsung_api.refresh_token = samsung_config.get('refresh_token')
                    self.samsung_api.token_expiry = samsung_config.get('token_expiry')
                logger.info("Samsung Health API initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Samsung Health API: {e}")

        # Initialize Whoop API
        whoop_config = self.config.get('whoop', {})
        if whoop_config.get('enabled', False):
            try:
                self.whoop_api = WhoopAPI(
                    client_id=whoop_config['client_id'],
                    client_secret=whoop_config['client_secret'],
                    redirect_uri=whoop_config['redirect_uri']
                )
                # Load existing tokens if available
                if whoop_config.get('access_token'):
                    self.whoop_api.access_token = whoop_config['access_token']
                    self.whoop_api.refresh_token = whoop_config.get('refresh_token')
                    self.whoop_api.token_expiry = whoop_config.get('token_expiry')
                logger.info("Whoop API initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Whoop API: {e}")

    def setup_default_alerts(self) -> None:
        """Set up default health alerts."""
        self.alerts = [
            HealthAlert(
                alert_type="heart_rate_high",
                condition="heart_rate > 100",
                threshold=100,
                message="Your heart rate is elevated. Consider taking a break.",
                severity="medium"
            ),
            HealthAlert(
                alert_type="heart_rate_critical",
                condition="heart_rate > 120",
                threshold=120,
                message="Your heart rate is critically high. Please rest immediately.",
                severity="high"
            ),
            HealthAlert(
                alert_type="recovery_low",
                condition="recovery_score < 33",
                threshold=33,
                message="Your recovery score is low. Consider light activity or rest.",
                severity="low"
            ),
            HealthAlert(
                alert_type="strain_high",
                condition="strain_score > 17",
                threshold=17,
                message="Your strain level is high. Consider reducing intensity.",
                severity="medium"
            ),
            HealthAlert(
                alert_type="sleep_low",
                condition="sleep_hours < 7",
                threshold=7,
                message="You got less than 7 hours of sleep. Prioritize rest today.",
                severity="low"
            ),
            HealthAlert(
                alert_type="stress_high",
                condition="stress_level > 70",
                threshold=70,
                message="Your stress level is elevated. Consider relaxation techniques.",
                severity="medium"
            )
        ]

    async def sync_health_data(self) -> None:
        """Synchronize health data from all sources."""
        if self.is_syncing:
            logger.info("Sync already in progress, skipping")
            return

        self.is_syncing = True
        try:
            logger.info("Starting health data synchronization")

            # Get data from Samsung Health
            samsung_data = await self._sync_samsung_health()

            # Get data from Whoop
            whoop_data = await self._sync_whoop()

            # Merge and process data
            merged_data = self._merge_health_data(samsung_data, whoop_data)

            # Store processed data
            self.health_data.extend(merged_data)

            # Keep only recent data (last 30 days)
            cutoff_date = datetime.now() - timedelta(days=30)
            self.health_data = [
                data for data in self.health_data
                if data.timestamp >= cutoff_date
            ]

            # Check for alerts
            await self._check_alerts()

            self.last_sync = datetime.now()
            logger.info(f"Health data sync completed. Processed {len(merged_data)} data points")

        except Exception as e:
            logger.error(f"Health data sync failed: {e}")
        finally:
            self.is_syncing = False

    async def _sync_samsung_health(self) -> List[Dict]:
        """Sync data from Samsung Health."""
        if not self.samsung_api:
            return []

        try:
            data = []

            # Get heart rate data
            heart_data = self.samsung_api.get_heart_rate_data(hours=24)
            data.extend(heart_data)

            # Get steps data
            steps_data = self.samsung_api.get_steps_data(days=1)
            data.extend(steps_data)

            # Get sleep data
            sleep_data = self.samsung_api.get_sleep_data(days=1)
            data.extend(sleep_data)

            # Get stress data
            stress_data = self.samsung_api.get_stress_data(hours=24)
            data.extend(stress_data)

            # Get blood pressure data
            bp_data = self.samsung_api.get_blood_pressure_data(days=7)
            data.extend(bp_data)

            return data

        except Exception as e:
            logger.error(f"Samsung Health sync failed: {e}")
            return []

    async def _sync_whoop(self) -> List[Dict]:
        """Sync data from Whoop."""
        if not self.whoop_api:
            return []

        try:
            data = []

            # Get recovery data
            recovery_data = self.whoop_api.get_recent_recovery(days=1)
            data.extend(recovery_data)

            # Get sleep data
            sleep_data = self.whoop_api.get_recent_sleep(days=1)
            data.extend(sleep_data)

            # Get workout data
            workout_data = self.whoop_api.get_recent_workouts(days=1)
            data.extend(workout_data)

            return data

        except Exception as e:
            logger.error(f"Whoop sync failed: {e}")
            return []

    def _merge_health_data(self, samsung_data: List[Dict], whoop_data: List[Dict]) -> List[HealthMetrics]:
        """Merge and process data from different sources."""
        merged_data = []

        # Process Samsung Health data
        for item in samsung_data:
            timestamp = datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00'))
            metrics = HealthMetrics(timestamp=timestamp)

            if item.get('data_type') == 'heart_rate':
                metrics.heart_rate = item.get('value')
            elif item.get('data_type') == 'steps':
                metrics.steps = item.get('value')
            elif item.get('data_type') == 'sleep':
                metrics.sleep_hours = item.get('duration_hours')
                metrics.sleep_quality = item.get('quality_score')
            elif item.get('data_type') == 'stress':
                metrics.stress_level = item.get('value')
            elif item.get('data_type') == 'blood_pressure':
                metrics.blood_pressure_systolic = item.get('systolic')
                metrics.blood_pressure_diastolic = item.get('diastolic')

            merged_data.append(metrics)

        # Process Whoop data
        for item in whoop_data:
            timestamp = datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00'))
            metrics = HealthMetrics(timestamp=timestamp)

            if 'recovery' in item:
                recovery = item['recovery']
                metrics.recovery_score = recovery.get('score')
                metrics.strain_score = recovery.get('strain')
                metrics.hrv = recovery.get('hrv')

            if 'sleep' in item:
                sleep = item['sleep']
                metrics.sleep_hours = sleep.get('duration_hours')
                metrics.sleep_quality = sleep.get('quality_score')

            if 'workout' in item:
                workout = item['workout']
                metrics.workout_intensity = workout.get('intensity')
                metrics.energy_level = workout.get('energy_level')

            merged_data.append(metrics)

        # Sort by timestamp and remove duplicates
        merged_data.sort(key=lambda x: x.timestamp)

        # Remove duplicates (keep most complete data point)
        deduplicated = []
        seen_timestamps = set()

        for metrics in merged_data:
            timestamp_key = metrics.timestamp.replace(second=0, microsecond=0)
            if timestamp_key not in seen_timestamps:
                seen_timestamps.add(timestamp_key)
                deduplicated.append(metrics)

        return deduplicated

    async def _check_alerts(self) -> None:
        """Check current health data against alert conditions."""
        if not self.health_data:
            return

        # Get most recent data point
        latest_data = max(self.health_data, key=lambda x: x.timestamp)

        for alert in self.alerts:
            if not alert.enabled:
                continue

            triggered = False

            if alert.alert_type == "heart_rate_high" and latest_data.heart_rate:
                triggered = latest_data.heart_rate > alert.threshold
            elif alert.alert_type == "heart_rate_critical" and latest_data.heart_rate:
                triggered = latest_data.heart_rate > alert.threshold
            elif alert.alert_type == "recovery_low" and latest_data.recovery_score:
                triggered = latest_data.recovery_score < alert.threshold
            elif alert.alert_type == "strain_high" and latest_data.strain_score:
                triggered = latest_data.strain_score > alert.threshold
            elif alert.alert_type == "sleep_low" and latest_data.sleep_hours:
                triggered = latest_data.sleep_hours < alert.threshold
            elif alert.alert_type == "stress_high" and latest_data.stress_level:
                triggered = latest_data.stress_level > alert.threshold

            if triggered:
                await self._trigger_alert(alert)

    async def _trigger_alert(self, alert: HealthAlert) -> None:
        """Trigger a health alert."""
        alert.last_triggered = datetime.now()
        logger.warning(f"Health Alert: {alert.message} (Severity: {alert.severity})")

        # Here you would integrate with notification systems
        # For now, just log the alert

    def get_current_health_status(self) -> Dict[str, Any]:
        """Get current health status summary."""
        if not self.health_data:
            return {"status": "no_data"}

        latest_data = max(self.health_data, key=lambda x: x.timestamp)

        status = {
            "timestamp": latest_data.timestamp.isoformat(),
            "heart_rate": latest_data.heart_rate,
            "recovery_score": latest_data.recovery_score,
            "strain_score": latest_data.strain_score,
            "sleep_hours": latest_data.sleep_hours,
            "stress_level": latest_data.stress_level,
            "active_alerts": [
                {
                    "type": alert.alert_type,
                    "message": alert.message,
                    "severity": alert.severity,
                    "last_triggered": alert.last_triggered.isoformat() if alert.last_triggered else None
                }
                for alert in self.alerts
                if alert.last_triggered and
                (datetime.now() - alert.last_triggered).seconds < 3600  # Last hour
            ]
        }

        return status

    def start_background_sync(self) -> None:
        """Start background synchronization thread."""
        def sync_loop():
            while True:
                asyncio.run(self.sync_health_data())
                time.sleep(self.sync_interval)

        sync_thread = threading.Thread(target=sync_loop, daemon=True)
        sync_thread.start()
        logger.info("Background health data sync started")

