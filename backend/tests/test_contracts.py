import pytest
from datetime import date, timedelta
from backend.app.models.contract import Contract, ContractStatus
from backend.app.models.deposit import Deposit, DepositStatus

def test_contract_creation(client, institution_token, test_institution):
    """Test valid contract creation by institution."""
    today = date.today()
    payload = {
        "contract_number": "AICTE-CON-2026-001",
        "title": "B.Tech Computer Science Affiliation Agreement",
        "description": "Statutory institutional affiliation for academic year 2026-2030",
        "contract_type": "Institutional Affiliation",
        "contract_amount": 5000000.0,
        "required_deposit_amount": 1500000.0,
        "start_date": str(today),
        "end_date": str(today + timedelta(days=365 * 4)),
        "status": "ACTIVE"
    }
    response = client.post(
        "/api/contracts",
        json=payload,
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["contract_number"] == "AICTE-CON-2026-001"
    assert data["institution_id"] == test_institution.id
    assert data["required_deposit_amount"] == 1500000.0
    assert data["total_deposited_amount"] == 0.0
    assert data["is_deposit_sufficient"] is False
    assert data["deposit_shortfall"] == 1500000.0

def test_contract_retrieval(client, institution_token, db_session, test_institution):
    """Test contract retrieval and listing."""
    today = date.today()
    contract = Contract(
        contract_number="AICTE-CON-2026-RETRIEVE",
        title="Infrastructure Lease Agreement",
        institution_id=test_institution.id,
        contract_type="Infrastructure Lease",
        contract_amount=3000000.0,
        required_deposit_amount=500000.0,
        start_date=today,
        end_date=today + timedelta(days=730),
        status=ContractStatus.ACTIVE
    )
    db_session.add(contract)
    db_session.commit()

    # Get single
    res = client.get(
        f"/api/contracts/{contract.id}",
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["contract_number"] == "AICTE-CON-2026-RETRIEVE"
    assert data["required_deposit_amount"] == 500000.0

    # List contracts
    res_list = client.get(
        "/api/contracts",
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert res_list.status_code == 200
    assert any(c["contract_number"] == "AICTE-CON-2026-RETRIEVE" for c in res_list.json())

def test_contract_updates(client, institution_token, db_session, test_institution):
    """Test updating contract details."""
    today = date.today()
    contract = Contract(
        contract_number="AICTE-CON-2026-UPDATE",
        title="Original Title",
        institution_id=test_institution.id,
        contract_type="Vendor Services",
        contract_amount=1000000.0,
        required_deposit_amount=200000.0,
        start_date=today,
        end_date=today + timedelta(days=365),
        status=ContractStatus.DRAFT
    )
    db_session.add(contract)
    db_session.commit()

    update_payload = {
        "title": "Updated Statutory Title",
        "required_deposit_amount": 250000.0,
        "status": "ACTIVE"
    }
    res = client.put(
        f"/api/contracts/{contract.id}",
        json=update_payload,
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Updated Statutory Title"
    assert data["required_deposit_amount"] == 250000.0
    assert data["status"] == "ACTIVE"

def test_institution_access_restrictions(client, institution_token, second_institution_token, db_session, second_institution):
    """Test that institutions can only view and edit their own contracts."""
    today = date.today()
    contract = Contract(
        contract_number="AICTE-CON-SECOND-COLLEGE",
        title="Second College Private Agreement",
        institution_id=second_institution.id,
        contract_type="PPP Joint Venture",
        contract_amount=4000000.0,
        required_deposit_amount=1000000.0,
        start_date=today,
        end_date=today + timedelta(days=365),
        status=ContractStatus.ACTIVE
    )
    db_session.add(contract)
    db_session.commit()

    # Institution 1 attempts to view Institution 2's contract -> 403 Forbidden
    res_view = client.get(
        f"/api/contracts/{contract.id}",
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert res_view.status_code == 403

    # Institution 1 attempts to modify Institution 2's contract -> 403 Forbidden
    res_edit = client.put(
        f"/api/contracts/{contract.id}",
        json={"title": "Hacked Title"},
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert res_edit.status_code == 403

def test_invalid_contract_dates(client, institution_token):
    """Test validation fails when end_date <= start_date."""
    today = date.today()
    payload = {
        "contract_number": "AICTE-CON-FAIL-DATES",
        "title": "Invalid Dates Contract",
        "start_date": str(today),
        "end_date": str(today - timedelta(days=10)),  # Past end date
        "contract_amount": 1000000.0,
        "required_deposit_amount": 100000.0
    }
    res = client.post(
        "/api/contracts",
        json=payload,
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert res.status_code == 422

def test_linking_fdr_to_contract(client, institution_token, db_session, test_institution, test_institution_user):
    """Test linking an FDR deposit to a contract."""
    today = date.today()
    contract = Contract(
        contract_number="AICTE-CON-LINK-TEST",
        title="Affiliation for Mechanical Dept",
        institution_id=test_institution.id,
        contract_type="Department Affiliation",
        contract_amount=2500000.0,
        required_deposit_amount=1000000.0,
        start_date=today,
        end_date=today + timedelta(days=730),
        status=ContractStatus.ACTIVE
    )
    dep = Deposit(
        fdr_number="FDR-LINK-001",
        amount=1000000.0,
        bank_name="State Bank of India",
        issue_date=today,
        maturity_date=today + timedelta(days=730),
        status=DepositStatus.ACTIVE,
        institution_id=test_institution.id,
        submitted_by_id=test_institution_user.id
    )
    db_session.add_all([contract, dep])
    db_session.commit()

    # Link FDR to contract
    link_res = client.post(
        f"/api/contracts/{contract.id}/deposits/{dep.id}",
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert link_res.status_code == 200
    data = link_res.json()
    assert data["total_deposited_amount"] == 1000000.0
    assert data["is_deposit_sufficient"] is True
    assert data["deposit_shortfall"] == 0.0
    assert data["linked_deposits_count"] == 1

    # Verify GET /contracts/{id}/deposits returns the linked FDR
    dep_list_res = client.get(
        f"/api/contracts/{contract.id}/deposits",
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert dep_list_res.status_code == 200
    assert any(d["fdr_number"] == "FDR-LINK-001" for d in dep_list_res.json())

def test_cross_institution_linking_forbidden(client, institution_token, db_session, test_institution, second_institution, second_institution_user):
    """Test that linking an FDR of college B to a contract of college A is strictly prohibited."""
    today = date.today()
    contract_a = Contract(
        contract_number="AICTE-CON-COLLEGE-A",
        title="College A Contract",
        institution_id=test_institution.id,
        start_date=today,
        end_date=today + timedelta(days=365)
    )
    dep_b = Deposit(
        fdr_number="FDR-COLLEGE-B-CROSS",
        amount=500000.0,
        bank_name="Canara Bank",
        issue_date=today,
        maturity_date=today + timedelta(days=365),
        status=DepositStatus.ACTIVE,
        institution_id=second_institution.id,  # Belongs to second institution!
        submitted_by_id=second_institution_user.id
    )
    db_session.add_all([contract_a, dep_b])
    db_session.commit()

    # Attempt cross-linking -> 400 Bad Request
    res = client.post(
        f"/api/contracts/{contract_a.id}/deposits/{dep_b.id}",
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert res.status_code == 400
    assert "Mismatched institutions" in res.json()["detail"]

def test_insufficient_security_deposit_detection(client, institution_token, db_session, test_institution, test_institution_user):
    """Test insufficient security deposit calculation and shortfall identification."""
    today = date.today()
    contract = Contract(
        contract_number="AICTE-CON-SHORTFALL",
        title="High Value Research Project",
        institution_id=test_institution.id,
        contract_amount=10000000.0,
        required_deposit_amount=2000000.0,  # Requires 20 Lakhs
        start_date=today,
        end_date=today + timedelta(days=1095),
        status=ContractStatus.ACTIVE
    )
    dep1 = Deposit(
        fdr_number="FDR-PARTIAL-1",
        amount=1200000.0,  # 12 Lakhs (Shortfall: 8 Lakhs)
        bank_name="HDFC Bank",
        issue_date=today,
        maturity_date=today + timedelta(days=1095),
        status=DepositStatus.ACTIVE,
        institution_id=test_institution.id,
        submitted_by_id=test_institution_user.id
    )
    dep2 = Deposit(
        fdr_number="FDR-PARTIAL-2",
        amount=800000.0,  # 8 Lakhs (Completes requirement)
        bank_name="Axis Bank",
        issue_date=today,
        maturity_date=today + timedelta(days=1095),
        status=DepositStatus.ACTIVE,
        institution_id=test_institution.id,
        submitted_by_id=test_institution_user.id
    )
    db_session.add_all([contract, dep1, dep2])
    db_session.commit()

    # Link first FDR
    client.post(
        f"/api/contracts/{contract.id}/deposits/{dep1.id}",
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    # Check shortfall
    res1 = client.get(
        f"/api/contracts/{contract.id}",
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    c1 = res1.json()
    assert c1["total_deposited_amount"] == 1200000.0
    assert c1["is_deposit_sufficient"] is False
    assert c1["deposit_shortfall"] == 800000.0

    # Link second FDR
    client.post(
        f"/api/contracts/{contract.id}/deposits/{dep2.id}",
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    res2 = client.get(
        f"/api/contracts/{contract.id}",
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    c2 = res2.json()
    assert c2["total_deposited_amount"] == 2000000.0
    assert c2["is_deposit_sufficient"] is True
    assert c2["deposit_shortfall"] == 0.0

def test_prevent_deleting_contract_with_linked_deposits(client, institution_token, db_session, test_institution, test_institution_user):
    """Test that contracts with linked financial records cannot be deleted."""
    today = date.today()
    contract = Contract(
        contract_number="AICTE-CON-NODELETE",
        title="Protected Financial Contract",
        institution_id=test_institution.id,
        start_date=today,
        end_date=today + timedelta(days=365)
    )
    dep = Deposit(
        fdr_number="FDR-PROTECTED",
        amount=500000.0,
        bank_name="ICICI Bank",
        issue_date=today,
        maturity_date=today + timedelta(days=365),
        status=DepositStatus.ACTIVE,
        institution_id=test_institution.id,
        submitted_by_id=test_institution_user.id
    )
    db_session.add_all([contract, dep])
    db_session.commit()

    # Link deposit
    client.post(
        f"/api/contracts/{contract.id}/deposits/{dep.id}",
        headers={"Authorization": f"Bearer {institution_token}"}
    )

    # Attempt deletion -> 400 Bad Request
    del_res = client.delete(
        f"/api/contracts/{contract.id}",
        headers={"Authorization": f"Bearer {institution_token}"}
    )
    assert del_res.status_code == 400
    assert "Cannot delete contract with linked financial FDR records" in del_res.json()["detail"]
