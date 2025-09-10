"""
Whoop API Integration

Handles authentication and data retrieval from Whoop API.
"""

import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
import base64

logger = logging.getLogger(__name__)

class WhoopAPI:
    """Whoop API client for retrieving fitness and health data."""

    BASE_URL = "https://api.prod.whoop.com"
    AUTH_URL = "https://api.prod.whoop.com/oauth"

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
            'scope': 'read:profile read:recovery read:cycles read:workout read:sleep'
        }
        auth_url = f"{self.AUTH_URL}/authorize?" + '&'.join([f"{k}={v}" for k, v in params.items()])
        return auth_url

    def exchange_code_for_token(self, authorization_code: str) -> Dict[str, Any]:
        """Exchange authorization code for access token."""
        auth_string = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()

        headers = {
            'Authorization': f'Basic {auth_string}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        data = {
            'grant_type': 'authorization_code',
            'redirect_uri': self.redirect_uri,
            'code': authorization_code
        }

        response = requests.post(f"{self.AUTH_URL}/token", headers=headers, data=data)
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

        auth_string = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()

        headers = {
            'Authorization': f'Basic {auth_string}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token
        }

        try:
            response = requests.post(f"{self.AUTH_URL}/token", headers=headers, data=data)
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

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make authenticated API request."""
        self._ensure_valid_token()

        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }

        url = f"{self.BASE_URL}{endpoint}"
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        return response.json()

    def get_user_profile(self) -> Dict[str, Any]:
        """Get user profile information."""
        return self._make_request("/user/profile")

    def get_recovery_data(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[Dict]:
        """Get recovery data for specified date range."""
        params = {}
        if start_date:
            params['start'] = start_date.isoformat()
        if end_date:
            params['end'] = end_date.isoformat()

        response = self._make_request("/recovery", params)
        return response.get('records', [])

    def get_cycles_data(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[Dict]:
        """Get menstrual cycle data for specified date range."""
        params = {}
        if start_date:
            params['start'] = start_date.isoformat()
        if end_date:
            params['end'] = end_date.isoformat()

        response = self._make_request("/cycles", params)
        return response.get('records', [])

    def get_workout_data(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[Dict]:
        """Get workout data for specified date range."""
        params = {}
        if start_date:
            params['start'] = start_date.isoformat()
        if end_date:
            params['end'] = end_date.isoformat()

        response = self._make_request("/workouts", params)
        return response.get('records', [])

    def get_sleep_data(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[Dict]:
        """Get sleep data for specified date range."""
        params = {}
        if start_date:
            params['start'] = start_date.isoformat()
        if end_date:
            params['end'] = end_date.isoformat()

        response = self._make_request("/sleeps", params)
        return response.get('records', [])

    def get_body_measurements(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[Dict]:
        """Get body measurements for specified date range."""
        params = {}
        if start_date:
            params['start'] = start_date.isoformat()
        if end_date:
            params['end'] = end_date.isoformat()

        response = self._make_request("/body", params)
        return response.get('records', [])

    # Convenience methods for recent data
    def get_recent_recovery(self, days: int = 7) -> List[Dict]:
        """Get recovery data for the last N days."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return self.get_recovery_data(start_date, end_date)

    def get_recent_workouts(self, days: int = 7) -> List[Dict]:
        """Get workout data for the last N days."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return self.get_workout_data(start_date, end_date)

    def get_recent_sleep(self, days: int = 7) -> List[Dict]:
        """Get sleep data for the last N days."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return self.get_sleep_data(start_date, end_date)

    def get_current_recovery_score(self) -> Optional[float]:
        """Get the most recent recovery score."""
        recovery_data = self.get_recent_recovery(1)
        if recovery_data:
            latest = recovery_data[-1]  # Most recent
            return latest.get('score')
        return None

    def get_current_strain_score(self) -> Optional[float]:
        """Get the most recent strain score."""
        recovery_data = self.get_recent_recovery(1)
        if recovery_data:
            latest = recovery_data[-1]  # Most recent
            return latest.get('strain')
        return None

