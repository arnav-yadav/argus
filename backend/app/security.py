"""Per-service ingest tokens.

A token is shown once, when a service registers or rotates it. Only its SHA-256 digest
is stored, so a database leak does not let anyone forge heartbeats.
"""

import hashlib
import hmac
import secrets

TOKEN_PREFIX = "argus_"  # noqa: S105 - a public prefix, not a secret


def new_token() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(24)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token(token: str | None, expected_hash: str) -> bool:
    if not token:
        return False
    return hmac.compare_digest(hash_token(token), expected_hash)
