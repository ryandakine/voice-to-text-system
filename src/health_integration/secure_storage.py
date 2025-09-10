"""
Secure Storage for Health Integration

Provides secure storage and management for API credentials,
health data, and sensitive user information.
"""

import os
import json
import base64
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import secrets
import keyring
from pathlib import Path

logger = logging.getLogger(__name__)

class SecureStorage:
    """Secure storage for health integration data."""

    def __init__(self, storage_dir: str = "~/.config/voice-to-text/health"):
        self.storage_dir = Path(storage_dir).expanduser()
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Use system keyring for master key storage
        self.service_name = "voice-to-text-health"
        self.master_key = self._get_or_create_master_key()

        # Initialize encryption
        self.fernet = Fernet(self.master_key)

    def _get_or_create_master_key(self) -> bytes:
        """Get existing master key or create a new one."""
        try:
            # Try to get existing key from system keyring
            stored_key = keyring.get_password(self.service_name, "master_key")
            if stored_key:
                return stored_key.encode()
        except Exception as e:
            logger.warning(f"Could not access system keyring: {e}")

        # Create new key if none exists
        key = Fernet.generate_key()

        try:
            # Store in system keyring
            keyring.set_password(self.service_name, "master_key", key.decode())
        except Exception as e:
            logger.warning(f"Could not store key in system keyring: {e}")
            # Fallback: store in encrypted file
            self._store_key_fallback(key)

        return key

    def _store_key_fallback(self, key: bytes) -> None:
        """Fallback storage for master key when keyring is unavailable."""
        key_file = self.storage_dir / "master_key.enc"

        # Use a simple password-based encryption for the fallback
        password = self._get_device_password()
        salt = secrets.token_bytes(16)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        fallback_key = base64.urlsafe_b64encode(kdf.derive(password.encode()))

        fernet_fallback = Fernet(fallback_key)
        encrypted_key = fernet_fallback.encrypt(key)

        with open(key_file, 'wb') as f:
            f.write(salt + encrypted_key)

    def _get_device_password(self) -> str:
        """Get or create a device-specific password."""
        password_file = self.storage_dir / "device_password"

        if password_file.exists():
            with open(password_file, 'r') as f:
                return f.read().strip()

        # Generate a secure password
        password = secrets.token_urlsafe(32)

        with open(password_file, 'w') as f:
            f.write(password)

        # Make password file readable only by owner
        password_file.chmod(0o600)

        return password

    def _encrypt_data(self, data: str) -> str:
        """Encrypt data using Fernet."""
        return self.fernet.encrypt(data.encode()).decode()

    def _decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt data using Fernet."""
        return self.fernet.decrypt(encrypted_data.encode()).decode()

    def store_api_credentials(self, service: str, credentials: Dict[str, Any]) -> None:
        """Store API credentials securely."""
        credentials_file = self.storage_dir / f"{service}_credentials.enc"

        # Add metadata
        credentials_data = {
            "service": service,
            "credentials": credentials,
            "stored_at": datetime.now().isoformat(),
            "version": "1.0"
        }

        # Encrypt and store
        json_data = json.dumps(credentials_data)
        encrypted_data = self._encrypt_data(json_data)

        with open(credentials_file, 'w') as f:
            f.write(encrypted_data)

        # Secure the file permissions
        credentials_file.chmod(0o600)

        logger.info(f"API credentials stored securely for {service}")

    def get_api_credentials(self, service: str) -> Optional[Dict[str, Any]]:
        """Retrieve API credentials securely."""
        credentials_file = self.storage_dir / f"{service}_credentials.enc"

        if not credentials_file.exists():
            return None

        try:
            with open(credentials_file, 'r') as f:
                encrypted_data = f.read()

            json_data = self._decrypt_data(encrypted_data)
            credentials_data = json.loads(json_data)

            return credentials_data.get("credentials")

        except Exception as e:
            logger.error(f"Failed to retrieve credentials for {service}: {e}")
            return None

    def update_api_tokens(self, service: str, tokens: Dict[str, Any]) -> None:
        """Update OAuth tokens for a service."""
        existing_credentials = self.get_api_credentials(service) or {}

        # Update tokens
        existing_credentials.update({
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "token_expiry": tokens.get("expires_in"),
            "updated_at": datetime.now().isoformat()
        })

        self.store_api_credentials(service, existing_credentials)

    def store_health_data(self, data_type: str, data: Dict[str, Any]) -> None:
        """Store health data securely."""
        data_file = self.storage_dir / f"health_{data_type}.enc"

        # Add metadata
        health_data = {
            "data_type": data_type,
            "data": data,
            "stored_at": datetime.now().isoformat(),
            "version": "1.0"
        }

        # Encrypt and store
        json_data = json.dumps(health_data)
        encrypted_data = self._encrypt_data(json_data)

        with open(data_file, 'w') as f:
            f.write(encrypted_data)

        # Secure the file permissions
        data_file.chmod(0o600)

    def get_health_data(self, data_type: str) -> Optional[Dict[str, Any]]:
        """Retrieve health data securely."""
        data_file = self.storage_dir / f"health_{data_type}.enc"

        if not data_file.exists():
            return None

        try:
            with open(data_file, 'r') as f:
                encrypted_data = f.read()

            json_data = self._decrypt_data(encrypted_data)
            health_data = json.loads(json_data)

            return health_data.get("data")

        except Exception as e:
            logger.error(f"Failed to retrieve health data for {data_type}: {e}")
            return None

    def store_user_profile(self, profile: Dict[str, Any]) -> None:
        """Store user profile information securely."""
        self.store_health_data("user_profile", profile)

    def get_user_profile(self) -> Optional[Dict[str, Any]]:
        """Retrieve user profile information."""
        return self.get_health_data("user_profile")

    def store_emergency_contacts(self, contacts: List[Dict[str, Any]]) -> None:
        """Store emergency contact information."""
        self.store_health_data("emergency_contacts", {"contacts": contacts})

    def get_emergency_contacts(self) -> List[Dict[str, Any]]:
        """Retrieve emergency contact information."""
        data = self.get_health_data("emergency_contacts")
        return data.get("contacts", []) if data else []

    def clear_service_data(self, service: str) -> None:
        """Clear all data for a specific service."""
        credentials_file = self.storage_dir / f"{service}_credentials.enc"

        if credentials_file.exists():
            credentials_file.unlink()
            logger.info(f"Cleared credentials for {service}")

    def list_stored_services(self) -> List[str]:
        """List all services with stored credentials."""
        services = []

        for file_path in self.storage_dir.glob("*_credentials.enc"):
            service_name = file_path.stem.replace("_credentials", "")
            services.append(service_name)

        return services

    def export_configuration(self) -> Dict[str, Any]:
        """Export configuration for backup (without sensitive data)."""
        config = {
            "services": self.list_stored_services(),
            "storage_dir": str(self.storage_dir),
            "exported_at": datetime.now().isoformat(),
            "version": "1.0"
        }

        return config

    def validate_storage_integrity(self) -> Dict[str, Any]:
        """Validate storage integrity and report status."""
        status = {
            "storage_dir_exists": self.storage_dir.exists(),
            "storage_dir_writable": os.access(self.storage_dir, os.W_OK),
            "services_count": len(self.list_stored_services()),
            "total_files": len(list(self.storage_dir.glob("*.enc"))),
            "last_check": datetime.now().isoformat()
        }

        return status
