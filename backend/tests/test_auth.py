def test_register_institution_user(client, test_institution):
    payload = {
        "email": "new_director@college.edu",
        "full_name": "Dr. Director New",
        "password": "SecurePassword123",
        "role": "INSTITUTION",
        "institution_id": test_institution.id
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "new_director@college.edu"
    assert data["role"] == "INSTITUTION"
    assert "hashed_password" not in data

def test_register_duplicate_email(client, test_admin_user, test_institution):
    payload = {
        "email": test_admin_user.email,
        "full_name": "Impostor Admin",
        "password": "Password123",
        "role": "INSTITUTION",
        "institution_id": test_institution.id
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]

def test_login_success(client, test_admin_user):
    response = client.post("/api/auth/login", json={
        "email": "test_admin@aicte.gov.in",
        "password": "AdminPass123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["role"] == "ADMIN"

def test_login_invalid_password(client, test_admin_user):
    response = client.post("/api/auth/login", json={
        "email": "test_admin@aicte.gov.in",
        "password": "WrongPassword!"
    })
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]

def test_get_current_user_me(client, admin_token):
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test_admin@aicte.gov.in"
    assert data["role"] == "ADMIN"


def test_anonymous_cannot_self_register_privileged_roles(client):
    for role in ("ADMIN", "OFFICER"):
        r = client.post("/api/auth/register", json={
            "email": f"sneaky_{role.lower()}@example.com", "full_name": "Sneaky User",
            "password": "Password123", "role": role,
        })
        assert r.status_code == 403, r.text


def test_admin_can_create_officer(client, admin_token):
    r = client.post("/api/auth/register", json={
        "email": "new_officer@aicte.gov.in", "full_name": "New Officer",
        "password": "Password123", "role": "OFFICER",
    }, headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "OFFICER"


def test_institution_registration_requires_real_institution(client):
    r = client.post("/api/auth/register", json={
        "email": "orphan@college.edu", "full_name": "Orphan User",
        "password": "Password123", "role": "INSTITUTION",
    })
    assert r.status_code == 400
    r = client.post("/api/auth/register", json={
        "email": "orphan2@college.edu", "full_name": "Orphan User",
        "password": "Password123", "role": "INSTITUTION", "institution_id": 99999,
    })
    assert r.status_code == 400


def test_weak_password_rejected(client, test_institution):
    for pw in ("short1", "allletters", "12345678"):
        r = client.post("/api/auth/register", json={
            "email": "weak@college.edu", "full_name": "Weak Pass",
            "password": pw, "role": "INSTITUTION", "institution_id": test_institution.id,
        })
        assert r.status_code == 422, pw


def test_login_locks_after_repeated_failures(client, test_admin_user):
    from backend.app.config import settings
    for _ in range(settings.LOGIN_MAX_FAILED_ATTEMPTS):
        r = client.post("/api/auth/login", json={"email": test_admin_user.email, "password": "WrongPass123"})
        assert r.status_code == 401
    # Even the correct password is refused while locked.
    r = client.post("/api/auth/login", json={"email": test_admin_user.email, "password": "AdminPass123"})
    assert r.status_code == 429
