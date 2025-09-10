"""
Samsung Health API Integration

Handles authentication and data retrieval from Samsung Health API.
"""

import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
import os

logger = logging.getLogger(__name__)

class SamsungHealthAPI:
    """Samsung Health API client for retrieving health data."""

    BASE_URL = "https://api.samsunghealth.com"
    AUTH_URL = "https://oauth.samsunghealth.com"

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None

    def get_authorization_url(self) -> str:
        """Generate OAuth2 authorization URL."""
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': 'com.samsung.health.*'
        }
        auth_url = f"{self.AUTH_URL}/authorize?" + '&'.join([f"{k}={v}" for k, v in params.items()])
        return auth_url

    def exchange_code_for_token(self, authorization_code: str) -> Dict[str, Any]:
        """Exchange authorization code for access token."""
        data = {
            'grant_type': 'authorization_code',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.redirect_uri,
            'code': authorization_code
        }

        response = requests.post(f"{self.AUTH_URL}/token", data=data)
        response.raise_for_status()

        token_data = response.json()
        self.access_token = token_data['access_token']
        self.refresh_token = token_data.get('refresh_token')
        self.token_expiry = datetime.now() + timedelta(seconds=token_data['expires_in'])

        return token_data

    def refresh_access_token(self) -> bool:
        """Refresh expired access token."""
        if not self.refresh_token:
            return False

        data = {
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token
        }

        try:
            response = requests.post(f"{self.AUTH_URL}/token", data=data)
            response.raise_for_status()

            token_data = response.json()
            self.access_token = token_data['access_token']
            self.refresh_token = token_data.get('refresh_token')
            self.token_expiry = datetime.now() + timedelta(seconds=token_data['expires_in'])
            return True
        except Exception as e:
            logger.error(f"Failed to refresh token: {e}")
            return False

    def _ensure_valid_token(self) -> None:
        """Ensure we have a valid access token."""
        if not self.access_token or (self.token_expiry and datetime.now() >= self.token_expiry):
            if not self.refresh_access_token():
                raise Exception("No valid access token and refresh failed")

    def get_health_data(self, data_type: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Retrieve specific health data from Samsung Health."""
        self._ensure_valid_token()

        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }

        params = {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        }

        url = f"{self.BASE_URL}/health-data/{data_type}"
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        return response.json()

    def get_heart_rate_data(self, hours: int = 24) -> List[Dict]:
        """Get heart rate data for the last N hours."""
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=hours)
        return self.get_health_data('heart_rate', start_date, end_date)

    def get_steps_data(self, days: int = 7) -> List[Dict]:
        """Get step count data for the last N days."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return self.get_health_data('steps', start_date, end_date)

    def get_sleep_data(self, days: int = 7) -> List[Dict]:
        """Get sleep data for the last N days."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return self.get_health_data('sleep', start_date, end_date)

    def get_stress_data(self, hours: int = 24) -> List[Dict]:
        """Get stress level data for the last N hours."""
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=hours)
        return self.get_health_data('stress', start_date, end_date)

    def get_blood_pressure_data(self, days: int = 30) -> List[Dict]:
        """Get blood pressure data for the last N days."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return self.get_health_data('blood_pressure', start_date, end_date)

