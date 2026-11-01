from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models.user import User, UserRole
from backend.app.models.institution import Institution
from backend.app.schemas.user import UserCreate, UserLogin, UserResponse, Token
from backend.app.auth.security import get_password_hash, verify_password, create_access_token
from backend.app.auth.dependencies import get_current_user, get_optional_user
from backend.app.config import settings
from backend.app.services.audit_service import record_audit_log
from backend.app.utils.clock import utc_now

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    acting_user: Optional[User] = Depends(get_optional_user),
):
    """
    Registers a new portal user.

    - INSTITUTION users may self-register but must name an existing institution
      (institution_id or aicte_id). They are never attached to an institution
      implicitly.
    - ADMIN and OFFICER accounts can only be created by a signed-in ADMIN
      (or when ALLOW_PRIVILEGED_SELF_REGISTRATION is explicitly enabled for a
      throw-away demo). This stops anyone from making themselves an administrator.
    """
    if user_in.role != UserRole.INSTITUTION:
        is_admin = acting_user is not None and acting_user.role == UserRole.ADMIN
        if not (is_admin or settings.ALLOW_PRIVILEGED_SELF_REGISTRATION):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only an administrator can create ADMIN or OFFICER accounts."
            )

    email = user_in.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists."
        )

    institution_id = None
    if user_in.role == UserRole.INSTITUTION:
        inst = None
        if user_in.institution_id:
            inst = db.query(Institution).filter(Institution.id == user_in.institution_id).first()
        elif user_in.aicte_id:
            inst = db.query(Institution).filter(Institution.aicte_id == user_in.aicte_id.strip()).first()
        if inst is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Institution users must register with a valid institution ID or AICTE ID."
            )
        institution_id = inst.id

    new_user = User(
        email=email,
        full_name=user_in.full_name.strip(),
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role,
        institution_id=institution_id,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    record_audit_log(
        db, action="USER_REGISTERED", actor_id=acting_user.id if acting_user else new_user.id,
        entity_type="USER", entity_id=new_user.id, institution_id=institution_id,
        after={"email": new_user.email, "role": new_user.role.value},
    )
    return new_user

# A real bcrypt hash of a random value, verified when the email is unknown so that
# response time does not reveal whether an account exists.
_DUMMY_HASH = get_password_hash("not-a-real-password-1")

@router.post("/login", response_model=Token)
def login(
    login_data: UserLogin,
    db: Session = Depends(get_db)
):
    """
    Authenticates a user and returns a signed JWT access token.
    Repeated failures lock the account temporarily.
    """
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )
    now = utc_now()
    user = db.query(User).filter(User.email == login_data.email.lower()).first()

    if user is None:
        verify_password(login_data.password, _DUMMY_HASH)
        raise invalid

    if user.locked_until and user.locked_until > now:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed sign-in attempts. Please try again later."
        )

    if not verify_password(login_data.password, user.hashed_password):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        locked = user.failed_login_attempts >= settings.LOGIN_MAX_FAILED_ATTEMPTS
        if locked:
            user.locked_until = now + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
            user.failed_login_attempts = 0
        db.commit()
        record_audit_log(
            db, action="LOGIN_LOCKED" if locked else "LOGIN_FAILED", actor_id=user.id,
            entity_type="USER", entity_id=user.id, institution_id=user.institution_id,
        )
        raise invalid

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact AICTE Administrator."
        )

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    db.commit()

    access_token = create_access_token(data={
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value,
        "name": user.full_name,
        "institution_id": user.institution_id,
    })
    return {"access_token": access_token, "token_type": "bearer", "user": user}

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Returns the authenticated user's profile and active session info."""
    return current_user
