#!/usr/bin/env python3
"""
Health Integration Example

This example demonstrates how to integrate the health monitoring system
with the voice-to-text application.
"""

import sys
import os
import json
import logging
from pathlib import Path

# Add the health integration module to the path
sys.path.insert(0, os.path.dirname(__file__))

from health_integration import HealthMonitor, SecureStorage

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HealthAwareVoiceSystem:
    """Example integration of health monitoring with voice system."""

    def __init__(self):
        self.health_monitor = HealthMonitor()
        self.storage = SecureStorage()

        # Setup alert callbacks
        self.health_monitor.add_alert_callback(self.handle_health_alert)

    def setup_samsung_health(self):
        """Setup Samsung Health integration."""
        print("🔧 Setting up Samsung Health integration...")

        # Example configuration (replace with your actual credentials)
        samsung_config = {
            "client_id": "your_samsung_client_id",
            "client_secret": "your_samsung_client_secret",
            "redirect_uri": "http://localhost:8080/callback/samsung"
        }

        success = self.health_monitor.configure_service("samsung_health", samsung_config)

        if success:
            print("✅ Samsung Health configured successfully!")
            print("📱 To authorize:")
            auth_url = self.health_monitor.get_auth_url("samsung_health")
            if auth_url:
                print(f"   Visit: {auth_url}")
                print("   Complete authorization and get the authorization code")
        else:
            print("❌ Failed to configure Samsung Health")

    def setup_whoop(self):
        """Setup Whoop integration."""
        print("🔧 Setting up Whoop integration...")

        # Example configuration (replace with your actual credentials)
        whoop_config = {
            "client_id": "your_whoop_client_id",
            "client_secret": "your_whoop_client_secret",
            "redirect_uri": "http://localhost:8080/callback/whoop"
        }

        success = self.health_monitor.configure_service("whoop", whoop_config)

        if success:
            print("✅ Whoop configured successfully!")
            print("📱 To authorize:")
            auth_url = self.health_monitor.get_auth_url("whoop")
            if auth_url:
                print(f"   Visit: {auth_url}")
                print("   Complete authorization and get the authorization code")
        else:
            print("❌ Failed to configure Whoop")

    def authenticate_service(self, service_name: str, auth_code: str):
        """Authenticate a service with authorization code."""
        print(f"🔐 Authenticating {service_name}...")

        success = self.health_monitor.authenticate_service(service_name, auth_code)

        if success:
            print(f"✅ {service_name} authenticated successfully!")
        else:
            print(f"❌ Failed to authenticate {service_name}")

    def handle_health_alert(self, alert: dict):
        """Handle health alerts."""
        print("🚨 HEALTH ALERT:"        print(f"   Type: {alert.get('type', 'Unknown')}")
        print(f"   Message: {alert.get('message', 'No message')}")
        print(f"   Severity: {alert.get('severity', 'Unknown')}")

        # Here you would integrate with your voice system
        # For example, modify voice parameters or trigger voice responses
        if alert.get('severity') == 'critical':
            print("🚨 CRITICAL ALERT - Taking emergency actions!")
            self.trigger_emergency_response()

    def trigger_emergency_response(self):
        """Handle emergency situations."""
        print("🚨 EMERGENCY PROTOCOL ACTIVATED")

        # Get emergency contacts
        contacts = self.health_monitor.get_emergency_contacts()

        if contacts:
            print(f"📞 Notifying {len(contacts)} emergency contacts...")
            for contact in contacts:
                print(f"   📱 {contact.get('name', 'Unknown')}: {contact.get('phone', 'No phone')}")
        else:
            print("⚠️  No emergency contacts configured!")

    def setup_emergency_contacts(self):
        """Setup emergency contact information."""
        print("📞 Setting up emergency contacts...")

        contacts = [
            {
                "name": "Emergency Contact 1",
                "phone": "+1234567890",
                "relationship": "Family",
                "priority": 1
            },
            {
                "name": "Emergency Contact 2",
                "phone": "+0987654321",
                "relationship": "Friend",
                "priority": 2
            }
        ]

        self.health_monitor.set_emergency_contacts(contacts)
        print(f"✅ Configured {len(contacts)} emergency contacts")

    def demonstrate_health_aware_responses(self):
        """Demonstrate health-aware voice responses."""
        print("\n🗣️  Demonstrating health-aware responses...")
        print("=" * 50)

        # Example user inputs that should trigger health-aware responses
        test_inputs = [
            "How am I feeling today?",
            "Check my health status",
            "I'm feeling stressed",
            "I need energy",
            "Should I work out today?",
            "Help me sleep better"
        ]

        for user_input in test_inputs:
            print(f"\n👤 User: '{user_input}'")

            # Get health-aware response
            response = self.health_monitor.get_health_aware_response(user_input)

            if response:
                print(f"🤖 System: '{response}'")
            else:
                print("🤖 System: 'No health-aware response available'")

            # Show voice modifications if any
            voice_mods = self.health_monitor.get_voice_modifications()
            if voice_mods:
                print(f"🎵 Voice modifications: {voice_mods}")

    def show_health_status(self):
        """Display current health status."""
        print("\n📊 Current Health Status")
        print("=" * 30)

        status = self.health_monitor.get_health_status()

        if status.get('status') == 'no_data':
            print("📭 No health data available yet")
            print("   Please configure and authorize your health services")
            return

        # Display current metrics
        if status.get('heart_rate'):
            print(f"❤️  Heart Rate: {status['heart_rate']} bpm")

        if status.get('recovery_score'):
            print(f"🔄 Recovery Score: {status['recovery_score']:.1f}/100")

        if status.get('strain_score'):
            print(f"💪 Strain Score: {status['strain_score']:.1f}")

        if status.get('sleep_hours'):
            print(f"😴 Sleep Hours: {status['sleep_hours']:.1f}")

        if status.get('stress_level'):
            print(f"😰 Stress Level: {status['stress_level']}/100")

        # Display active alerts
        active_alerts = status.get('active_alerts', [])
        if active_alerts:
            print(f"\n🚨 Active Alerts: {len(active_alerts)}")
            for alert in active_alerts:
                print(f"   ⚠️  {alert.get('message', 'Unknown alert')}")

        # Display health tips
        tips = self.health_monitor.get_health_tips()
        if tips:
            print("
💡 Health Tips:"            for tip in tips:
                print(f"   • {tip}")

    def run_demo(self):
        """Run the complete health integration demo."""
        print("🚀 Health Integration Demo")
        print("=" * 30)

        # Show current service status
        service_status = self.health_monitor.get_service_status()
        print(f"📡 Monitoring Active: {service_status['monitoring_active']}")

        print("🔧 Configured Services:")
        for service, info in service_status['services'].items():
            status = "✅" if info['configured'] and info['enabled'] else "❌"
            print(f"   {status} {service.replace('_', ' ').title()}: {info}")

        # Setup emergency contacts
        self.setup_emergency_contacts()

        # Show health status
        self.show_health_status()

        # Demonstrate health-aware responses
        self.demonstrate_health_aware_responses()

        # Show export capability
        print("
📤 Health Data Export:"        export_data = self.health_monitor.export_health_data()
        print(f"   📊 Data points: {len(export_data) if export_data else 0}")

def main():
    """Main demo function."""
    try:
        # Create health-aware voice system
        voice_system = HealthAwareVoiceSystem()

        # Setup services (commented out - replace with your credentials)
        # voice_system.setup_samsung_health()
        # voice_system.setup_whoop()

        # For demo purposes, setup emergency contacts
        voice_system.setup_emergency_contacts()

        # Run the demo
        voice_system.run_demo()

        print("
🎉 Demo completed!"        print("To integrate with your voice system:")
        print("1. Import HealthMonitor in your main application")
        print("2. Configure your API credentials")
        print("3. Call get_health_aware_response() for user inputs")
        print("4. Use get_voice_modifications() to adjust voice parameters")

    except KeyboardInterrupt:
        print("\n👋 Demo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"❌ Demo failed: {e}")

if __name__ == "__main__":
    main()

