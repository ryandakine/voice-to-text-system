# Health Integration Module

A comprehensive health monitoring system that integrates Samsung Health and Whoop data with voice-to-text applications to provide health-aware responses and real-time monitoring.

## 🚀 Features

- **Multi-Service Integration**: Connect with Samsung Health and Whoop APIs
- **Real-time Health Monitoring**: Continuous health data synchronization
- **Health-Aware Responses**: Context-aware voice responses based on health state
- **Secure Data Storage**: Encrypted storage for sensitive health information
- **Emergency Protocols**: Automated emergency response system
- **Customizable Alerts**: Configurable health thresholds and notifications
- **Voice Modifications**: Adjust voice parameters based on health state

## 📦 Installation

### Requirements

```bash
pip install cryptography keyring requests python-dotenv
```

### Quick Setup

```bash
# Clone or navigate to the health integration module
cd src/health_integration

# Install dependencies
npm install  # For linting tools
pip install -r requirements.txt  # For Python dependencies
```

## 🔧 Configuration

### 1. API Credentials Setup

#### Samsung Health
1. Register your application at [Samsung Health Developer Portal](https://developer.samsung.com/health)
2. Get your Client ID and Client Secret
3. Configure the integration:

```python
from health_integration import HealthMonitor

monitor = HealthMonitor()
monitor.configure_service("samsung_health", {
    "client_id": "your_client_id",
    "client_secret": "your_client_secret",
    "redirect_uri": "http://localhost:8080/callback/samsung"
})
```

#### Whoop
1. Register your application at [Whoop Developer Portal](https://developer.whoop.com)
2. Get your Client ID and Client Secret
3. Configure the integration:

```python
monitor.configure_service("whoop", {
    "client_id": "your_client_id",
    "client_secret": "your_client_secret",
    "redirect_uri": "http://localhost:8080/callback/whoop"
})
```

### 2. OAuth Authentication

For both services, complete OAuth authentication:

```python
# Get authorization URL
auth_url = monitor.get_auth_url("samsung_health")  # or "whoop"
print(f"Visit: {auth_url}")

# After user authorizes, exchange code for tokens
auth_code = "authorization_code_from_callback"
monitor.authenticate_service("samsung_health", auth_code)
```

## 🚀 Usage

### Basic Integration

```python
from health_integration import HealthMonitor

# Initialize health monitor
monitor = HealthMonitor()

# Start monitoring
monitor.start_monitoring()

# Get health-aware response
user_input = "How am I feeling today?"
response = monitor.get_health_aware_response(user_input)
print(response)  # "Here's your current health status: Your heart rate is 72 bpm..."

# Get voice modifications based on health state
voice_mods = monitor.get_voice_modifications()
# Returns: {"speed": "slow", "tone": "calm"} if user is stressed

# Get personalized health tips
tips = monitor.get_health_tips()
# Returns: ["Focus on recovery today", "Consider light walking"]
```

### Advanced Features

#### Emergency Contacts Setup

```python
contacts = [
    {
        "name": "Emergency Contact 1",
        "phone": "+1234567890",
        "relationship": "Family",
        "priority": 1
    }
]

monitor.set_emergency_contacts(contacts)
```

#### Custom Alert Callbacks

```python
def handle_alert(alert):
    print(f"Alert: {alert['message']}")
    if alert['severity'] == 'critical':
        # Trigger emergency protocol
        monitor.trigger_emergency_protocol("Critical health alert")

monitor.add_alert_callback(handle_alert)
```

#### Health Data Export

```python
# Export all health data
export_data = monitor.export_health_data()

# Contains: current status, health tips, emergency contacts, configuration
with open('health_backup.json', 'w') as f:
    json.dump(export_data, f, indent=2)
```

## 📊 Health Metrics Tracked

### Samsung Health Data
- **Heart Rate**: Real-time heart rate monitoring
- **Steps**: Daily step count
- **Sleep**: Sleep duration and quality
- **Stress Level**: Current stress assessment
- **Blood Pressure**: Systolic/diastolic readings
- **Calories**: Energy expenditure
- **Distance**: Walking/running distance

### Whoop Data
- **Recovery Score**: Overall recovery status (0-100)
- **Strain Score**: Daily strain level
- **HRV**: Heart rate variability
- **Sleep Metrics**: Sleep stages and quality
- **Workout Data**: Exercise intensity and duration
- **Body Measurements**: Weight, body fat percentage

## 🎯 Health-Aware Responses

The system provides context-aware responses based on:

### Health States
- **Normal**: Standard responses
- **Fatigued**: Suggests rest and recovery
- **Stressed**: Offers relaxation techniques
- **High Heart Rate**: Recommends breaks and rest
- **Low Energy**: Suggests energizing activities
- **Good Recovery**: Encourages activity
- **Emergency**: Triggers emergency protocols

### Voice Modifications
- **Emergency**: Slow, loud, urgent tone
- **Fatigued**: Slow, soft, calm tone
- **Stressed**: Slow, calm with longer pauses

### Response Examples

```
User: "How am I feeling?"
System: "Here's your current health status: Your heart rate is 72 bpm.
         Your recovery score is 85.3/100. You're in great shape today!"

User: "I'm feeling stressed"
System: "I can see you're feeling stressed. Let me guide you through
         a breathing exercise: Inhale for 4 counts, hold for 4,
         exhale for 4. Would you like me to continue guiding you?"
```

## 🔐 Security & Privacy

### Data Encryption
- All health data is encrypted using Fernet (AES 128)
- API credentials stored securely using system keyring
- Master encryption keys protected with PBKDF2

### Privacy Controls
- Local data storage only (no cloud sync by default)
- Data anonymization options available
- Configurable data retention policies
- Emergency contact information encrypted

### Security Features
- OAuth 2.0 authentication for all services
- Secure token refresh mechanisms
- Input validation and sanitization
- Rate limiting and error handling

## ⚠️ Alert System

### Default Alerts
- **Heart Rate High**: > 100 bpm (medium priority)
- **Heart Rate Critical**: > 120 bpm (high priority)
- **Recovery Low**: < 33 (low priority)
- **Strain High**: > 17 (medium priority)
- **Sleep Low**: < 7 hours (low priority)
- **Stress High**: > 70 (medium priority)

### Custom Alerts
```python
from health_integration import HealthAlert

custom_alert = HealthAlert(
    alert_type="custom_exercise",
    condition="steps < 5000",
    threshold=5000,
    message="You haven't reached your daily step goal yet.",
    severity="low"
)

# Add to monitoring system
# (Implementation depends on specific use case)
```

## 🧪 Testing

### Run the Demo
```bash
python src/health_integration_example.py
```

### Unit Tests
```bash
# Run health integration tests
python -m pytest tests/health_integration/

# Run with coverage
python -m pytest --cov=src/health_integration tests/health_integration/
```

## 🔧 API Reference

### HealthMonitor Class

#### Methods
- `configure_service(service, config)`: Configure a health service
- `authenticate_service(service, auth_code)`: Complete OAuth authentication
- `start_monitoring()`: Start health data monitoring
- `stop_monitoring()`: Stop health monitoring
- `get_health_status()`: Get current health status
- `get_health_aware_response(user_input)`: Get health-aware response
- `get_voice_modifications()`: Get voice parameter modifications
- `get_health_tips()`: Get personalized health tips
- `set_emergency_contacts(contacts)`: Set emergency contacts
- `trigger_emergency_protocol(reason)`: Trigger emergency response

### HealthDataSync Class

#### Methods
- `sync_health_data()`: Synchronize data from all sources
- `get_current_health_status()`: Get latest health metrics
- `setup_default_alerts()`: Configure default health alerts

### HealthAwareResponses Class

#### Methods
- `get_health_aware_response(user_input)`: Generate health-aware response
- `get_current_health_context()`: Get current health context
- `should_modify_voice_parameters(context)`: Determine voice modifications

## 📈 Performance

### Sync Intervals
- **Health Data**: Every 5 minutes (configurable)
- **Alert Checks**: Every 1 minute (configurable)
- **Data Retention**: 30 days (configurable)

### Resource Usage
- **Memory**: ~50MB for typical usage
- **CPU**: Minimal background processing
- **Storage**: ~10MB per month of health data
- **Network**: ~1MB per day for data sync

## 🐛 Troubleshooting

### Common Issues

#### Authentication Failures
```python
# Check service status
status = monitor.get_service_status()
print(status)

# Re-authenticate if needed
auth_url = monitor.get_auth_url("samsung_health")
# Visit URL and re-authenticate
```

#### Data Sync Issues
```python
# Check API connectivity
try:
    monitor.health_sync.sync_health_data()
    print("Sync successful")
except Exception as e:
    print(f"Sync failed: {e}")
```

#### Storage Issues
```python
# Validate storage integrity
integrity = monitor.storage.validate_storage_integrity()
print(integrity)
```

## 📚 Examples

See `src/health_integration_example.py` for a complete integration example that demonstrates:

- Service configuration and authentication
- Health monitoring setup
- Alert handling
- Health-aware responses
- Emergency contact management
- Data export functionality

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all linting passes
6. Submit a pull request

## 📄 License

This health integration module is part of the Voice-to-Text System and follows the same licensing terms.

## 🆘 Support

For issues and questions:

1. Check the troubleshooting section above
2. Review the example implementations
3. Open an issue on the project repository
4. Check the documentation in the main project

---

**Note**: This module handles sensitive health data. Always ensure compliance with relevant privacy laws (HIPAA, GDPR, etc.) and obtain proper user consent before collecting or processing health information.

