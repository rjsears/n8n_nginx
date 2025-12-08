"""
Security utilities: password hashing, encryption, token generation.
"""

import secrets
import hashlib
import base64
from datetime import datetime, timedelta, UTC
from typing import Optional, Tuple
from passlib.context import CryptContext
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import ipaddress
import logging

from api.config import settings

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.bcrypt_rounds,
)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def generate_session_token() -> str:
    """Generate a secure random session token (64 chars)."""
    return secrets.token_urlsafe(48)


def generate_api_key() -> str:
    """Generate a secure API key."""
    return secrets.token_urlsafe(32)


class EncryptionService:
    """AES-256-GCM encryption for sensitive data."""

    def __init__(self, master_key: str):
        """Initialize with master encryption key."""
        # Derive a proper 32-byte key from the master key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"n8n-management-salt",  # Static salt for deterministic key
            iterations=100000,
        )
        self._key = kdf.derive(master_key.encode())
        self._aesgcm = AESGCM(self._key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string, returning base64-encoded ciphertext."""
        if not plaintext:
            return plaintext

        nonce = secrets.token_bytes(12)  # 96-bit nonce for GCM
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode(), None)

        # Combine nonce + ciphertext and base64 encode
        combined = nonce + ciphertext
        return base64.b64encode(combined).decode()

    def decrypt(self, encrypted: str) -> str:
        """Decrypt a base64-encoded ciphertext."""
        if not encrypted:
            return encrypted

        try:
            combined = base64.b64decode(encrypted.encode())
            nonce = combined[:12]
            ciphertext = combined[12:]

            plaintext = self._aesgcm.decrypt(nonce, ciphertext, None)
            return plaintext.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Failed to decrypt data")


# Global encryption service instance
encryption_service = EncryptionService(settings.encryption_key)


def encrypt_value(value: str) -> str:
    """Encrypt a sensitive value."""
    return encryption_service.encrypt(value)


def decrypt_value(encrypted: str) -> str:
    """Decrypt an encrypted value."""
    return encryption_service.decrypt(encrypted)


def is_ip_in_subnet(ip: str, cidr: str) -> bool:
    """Check if an IP address is within a CIDR subnet."""
    try:
        ip_obj = ipaddress.ip_address(ip)
        network = ipaddress.ip_network(cidr, strict=False)
        return ip_obj in network
    except ValueError:
        return False


def is_ip_allowed(ip: str, allowed_subnets: list[str]) -> bool:
    """Check if an IP is allowed based on subnet list."""
    if not allowed_subnets:
        return True  # No restrictions if empty

    for subnet in allowed_subnets:
        if is_ip_in_subnet(ip, subnet):
            return True
    return False


def calculate_lockout_expiry(failed_attempts: int) -> Optional[datetime]:
    """Calculate lockout expiry based on failed attempts."""
    if failed_attempts < settings.max_failed_attempts:
        return None

    # Exponential backoff: 30min, 1hr, 2hr, 4hr, max 24hr
    multiplier = min(2 ** (failed_attempts - settings.max_failed_attempts), 48)
    minutes = settings.lockout_minutes * multiplier

    return datetime.now(UTC) + timedelta(minutes=minutes)


def hash_file_sha256(filepath: str) -> str:
    """Calculate SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()
