#!/usr/bin/env python3
"""
Real API Setup Script

Helps set up actual Samsung Health and banking API connections
with real credentials and data flow.
"""

import json
import os
import sys
from pathlib import Path
import webbrowser
import time

# Add health integration to path
sys.path.insert(0, os.path.dirname(__file__) + '/src')

try:
    from health_integration import HealthMonitor
except ImportError as e:
    print(f"❌ Cannot import HealthMonitor: {e}")
    print("Please run: pip install cryptography keyring requests")
    sys.exit(1)

class APISetup:
    """Handles real API setup and configuration."""

    def __init__(self):
        self.monitor = HealthMonitor()
        self.config_file = Path.home() / ".config" / "voice-to-text" / "real_api_config.json"
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

    def load_existing_config(self):
        """Load existing API configuration if available."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  Could not load existing config: {e}")
        return {}

    def save_config(self, config):
        """Save API configuration."""
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"✅ Configuration saved to {self.config_file}")

    def setup_samsung_health(self):
        """Set up real Samsung Health API connection."""
        print("\n🏥 Setting up Samsung Health API")
        print("=" * 40)

        # Check if already configured
        existing_config = self.load_existing_config()
        samsung_config = existing_config.get('samsung_health', {})

        if samsung_config.get('configured', False):
            print("✅ Samsung Health already configured!")
            choice = input("Reconfigure? (y/N): ").lower().strip()
            if choice != 'y':
                return samsung_config

        print("\n📋 Samsung Health API Setup Steps:")
        print("1. Go to: https://developer.samsung.com/health")
        print("2. Create a developer account")
        print("3. Register a new application")
        print("4. Get your Client ID and Client Secret")
        print("5. Set redirect URI to: http://localhost:8080/callback/samsung")

        # Open browser
        try:
            webbrowser.open("https://developer.samsung.com/health")
            print("\n🌐 Opened Samsung Developer Portal in browser")
        except Exception as e:
            print(f"⚠️  Could not open browser: {e}")

        print("\n🔑 Enter your Samsung Health API credentials:")

        client_id = input("Client ID: ").strip()
        if not client_id:
            print("❌ Client ID is required")
            return None

        client_secret = input("Client Secret: ").strip()
        if not client_secret:
            print("❌ Client Secret is required")
            return None

        redirect_uri = input("Redirect URI [http://localhost:8080/callback/samsung]: ").strip()
        if not redirect_uri:
            redirect_uri = "http://localhost:8080/callback/samsung"

        # Configure the service
        api_config = {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri
        }

        success = self.monitor.configure_service("samsung_health", api_config)

        if success:
            print("✅ Samsung Health API configured successfully!")

            # Get authorization URL
            auth_url = self.monitor.get_auth_url("samsung_health")
            if auth_url:
                print(f"\n🔗 Authorization URL: {auth_url}")
                print("\n📱 Next steps:")
                print("1. Visit the authorization URL above")
                print("2. Grant permissions to access your health data")
                print("3. You'll be redirected to your redirect URI")
                print("4. Copy the authorization code from the URL")

                auth_code = input("\n📋 Paste the authorization code here: ").strip()
                if auth_code:
                    if self.monitor.authenticate_service("samsung_health", auth_code):
                        print("✅ Samsung Health authentication successful!")
                        print("🎉 Your health data will now sync automatically")

                        # Save configuration
                        config = self.load_existing_config()
                        config['samsung_health'] = {
                            'configured': True,
                            'client_id': client_id,
                            'redirect_uri': redirect_uri,
                            'authenticated': True
                        }
                        self.save_config(config)

                        return config['samsung_health']
                    else:
                        print("❌ Authentication failed")
                else:
                    print("⚠️  Skipping authentication - you can authenticate later")
            else:
                print("❌ Could not generate authorization URL")
        else:
            print("❌ Failed to configure Samsung Health API")

        return None

    def setup_banking_api(self):
        """Set up banking API integration."""
        print("\n🏦 Setting up Banking API")
        print("=" * 30)

        print("🤔 What banking integration do you need?")
        print("1. Bank account balance monitoring")
        print("2. Transaction analysis")
        print("3. Budget tracking")
        print("4. Payment processing")
        print("5. Something else (please specify)")

        choice = input("\nEnter your choice (1-5): ").strip()

        if choice == "5":
            other = input("Please describe what banking features you need: ").strip()
            print(f"\n📝 You specified: {other}")
            print("I'll help you set this up once we clarify the requirements.")
            return None

        banking_type = {
            "1": "account_balance",
            "2": "transaction_analysis",
            "3": "budget_tracking",
            "4": "payment_processing"
        }.get(choice)

        if not banking_type:
            print("❌ Invalid choice")
            return None

        print(f"\n🔍 Setting up {banking_type.replace('_', ' ').title()}")

        # For now, we'll set up a basic framework
        # In a real implementation, you'd integrate with:
        # - Plaid for bank account access
        # - Stripe for payment processing
        # - Mint/Yodlee for budget tracking

        print("📋 Banking API Integration Options:")
        print("- Plaid (most banks, secure)")
        print("- Stripe (payments)")
        print("- Teller (European banks)")
        print("- Custom bank API")

        provider = input("\nWhich provider do you prefer? ").strip().lower()

        if provider in ['plaid', 'stripe', 'teller']:
            print(f"\n🔧 To set up {provider.upper()}:")
            print(f"1. Go to {provider}.com/developers")
            print("2. Create an account")
            print("3. Get your API keys")
            print("4. Configure the integration")
        else:
            print("\n📝 Custom banking setup needed.")
            print("Please provide more details about your banking requirements.")

        return {"type": banking_type, "provider": provider, "configured": False}

    def setup_emergency_contacts(self):
        """Set up emergency contacts."""
        print("\n🚨 Setting up Emergency Contacts")
        print("=" * 35)

        contacts = []
        print("📞 Emergency contacts are crucial for the health monitoring system.")
        print("Add at least 2 emergency contacts who can be notified in case of health emergencies.")

        while len(contacts) < 3:
            print(f"\n👤 Emergency Contact #{len(contacts) + 1}")

            name = input("Name: ").strip()
            if not name:
                break

            phone = input("Phone number: ").strip()
            relationship = input("Relationship (e.g., Family, Friend, Doctor): ").strip()

            contact = {
                "name": name,
                "phone": phone,
                "relationship": relationship,
                "priority": len(contacts) + 1
            }

            contacts.append(contact)
            print(f"✅ Added {name} as emergency contact #{len(contacts)}")

            if len(contacts) >= 3:
                break

            add_more = input("\nAdd another contact? (y/N): ").lower().strip()
            if add_more != 'y':
                break

        if contacts:
            self.monitor.set_emergency_contacts(contacts)
            print(f"\n✅ Configured {len(contacts)} emergency contacts")

            # Save to config
            config = self.load_existing_config()
            config['emergency_contacts'] = contacts
            self.save_config(config)
        else:
            print("⚠️  No emergency contacts configured")

        return contacts

    def test_health_data_flow(self):
        """Test that health data is flowing properly."""
        print("\n🧪 Testing Health Data Flow")
        print("=" * 30)

        # Start monitoring briefly to test
        print("📡 Starting health monitoring for 30 seconds...")

        try:
            self.monitor.start_monitoring()

            # Wait a bit for data to sync
            print("⏳ Waiting for health data sync...")
            time.sleep(5)

            # Check status
            status = self.monitor.get_health_status()

            if status.get('status') == 'no_data':
                print("📭 No health data available yet")
                print("This is normal if you just set up the API")
                print("Data will sync automatically in the background")
            else:
                print("✅ Health data is flowing!")
                print(f"📊 Latest data: {status}")

            # Get health tips
            tips = self.monitor.get_health_tips()
            if tips:
                print("\n💡 Sample health tips:")
                for tip in tips[:2]:  # Show first 2 tips
                    print(f"   • {tip}")

            # Test health-aware response
            test_input = "How am I feeling today?"
            response = self.monitor.get_health_aware_response(test_input)
            if response:
                print("\n🗣️  Sample response:")
                print(f"   '{response}'")

        except Exception as e:
            print(f"❌ Test failed: {e}")
        finally:
            # Stop monitoring
            self.monitor.stop_monitoring()
            print("✅ Health monitoring test completed")

    def show_status(self):
        """Show current setup status."""
        print("\n📊 Current Setup Status")
        print("=" * 25)

        config = self.load_existing_config()

        # Samsung Health status
        samsung = config.get('samsung_health', {})
        status = "✅ Connected" if samsung.get('authenticated') else "❌ Not Connected"
        print(f"🏥 Samsung Health: {status}")

        # Banking status
        banking = config.get('banking', {})
        status = "✅ Configured" if banking.get('configured') else "❌ Not Configured"
        print(f"🏦 Banking: {status}")

        # Emergency contacts
        contacts = config.get('emergency_contacts', [])
        status = f"✅ {len(contacts)} contacts" if contacts else "❌ None"
        print(f"🚨 Emergency Contacts: {status}")

        # Service status
        service_status = self.monitor.get_service_status()
        monitoring = "✅ Active" if service_status['monitoring_active'] else "❌ Inactive"
        print(f"📡 Health Monitoring: {monitoring}")

    def run_setup_wizard(self):
        """Run the complete setup wizard."""
        print("🚀 Real API Setup Wizard")
        print("=" * 30)
        print("This will help you connect your actual health and banking data.")

        # Show current status
        self.show_status()

        # Setup Samsung Health
        print("\n" + "="*50)
        samsung_result = self.setup_samsung_health()

        # Setup Banking
        print("\n" + "="*50)
        banking_result = self.setup_banking_api()

        # Setup Emergency Contacts
        print("\n" + "="*50)
        contacts_result = self.setup_emergency_contacts()

        # Test the setup
        if samsung_result:
            print("\n" + "="*50)
            self.test_health_data_flow()

        # Final status
        print("\n" + "="*50)
        self.show_status()

        print("\n🎉 Setup Complete!")
        print("\n📋 Next Steps:")
        print("1. Health data will sync automatically every 5 minutes")
        print("2. Use voice commands like 'How am I feeling?' to get health updates")
        print("3. Emergency contacts are ready for critical situations")
        print("4. Monitor your health status with 'Check my health status'")

        if not samsung_result:
            print("\n⚠️  Note: Complete Samsung Health setup to get real health data")

def main():
    """Main setup function."""
    try:
        setup = APISetup()
        setup.run_setup_wizard()

    except KeyboardInterrupt:
        print("\n\n👋 Setup cancelled by user")
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
