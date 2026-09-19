"""Centralized provider authentication management and credential verification."""

from __future__ import annotations

from enum import StrEnum
import os
import re
from typing import Any


class AuthErrorCode(StrEnum):
    AUTH_MISSING = "AUTH_MISSING"
    AUTH_INVALID = "AUTH_INVALID"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    AUTH_FORBIDDEN = "AUTH_FORBIDDEN"
    AUTH_RATE_LIMITED = "AUTH_RATE_LIMITED"


class AuthResult:
    """Result of credential inspection and validation."""

    def __init__(
        self,
        valid: bool,
        provider: str,
        error_code: AuthErrorCode | None = None,
        message: str = "",
    ) -> None:
        self.valid = valid
        self.provider = provider
        self.error_code = error_code
        self.message = message

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "provider": self.provider,
            "error_code": self.error_code.value if self.error_code else None,
            "message": self.message,
        }


def mask_secret(secret: str | None) -> str:
    """Safely mask API key or token for logging."""
    if not secret:
        return "[NOT_SET]"
    clean = str(secret).strip()
    if len(clean) <= 6:
        return "***"
    return f"{clean[:3]}...{clean[-3:]}"


class ProviderAuthManager:
    """Authoritative manager resolving and validating environment-only provider credentials."""

    PROVIDER_ENV_VARS = {
        "gemini": "GEMINI_API_KEY",
        "youtube": "YOUTUBE_API_KEY",
        "news_api": "NEWS_API_KEY",
        "newsapi": "NEWS_API_KEY",
    }

    @classmethod
    def get_api_key(cls, provider: str, env_var: str | None = None) -> str | None:
        """Resolve API key strictly from environment variables."""
        target_var = env_var or cls.PROVIDER_ENV_VARS.get(provider.lower())
        if not target_var:
            return None
        val = os.environ.get(target_var, "").strip()
        return val or None

    @classmethod
    def validate_provider_auth(cls, provider: str, env_var: str | None = None) -> AuthResult:
        """Validate credentials for a provider with specific failure classifications."""
        prov = provider.lower()
        key = cls.get_api_key(prov, env_var=env_var)

        if not key:
            return AuthResult(
                valid=False,
                provider=prov,
                error_code=AuthErrorCode.AUTH_MISSING,
                message=f"Environment variable for {prov} credentials is not set.",
            )

        # Detect placeholders or invalid formatting
        if key in {"PLACEHOLDER", "YOUR_KEY_HERE", "NONE", "test", "dummy"} or " " in key:
            return AuthResult(
                valid=False,
                provider=prov,
                error_code=AuthErrorCode.AUTH_INVALID,
                message=f"Credentials for {prov} contain invalid placeholder or spacing.",
            )

        if len(key) < 8:
            return AuthResult(
                valid=False,
                provider=prov,
                error_code=AuthErrorCode.AUTH_INVALID,
                message=f"Credentials for {prov} are too short to be a valid token.",
            )

        return AuthResult(valid=True, provider=prov, message="Credentials structurally valid.")

    @classmethod
    def sanitize_headers(cls, headers: dict[str, str]) -> dict[str, str]:
        """Redact authorization or token headers from request dictionaries."""
        sanitized = {}
        for k, v in headers.items():
            if re.search(r"auth|token|key|secret", k, re.IGNORECASE):
                sanitized[k] = mask_secret(v)
            else:
                sanitized[k] = v
        return sanitized
