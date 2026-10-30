from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User, UserRole
from app.models.institution import Institution
from app.schemas.user import UserCreate, UserLogin, UserResponse, Token
from app.auth.security import get_password_hash, verify_password, create_access_token
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_in: UserCreate,
    db: Session = Depends(get_db)
):
    """
    Registers a new portal user.
    - Roles: ADMIN, INSTITUTION, OFFICER
    - For INSTITUTION role, can link to an existing institution via institution_id or aicte_id.
    """
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_in.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists."
        )

    institution_id = user_in.institution_id

    # If an aicte_id is provided, resolve institution
    if user_in.aicte_id and not institution_id:
        inst = db.query(Institution).filter(Institution.aicte_id == user_in.aicte_id.strip()).first()
        if inst:
            institution_id = inst.id

    # Enforce that institution users should belong to an institution if available
    if user_in.role == UserRole.INSTITUTION and not institution_id:
        # Check if there is an institution with matching domain/name or auto-assign first available
        first_inst = db.query(Institution).first()
        if first_inst:
            institution_id = first_inst.id

    new_user = User(
        email=user_in.email.lower(),
        full_name=user_in.full_name.strip(),
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role,
        institution_id=institution_id,
        is_active=True
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/login", response_model=Token)
def login(
    login_data: UserLogin,
    db: Session = Depends(get_db)
):
    """
    Authenticates a user and returns a signed JWT access token.
    """
    user = db.query(User).filter(User.email == login_data.email.lower()).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact AICTE Administrator."
        )

    # JWT payload: sub=user.id, role=user.role.value, email=user.email
    token_claims = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value,
        "name": user.full_name,
        "institution_id": user.institution_id
    }
    
    access_token = create_access_token(data=token_claims)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Returns the authenticated user's profile and active session info."""
    return current_user
