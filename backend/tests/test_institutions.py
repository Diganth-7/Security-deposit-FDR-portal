def test_list_institutions(client, test_institution):
    response = client.get("/api/institutions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    names = [inst["name"] for inst in data]
    assert test_institution.name in names

def test_admin_create_institution(client, admin_token):
    payload = {
        "aicte_id": "1-9988776655",
        "name": "National Institute of Advanced Studies",
        "state": "Karnataka",
        "city": "Bengaluru",
        "address": "IISc Campus, Bengaluru",
        "institute_type": "Autonomous Research",
        "contact_email": "director@nias.res.in",
        "contact_phone": "+91-80-22185000"
    }
    response = client.post(
        "/api/institutions",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 201
    assert response.json()["aicte_id"] == "1-9988776655"

def test_officer_cannot_create_institution(client, officer_token):
    payload = {
        "aicte_id": "1-UNAUTH-INST",
        "name": "Unauthorized College",
        "state": "Goa",
        "city": "Panaji",
        "contact_email": "dean@unauth.edu"
    }
    response = client.post(
        "/api/institutions",
        json=payload,
        headers={"Authorization": f"Bearer {officer_token}"}
    )
    assert response.status_code == 403
