import os  # Read account setup values from the local environment.
from datetime import datetime, timezone  # Mark demo accounts as verified for local testing.
from dotenv import load_dotenv  # Load the ignored local .env file.
from sqlalchemy import select  # Find existing accounts without creating duplicates.

from app.database import SessionLocal  # Open a database session for account setup.
from app.models import User  # Create or promote account records.
from app.security import hash_password  # Store only secure password hashes.


# Load local settings before checking for credentials.
load_dotenv()  # Read .env values into the process environment.
admin_email = os.getenv("ADMIN_EMAIL", "maxime.messaoui@gmail.com").strip().lower()  # Keep the initial admin identity fixed to the planned address.
admin_password = os.getenv("ADMIN_INITIAL_PASSWORD", "").strip()  # Use this only if the admin account needs to be created or lacks a password.
demo_email = os.getenv("DEMO_USER_EMAIL", "kitchai.demo@example.com").strip().lower()  # Give the test account a stable login address.
demo_password = os.getenv("DEMO_USER_PASSWORD", "").strip()  # Require a local test password instead of using a hard-coded default.
if len(demo_password) < 12:  # Apply the same minimum length as normal account creation.
    raise RuntimeError("DEMO_USER_PASSWORD must contain at least 12 characters.")  # Stop rather than create a weak account.
db = SessionLocal()  # Open the database connection used for this one-time setup.
try:  # Keep account changes within one transaction.
    now = datetime.now(timezone.utc)  # Reuse one explicit UTC timestamp for account verification.
    admin = db.scalar(select(User).where(User.email == admin_email))  # Find the already registered administrator account.
    if admin is None:  # Create the initial admin only if the planned address is not registered.
        if len(admin_password) < 12:  # Require an explicit password for a newly created admin.
            raise RuntimeError("Set ADMIN_INITIAL_PASSWORD before creating the initial admin account.")  # Prevent a predictable default credential.
        admin = User(email=admin_email, password_hash=hash_password(admin_password), first_name="Maxime", is_admin=True, email_verified_at=now)  # Create the initial verified admin with a password hash.
        db.add(admin)  # Stage the new admin account.
    else:  # Promote the existing user without replacing their current password.
        admin.is_admin = True  # Grant the administrator role to the configured email.
        if admin.password_hash is None:  # Add password login only when the existing account has no password.
            if len(admin_password) < 12:  # Require an explicit password before enabling password login.
                raise RuntimeError("Set ADMIN_INITIAL_PASSWORD because the existing admin account has no password.")  # Avoid creating an unusable admin.
            admin.password_hash = hash_password(admin_password)  # Hash the configured initial password.
        if admin.email_verified_at is None:  # Ensure the initial administrator can exercise admin-only workflows.
            admin.email_verified_at = now  # Mark the trusted configured admin address verified.
    demo = db.scalar(select(User).where(User.email == demo_email))  # Find the stable test account if it already exists.
    if demo is None:  # Create the test account once.
        demo = User(email=demo_email, first_name="Compte test", is_admin=False)  # Start with an ordinary non-admin account.
        db.add(demo)  # Stage the test account.
    demo.first_name = "Compte test"  # Keep the test profile label predictable.
    demo.is_admin = False  # Never allow the test account to inherit administrator privileges.
    demo.email_verified_at = demo.email_verified_at or now  # Allow local publishing and device-pairing workflows without outbound email.
    demo.password_hash = hash_password(demo_password)  # Synchronize the local login with the configured demo password.
    db.commit()  # Save the promoted admin and test account together.
    print(f"Admin prêt : {admin.email} (admin={admin.is_admin}, verified={admin.email_verified_at is not None})")  # Confirm setup without printing credentials.
    print(f"Compte test prêt : {demo.email} (admin={demo.is_admin}, verified={demo.email_verified_at is not None})")  # Confirm the test account is a normal verified user.
finally:  # Always release the database connection.
    db.close()  # Return the connection to the pool.
