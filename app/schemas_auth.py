# Import annotated field constraints for request validation.
from typing import Annotated  # Attach validation rules directly to request fields.
# Import Pydantic schema tools and email syntax validation.
from pydantic import BaseModel, EmailStr, Field  # Validate incoming data and shape public account responses.


# Describe the data required to create a password-based account.
class RegisterRequest(BaseModel):  # Validate a new account registration request.
    email: EmailStr  # Require and normalize a syntactically valid email address.
    password: Annotated[str, Field(min_length=12, max_length=128)]  # Require a long password and bound hashing work.
    first_name: Annotated[str, Field(min_length=1, max_length=100)]  # Require a short first name.
    last_name: Annotated[str | None, Field(max_length=100)] = None  # Allow an optional last name.


# Describe the data required for an email/password login.
class LoginRequest(BaseModel):  # Validate a login attempt.
    email: EmailStr  # Require a syntactically valid email address for sign-in.
    password: Annotated[str, Field(min_length=1, max_length=128)]  # Bound password input before verification.


# Validate requests that ask KitchAI to email an account action link.
class EmailActionRequest(BaseModel):  # Accept an email for verification resend or password recovery.
    email: EmailStr  # Require a syntactically valid address.


# Validate a one-time action token submitted by the frontend.
class EmailTokenRequest(BaseModel):  # Accept a token from a verification link.
    token: Annotated[str, Field(min_length=20, max_length=200)]  # Bound the opaque random token input.


# Validate a password-reset token together with its new password.
class PasswordResetRequest(BaseModel):  # Accept a reset link token and replacement password.
    token: Annotated[str, Field(min_length=20, max_length=200)]  # Require the one-time reset token.
    new_password: Annotated[str, Field(min_length=12, max_length=128)]  # Apply the same password limits as registration.


# Return only non-secret account details to the browser.
class UserPublic(BaseModel):  # Shape the authenticated user profile.
    id: int  # Return the stable account identifier.
    email: EmailStr  # Return the account email address.
    first_name: str  # Return the account holder's first name.
    last_name: str | None  # Return the optional last name.
    is_admin: bool  # Expose the role flag for later frontend authorization display.
    email_verified: bool  # Tell the frontend whether email-gated actions are available.


# Return a generic status message for email workflows.
class AuthMessage(BaseModel):  # Keep responses consistent without revealing account existence.
    message: str  # Explain that the request was accepted or completed.
