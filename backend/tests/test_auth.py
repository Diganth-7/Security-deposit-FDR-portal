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

def test_register_duplicate_email(client, test_admin_user):
    payload = {
        "email": test_admin_user.email,
        "full_name": "Impostor Admin",
        "password": "Password123",
        "role": "ADMIN"
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
