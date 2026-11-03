# Import timezone-aware date helpers and environment settings.
import os  # Read cookie security options from environment variables.
import logging  # Record provider failures without leaking tokens to API clients.
from datetime import datetime, timedelta, timezone  # Set and validate session expiration times.
# Import FastAPI request, response, dependency, and error helpers.
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status  # Build cookie-based authentication routes.
# Import SQLAlchemy query and transaction error helpers.
from sqlalchemy import select, update  # Query accounts and sessions and revoke prior action links.
from sqlalchemy.exc import IntegrityError  # Handle a duplicate-email race safely.
from sqlalchemy.orm import Session  # Type the request-scoped database session.
# Import project database, models, schemas, and security helpers.
from app.database import get_db  # Provide one database session for each request.
from app.email_service import EmailDeliveryError, send_account_action_email  # Send verification and password reset links through Resend.
from app.models import EmailActionToken, User, UserSession  # Read accounts and persist sessions and one-time action tokens.
from app.schemas_auth import AuthMessage, EmailActionRequest, EmailTokenRequest, LoginRequest, PasswordResetRequest, RegisterRequest, UserPublic  # Validate auth requests and safe response shapes.
from app.security import create_session_token, hash_password, hash_session_token, verify_password  # Hash passwords and session tokens.


# Centralize the browser cookie and session lifetime settings.
SESSION_COOKIE_NAME = "kitchai_session"  # Name the opaque browser cookie.
SESSION_LIFETIME = timedelta(days=14)  # Let a browser session last for two weeks.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"  # Require HTTPS cookies when deployment enables the setting.
router = APIRouter()  # Group authentication routes under one router.
logger = logging.getLogger(__name__)  # Keep provider errors in server logs without returning sensitive details.


# Convert an ORM account into a safe response schema.
def public_user(user: User) -> UserPublic:  # Exclude password hashes and internal timestamps.
    return UserPublic(id=user.id, email=user.email, first_name=user.first_name, last_name=user.last_name, is_admin=user.is_admin, email_verified=user.email_verified_at is not None)  # Return only fields needed by the signed-in interface.


# Create a database session and put its raw token into an HttpOnly cookie.
def start_session(user: User, db: Session, response: Response) -> None:  # Share session creation between registration and login.
    raw_token, token_hash = create_session_token()  # Generate a private cookie and the digest saved in PostgreSQL.
    expires_at = datetime.now(timezone.utc) + SESSION_LIFETIME  # Calculate the expiration in UTC.
    db.add(UserSession(user_id=user.id, token_hash=token_hash, expires_at=expires_at))  # Persist a revocable server-side session.
    db.commit()  # Save the session before returning a valid cookie.
    response.set_cookie(SESSION_COOKIE_NAME, raw_token, max_age=int(SESSION_LIFETIME.total_seconds()), httponly=True, secure=COOKIE_SECURE, samesite="lax", path="/")  # Keep JavaScript from reading the token and send it only to KitchAI.


# Create a fresh one-time token and invalidate older unused links of the same purpose.
def issue_action_token(user: User, purpose: str, lifetime: timedelta, db: Session) -> str:  # Keep only one active link per account and action.
    now = datetime.now(timezone.utc)  # Use one UTC timestamp for the update and new expiration.
    db.execute(update(EmailActionToken).where(EmailActionToken.user_id == user.id, EmailActionToken.purpose == purpose, EmailActionToken.consumed_at.is_(None)).values(consumed_at=now))  # Make older links unusable when a fresh one is issued.
    raw_token, token_hash = create_session_token()  # Reuse the secure random token generator and store only its digest.
    db.add(EmailActionToken(user_id=user.id, purpose=purpose, token_hash=token_hash, expires_at=now + lifetime))  # Persist a single-use token with an explicit expiry.
    return raw_token  # Return the raw token only to the email-building code.


# Lock and validate a one-time action token before changing an account.
def find_valid_action_token(raw_token: str, purpose: str, db: Session) -> EmailActionToken | None:  # Reject expired, consumed, unknown, or wrong-purpose links.
    token_hash = hash_session_token(raw_token)  # Hash the submitted token before querying PostgreSQL.
    return db.scalar(select(EmailActionToken).where(EmailActionToken.token_hash == token_hash, EmailActionToken.purpose == purpose, EmailActionToken.consumed_at.is_(None), EmailActionToken.expires_at > datetime.now(timezone.utc)).with_for_update())  # Lock a valid row to prevent simultaneous reuse.


# Resolve the current account from an unexpired, unrevoked session cookie.
def get_current_user(kitchai_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME), db: Session = Depends(get_db)) -> User:  # Protect routes that require a signed-in account.
    if not kitchai_session:  # Reject requests without a browser cookie.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Connexion requise.")  # Return a generic authentication error.
    token_hash = hash_session_token(kitchai_session)  # Hash the cookie before searching the database.
    session = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash, UserSession.revoked_at.is_(None), UserSession.expires_at > datetime.now(timezone.utc)))  # Find only active and unexpired sessions.
    if session is None:  # Reject unknown, expired, or revoked tokens.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalide ou expirée.")  # Ask the browser to sign in again.
    return session.user  # Return the account linked to this valid session.


# Create a new unverified account and sign it in immediately.
@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)  # Expose account registration.
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> UserPublic:  # Validate and persist a new account.
    normalized_email = str(payload.email).strip().lower()  # Normalize case so the same email cannot be registered twice by spelling.
    user = User(email=normalized_email, password_hash=hash_password(payload.password), first_name=payload.first_name.strip(), last_name=payload.last_name.strip() if payload.last_name else None, is_admin=False)  # Create a standard account that still needs email verification.
    db.add(user)  # Stage the account for insertion.
    try:  # Translate duplicate email conflicts into a stable API response.
        db.flush()  # Assign the new user's ID before creating its session.
        verification_token = issue_action_token(user, "verify_email", timedelta(hours=24), db)  # Prepare a verification link that expires after one day.
        start_session(user, db, response)  # Sign in the new user with a revocable cookie.
    except IntegrityError as error:  # Catch a duplicate email even if another registration raced this request.
        db.rollback()  # Undo the failed insert and any staged session.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cette adresse email possède déjà un compte.") from error  # Explain the conflict without exposing database details.
    try:  # Send the verification message after saving the account and its token.
        send_account_action_email(user.email, "Vérifiez votre adresse email KitchAI", verification_token, "verify-email", "Vérifier votre adresse email")  # Email the one-time link to the new account.
    except EmailDeliveryError as error:  # Handle missing Resend configuration or temporary provider failures.
        logger.exception("Échec d'envoi de l'email de vérification.")  # Keep the technical cause in server logs without logging the token.
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Le compte a été créé, mais l'email de vérification n'a pas pu être envoyé. Réessayez depuis la page de connexion.") from error  # Explain the partial success and point to the resend flow.
    return public_user(user)  # Return the safe profile without the password hash.


# Authenticate an existing account using its email and password.
@router.post("/login", response_model=UserPublic)  # Expose email/password sign-in.
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> UserPublic:  # Validate credentials and establish a session.
    normalized_email = str(payload.email).strip().lower()  # Apply the same normalization used at registration.
    user = db.scalar(select(User).where(User.email == normalized_email))  # Search for the account by its normalized email.
    valid_password = verify_password(payload.password, user.password_hash) if user and user.password_hash else False  # Verify only accounts with a password login configured.
    if not valid_password:  # Use one response for unknown emails and incorrect passwords.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email ou mot de passe incorrect.")  # Avoid disclosing which part of the credentials was wrong.
    start_session(user, db, response)  # Create a server-revocable session and set the cookie.
    return public_user(user)  # Return only the account's public profile.


# Return the profile associated with the browser's current session.
@router.get("/me", response_model=UserPublic)  # Expose the current signed-in account.
def read_current_user(user: User = Depends(get_current_user)) -> UserPublic:  # Require an active session cookie.
    return public_user(user)  # Return account details without credentials.


# Revoke the current session and clear the browser cookie.
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)  # Expose sign-out for the current browser.
def logout(response: Response, kitchai_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME), db: Session = Depends(get_db)) -> None:  # Revoke the session row before deleting its cookie.
    if kitchai_session:  # Revoke a matching session when a cookie is present.
        token_hash = hash_session_token(kitchai_session)  # Hash the presented cookie for the database lookup.
        session = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash, UserSession.revoked_at.is_(None)))  # Load an active session if it exists.
        if session is not None:  # Update only a real active session.
            session.revoked_at = datetime.now(timezone.utc)  # Make any copied cookie unusable immediately.
            db.commit()  # Persist the revocation before responding.
    response.delete_cookie(SESSION_COOKIE_NAME, path="/", secure=COOKIE_SECURE, httponly=True, samesite="lax")  # Remove the browser's copy of the session token.
    return None  # Complete sign-out even when there was no valid session cookie.


# Consume an email verification link and mark the account as verified.
@router.post("/email/verify", response_model=AuthMessage)  # Expose the one-time email verification action.
def verify_email(payload: EmailTokenRequest, db: Session = Depends(get_db)) -> AuthMessage:  # Verify ownership using the emailed token.
    action_token = find_valid_action_token(payload.token, "verify_email", db)  # Find and lock the active verification token.
    if action_token is None:  # Reject malformed, expired, reused, or incorrect-purpose tokens.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lien de vérification invalide ou expiré.")  # Ask the user to request another link.
    action_token.consumed_at = datetime.now(timezone.utc)  # Make this verification link single-use.
    action_token.user.email_verified_at = datetime.now(timezone.utc)  # Record when the email owner completed verification.
    db.commit()  # Atomically save the verification and token consumption.
    return AuthMessage(message="Adresse email vérifiée.")  # Confirm the completed action.


# Resend an email verification link without disclosing account existence.
@router.post("/email/resend", response_model=AuthMessage, status_code=status.HTTP_202_ACCEPTED)  # Expose verification email resend.
def resend_verification(payload: EmailActionRequest, db: Session = Depends(get_db)) -> AuthMessage:  # Find an unverified account and issue a fresh link.
    normalized_email = str(payload.email).strip().lower()  # Apply the registration email normalization rule.
    user = db.scalar(select(User).where(User.email == normalized_email, User.email_verified_at.is_(None)))  # Select only accounts that still need verification.
    if user is not None:  # Do work only for an existing unverified account.
        token = issue_action_token(user, "verify_email", timedelta(hours=24), db)  # Replace prior verification links with a fresh one.
        db.commit()  # Save the replacement token before asking Resend to deliver it.
        try:  # Attempt delivery while keeping the response neutral.
            send_account_action_email(user.email, "Vérifiez votre adresse email KitchAI", token, "verify-email", "Vérifier votre adresse email")  # Send the verification link.
        except EmailDeliveryError:  # Handle provider failure without revealing whether the address is registered.
            logger.exception("Échec du renvoi de l'email de vérification.")  # Keep only the technical error in server logs.
    return AuthMessage(message="Si un compte non vérifié correspond à cette adresse, un lien vient d'être envoyé.")  # Use the same response for known and unknown addresses.


# Start password recovery without revealing whether an account exists.
@router.post("/password/forgot", response_model=AuthMessage, status_code=status.HTTP_202_ACCEPTED)  # Expose the forgot-password request.
def forgot_password(payload: EmailActionRequest, db: Session = Depends(get_db)) -> AuthMessage:  # Issue a short-lived recovery link when the account exists.
    normalized_email = str(payload.email).strip().lower()  # Apply the same email normalization used at registration.
    user = db.scalar(select(User).where(User.email == normalized_email))  # Find the account without exposing the result in the response.
    if user is not None:  # Create a recovery link only for a known account.
        token = issue_action_token(user, "reset_password", timedelta(hours=1), db)  # Set a short one-hour lifetime for password reset links.
        db.commit()  # Persist the token before trying to send the email.
        try:  # Ask Resend to deliver the reset link.
            send_account_action_email(user.email, "Réinitialisez votre mot de passe KitchAI", token, "reset-password", "Réinitialiser votre mot de passe")  # Send the one-time recovery link.
        except EmailDeliveryError:  # Keep the response indistinguishable if delivery fails.
            logger.exception("Échec de l'envoi de l'email de réinitialisation.")  # Record the provider error without recording the link token.
    return AuthMessage(message="Si un compte correspond à cette adresse, un lien de réinitialisation vient d'être envoyé.")  # Use one response for existing and unknown addresses.


# Set a new password using a valid one-time reset link.
@router.post("/password/reset", response_model=AuthMessage)  # Expose completion of password recovery.
def reset_password(payload: PasswordResetRequest, db: Session = Depends(get_db)) -> AuthMessage:  # Consume the token and replace the account password.
    action_token = find_valid_action_token(payload.token, "reset_password", db)  # Find and lock an active password-reset token.
    if action_token is None:  # Reject invalid, expired, reused, or verification-only tokens.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lien de réinitialisation invalide ou expiré.")  # Ask the user to request a fresh reset link.
    now = datetime.now(timezone.utc)  # Reuse one timestamp for token consumption and session revocation.
    action_token.consumed_at = now  # Make the reset link single-use.
    action_token.user.password_hash = hash_password(payload.new_password)  # Replace the stored password with a secure hash.
    db.execute(update(UserSession).where(UserSession.user_id == action_token.user_id, UserSession.revoked_at.is_(None)).values(revoked_at=now))  # Sign out existing browsers after the password changes.
    db.commit()  # Save the new password, token consumption, and revocations together.
    return AuthMessage(message="Mot de passe modifié. Connectez-vous avec votre nouveau mot de passe.")  # Ask the user to authenticate again.

# Require an administrator account for catalogue and moderation actions.
def get_current_admin(user: User = Depends(get_current_user)) -> User:  # Protect administrative API routes.
    if not user.is_admin:  # Reject regular users before they can change shared data.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès administrateur requis.")  # Explain the role requirement.
    return user  # Return the authenticated administrator.

# Resolve a browser session when present while allowing anonymous public reads.
def get_optional_current_user(kitchai_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME), db: Session = Depends(get_db)) -> User | None:  # Support catalogue routes for visitors and signed-in users.
    if not kitchai_session:  # Treat a missing cookie as an anonymous visitor.
        return None  # Do not require accounts for public catalogue reads.
    token_hash = hash_session_token(kitchai_session)  # Hash the cookie before searching stored sessions.
    session = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash, UserSession.revoked_at.is_(None), UserSession.expires_at > datetime.now(timezone.utc)))  # Find only a currently valid session.
    return session.user if session is not None else None  # Ignore missing or expired cookies as anonymous access.
