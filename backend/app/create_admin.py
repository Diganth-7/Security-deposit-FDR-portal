"""
Create a real administrator account (use this instead of demo data in a real deployment).

    python -m backend.app.create_admin --email you@example.org --name "Your Name"

The password is read from the ADMIN_PASSWORD environment variable, or prompted for
(hidden). It is never taken from the command line or stored anywhere but as a bcrypt hash.
"""
import argparse
import getpass
import os
import sys

from backend.app.auth.security import get_password_hash
from backend.app.database import SessionLocal
from backend.app.migrations import run_migrations
from backend.app.database import engine
from backend.app.models.user import User, UserRole
from backend.app.schemas.user import UserCreate
from backend.app.services.audit_service import record_audit_log


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", choices=["ADMIN", "OFFICER"], default="ADMIN")
    args = parser.parse_args(argv)

    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password: ")
    try:
        validated = UserCreate(email=args.email, full_name=args.name, password=password, role=UserRole(args.role))
    except Exception as exc:  # pydantic validation error: show the reasons, never the password
        print("Invalid input:", "; ".join(e["msg"] for e in getattr(exc, "errors", lambda: [{"msg": str(exc)}])()), file=sys.stderr)
        return 2

    run_migrations(engine)
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == validated.email.lower()).first():
            print("A user with that email already exists.", file=sys.stderr)
            return 1
        user = User(email=validated.email.lower(), full_name=validated.full_name.strip(),
                    hashed_password=get_password_hash(validated.password), role=validated.role, is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        record_audit_log(db, action="USER_REGISTERED", actor_id=user.id, entity_type="USER", entity_id=user.id,
                         details="Created with the create_admin command.", after={"email": user.email, "role": user.role.value})
        print(f"Created {user.role.value} account {user.email}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
