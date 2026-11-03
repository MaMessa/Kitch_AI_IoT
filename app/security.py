# Import secure random token generation and digest tools.
import hashlib  # Hash raw browser tokens before they reach the database.
import secrets  # Generate unpredictable session tokens.
# Import the password hashing implementation recommended for new FastAPI projects.
from pwdlib import PasswordHash  # Use Argon2 for new password hashes.


# Reuse one configured password hasher across requests.
password_hasher = PasswordHash.recommended()  # Select a modern password hashing algorithm.


# Hash a user's password before storing it.
def hash_password(password: str) -> str:  # Convert a password into a non-reversible Argon2 hash.
    return password_hasher.hash(password)  # Return only the encoded hash for persistence.


# Check a login password against its stored hash.
def verify_password(password: str, password_hash: str) -> bool:  # Compare without exposing the original password.
    return password_hasher.verify(password, password_hash)  # Return whether the submitted password matches.


# Create a raw cookie token and its database-safe digest.
def create_session_token() -> tuple[str, str]:  # Return the browser token and the digest stored by KitchAI.
    raw_token = secrets.token_urlsafe(32)  # Generate a cryptographically strong random token.
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()  # Hash the token so a DB leak does not reveal usable cookies.
    return raw_token, token_hash  # Send the raw form only to the browser and persist the digest.


# Hash a presented browser token before looking up its session.
def hash_session_token(raw_token: str) -> str:  # Convert a cookie value to the matching database digest.
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()  # Return a stable SHA-256 hexadecimal digest.
