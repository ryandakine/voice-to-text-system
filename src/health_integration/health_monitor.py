"""
Health Monitor - Main Integration Module

Provides real-time health monitoring and integrates with the voice-to-text system.
"""

import asyncio
import logging
import threading
import time
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta

from .samsung_health_api import SamsungHealthAPI
from .whoop_api import WhoopAPI
from .health_data_sync import HealthDataSync
from .health_aware_responses import HealthAwareResponses
from .secure_storage import SecureStorage

logger = logging.getLogger(__name__)

class HealthMonitor:
    """Main health monitoring integration for voice-to-text system."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._get_default_config()
        self.storage = SecureStorage()
        self.health_sync = HealthDataSync(self.config)
        self.health_responses = HealthAwareResponses(self.health_sync)
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.alert_callbacks: List[Callable] = []

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "sync_interval": 300,  # 5 minutes
            "alert_check_interval": 60,  # 1 minute
            "emergency_thresholds": {
                "heart_rate_critical": 120,
                "stress_critical": 90,
                "recovery_critical": 20
            },
            "samsung_health": {
                "enabled": False,
                "client_id": "",
                "client_secret": "",
                "redirect_uri": ""
            },
            "whoop": {
                "enabled": False,
                "client_id": "",
                "client_secret": "",
                "redirect_uri": ""
            }
        }

    def configure_service(self, service: str, config: Dict[str, Any]) -> bool:
        """Configure a health service (Samsung Health or Whoop)."""
        if service not in ["samsung_health", "whoop"]:
            logger.error(f"Unknown service: {service}")
            return False

        try:
            # Update configuration
            self.config[service].update(config)
            self.config[service]["enabled"] = True

            # Initialize API
            if service == "samsung_health":
                self.health_sync.samsung_api = SamsungHealthAPI(
                    client_id=config["client_id"],
                    client_secret=config["client_secret"],
                    redirect_uri=config["redirect_uri"]
                )
            elif service == "whoop":
                self.health_sync.whoop_api = WhoopAPI(
                    client_id=config["client_id"],
                    client_secret=config["client_secret"],
                    redirect_uri=config["redirect_uri"]
                )

            # Store credentials securely
            self.storage.store_api_credentials(service, config)

            logger.info(f"Successfully configured {service}")
            return True

        except Exception as e:
            logger.error(f"Failed to configure {service}: {e}")
            return False

    def authenticate_service(self, service: str, authorization_code: str) -> bool:
        """Complete OAuth authentication for a service."""
        try:
            if service == "samsung_health" and self.health_sync.samsung_api:
                token_data = self.health_sync.samsung_api.exchange_code_for_token(authorization_code)
                self.storage.update_api_tokens(service, token_data)
                return True

            elif service == "whoop" and self.health_sync.whoop_api:
                token_data = self.health_sync.whoop_api.exchange_code_for_token(authorization_code)
                self.storage.update_api_tokens(service, token_data)
                return True

            else:
                logger.error(f"Service {service} not properly configured")
                return False

        except Exception as e:
            logger.error(f"Authentication failed for {service}: {e}")
            return False

    def get_auth_url(self, service: str) -> Optional[str]:
        """Get OAuth authorization URL for a service."""
        try:
            if service == "samsung_health" and self.health_sync.samsung_api:
                return self.health_sync.samsung_api.get_authorization_url()
            elif service == "whoop" and self.health_sync.whoop_api:
                return self.health_sync.whoop_api.get_authorization_url()
            else:
                logger.error(f"Service {service} not configured")
                return None
        except Exception as e:
            logger.error(f"Failed to get auth URL for {service}: {e}")
            return None

    def start_monitoring(self) -> bool:
        """Start health monitoring."""
        if self.monitoring_active:
            logger.info("Health monitoring already active")
            return True

        try:
            # Load stored API configurations
            self._load_stored_configurations()

            # Initialize APIs
            self.health_sync.initialize_apis()

            # Setup default alerts
            self.health_sync.setup_default_alerts()

            # Start background monitoring
            self.monitoring_active = True
            self.monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                daemon=True
            )
            self.monitor_thread.start()

            logger.info("Health monitoring started successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to start health monitoring: {e}")
            self.monitoring_active = False
            return False

    def stop_monitoring(self) -> None:
        """Stop health monitoring."""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Health monitoring stopped")

    def _load_stored_configurations(self) -> None:
        """Load stored API configurations."""
        for service in ["samsung_health", "whoop"]:
            stored_config = self.storage.get_api_credentials(service)
            if stored_config:
                self.config[service].update(stored_config)
                logger.info(f"Loaded stored configuration for {service}")

    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        logger.info("Health monitoring loop started")

        while self.monitoring_active:
            try:
                # Sync health data
                asyncio.run(self.health_sync.sync_health_data())

                # Check for alerts
                asyncio.run(self._check_alerts())

                # Wait before next cycle
                time.sleep(self.config["alert_check_interval"])

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(30)  # Wait before retrying

        logger.info("Health monitoring loop ended")

    async def _check_alerts(self) -> None:
        """Check for health alerts and trigger callbacks."""
        if not self.health_sync.health_data:
            return

        # Get current health status
        status = self.health_sync.get_current_health_status()
        active_alerts = status.get("active_alerts", [])

        # Trigger alert callbacks
        for alert in active_alerts:
            for callback in self.alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    logger.error(f"Error in alert callback: {e}")

    def add_alert_callback(self, callback: Callable) -> None:
        """Add a callback function for health alerts."""
        self.alert_callbacks.append(callback)

    def remove_alert_callback(self, callback: Callable) -> None:
        """Remove an alert callback function."""
        if callback in self.alert_callbacks:
            self.alert_callbacks.remove(callback)

    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status."""
        return self.health_sync.get_current_health_status()

    def get_health_aware_response(self, user_input: str) -> Optional[str]:
        """Get health-aware response for user input."""
        return self.health_responses.get_health_aware_response(user_input)

    def get_voice_modifications(self) -> Dict[str, Any]:
        """Get voice parameter modifications based on health state."""
        context = self.health_responses.get_current_health_context()
        return self.health_responses.should_modify_voice_parameters(context)

    def get_health_tips(self) -> List[str]:
        """Get personalized health tips."""
        context = self.health_responses.get_current_health_context()
        return self.health_responses.get_health_tips(context)

    def set_emergency_contacts(self, contacts: List[Dict[str, Any]]) -> None:
        """Set emergency contact information."""
        self.storage.store_emergency_contacts(contacts)
        logger.info(f"Stored {len(contacts)} emergency contacts")

    def get_emergency_contacts(self) -> List[Dict[str, Any]]:
        """Get emergency contact information."""
        return self.storage.get_emergency_contacts()

    def export_health_data(self) -> Dict[str, Any]:
        """Export health data for backup or analysis."""
        return {
            "current_status": self.get_health_status(),
            "health_tips": self.get_health_tips(),
            "emergency_contacts": self.get_emergency_contacts(),
            "configuration": self.storage.export_configuration(),
            "exported_at": datetime.now().isoformat()
        }

    def get_service_status(self) -> Dict[str, Any]:
        """Get status of configured health services."""
        status = {
            "monitoring_active": self.monitoring_active,
            "services": {}
        }

        for service in ["samsung_health", "whoop"]:
            service_config = self.storage.get_api_credentials(service)
            status["services"][service] = {
                "configured": service_config is not None,
                "enabled": self.config[service].get("enabled", False),
                "has_tokens": service_config and "access_token" in service_config if service_config else False
            }

        return status

    def trigger_emergency_protocol(self, reason: str) -> None:
        """Trigger emergency protocol."""
        logger.critical(f"EMERGENCY PROTOCOL TRIGGERED: {reason}")

        # Get emergency contacts
        contacts = self.get_emergency_contacts()

        # Log emergency event
        emergency_data = {
            "timestamp": datetime.now().isoformat(),
            "reason": reason,
            "health_status": self.get_health_status(),
            "contacts_notified": len(contacts)
        }

        self.storage.store_health_data("emergency_event", emergency_data)

        # Here you would integrate with emergency notification systems
        # For now, just log the emergency
        print(f"🚨 EMERGENCY: {reason}")
        print(f"Emergency contacts: {len(contacts)}")
        for contact in contacts[:3]:  # Show first 3 contacts
            print(f"  - {contact.get('name', 'Unknown')}: {contact.get('phone', 'No phone')}")

