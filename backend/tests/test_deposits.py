from datetime import date, timedelta

def test_submit_deposit_success(client, institution_token, test_institution):
    today = date.today()
    payload = {
        "fdr_number": "FDR-HDFC-2026-TEST1",
        "amount": 2500000.0,
        "bank_name": "HDFC Bank",
        "branch_name": "Powai Mumbai",
        "ifsc_code": "HDFC0000123",
        "issue_date": str(today),
        "maturity_date": str(today + timedelta(days=365 * 3))
    }
    response = client.post(
        "/api/deposits",
        json=payload,
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["fdr_number"] == "FDR-HDFC-2026-TEST1"
    assert data["status"] == "PENDING_VERIFICATION"
    assert data["amount"] == 2500000.0
    assert data["institution_id"] == test_institution.id

def test_submit_deposit_invalid_dates(client, institution_token):
    today = date.today()
    # Maturity date before issue date
    payload = {
        "fdr_number": "FDR-FAIL-DATES",
        "amount": 1000000.0,
        "bank_name": "Axis Bank",
        "issue_date": str(today),
        "maturity_date": str(today - timedelta(days=30))
    }
    response = client.post(
        "/api/deposits",
        json=payload,
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert response.status_code == 422  # Pydantic validation error

def test_submit_deposit_negative_amount(client, institution_token):
    today = date.today()
    payload = {
        "fdr_number": "FDR-FAIL-AMOUNT",
        "amount": -5000.0,
        "bank_name": "Axis Bank",
        "issue_date": str(today),
        "maturity_date": str(today + timedelta(days=365))
    }
    response = client.post(
        "/api/deposits",
        json=payload,
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert response.status_code == 422

def test_officer_cannot_submit_deposit(client, officer_token):
    today = date.today()
    payload = {
        "fdr_number": "FDR-OFFICER-SUBMIT",
        "amount": 1000000.0,
        "bank_name": "State Bank of India",
        "issue_date": str(today),
        "maturity_date": str(today + timedelta(days=365))
    }
    response = client.post(
        "/api/deposits",
        json=payload,
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert response.status_code == 403

def test_officer_verify_deposit(client, institution_token, officer_token):
    today = date.today()
    # 1. Institution creates deposit
    create_res = client.post(
        "/api/deposits",
        json={
            "fdr_number": "FDR-VERIFY-FLOW",
            "amount": 1500000.0,
            "bank_name": "Canara Bank",
            "issue_date": str(today),
            "maturity_date": str(today + timedelta(days=730))
        },
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert create_res.status_code == 201
    deposit_id = create_res.json()["id"]

    # 2. Officer verifies deposit
    verify_res = client.patch(
        f"/api/deposits/{deposit_id}/status",
        json={
            "status": "VERIFIED",
            "verification_remarks": "Original receipt and bank certificate verified in order."
        },
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert verify_res.status_code == 200
    data = verify_res.json()
    assert data["status"] == "VERIFIED"
    assert data["verified_by_id"] is not None
    assert "Original receipt" in data["verification_remarks"]

def test_institution_cannot_verify_own_deposit(client, institution_token):
    today = date.today()
    create_res = client.post(
        "/api/deposits",
        json={
            "fdr_number": "FDR-SELF-APPROVE",
            "amount": 1200000.0,
            "bank_name": "Bank of India",
            "issue_date": str(today),
            "maturity_date": str(today + timedelta(days=365))
        },
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    deposit_id = create_res.json()["id"]

    # Institution tries to verify own deposit -> 403 Forbidden
    verify_res = client.patch(
        f"/api/deposits/{deposit_id}/status",
        json={"status": "VERIFIED"},
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert verify_res.status_code == 403
