def test_list_all_evidence(client):
    response = client.get("/api/evidence")

    assert response.status_code == 200
    records = response.json()
    assert len(records) == 2
    assert {record["id"] for record in records} == {
        "fixture-companion-ai-001",
        "fixture-exercise-002",
    }


def test_filter_by_strength(client):
    response = client.get("/api/evidence", params={"strength": "moderate"})

    assert response.status_code == 200
    records = response.json()
    assert len(records) == 1
    assert records[0]["id"] == "fixture-companion-ai-001"


def test_filter_by_query(client):
    response = client.get("/api/evidence", params={"q": "walking"})

    assert response.status_code == 200
    records = response.json()
    assert len(records) == 1
    assert records[0]["id"] == "fixture-exercise-002"


def test_filter_by_query_and_strength(client):
    response = client.get(
        "/api/evidence",
        params={"q": "companion", "strength": "moderate"},
    )

    assert response.status_code == 200
    records = response.json()
    assert len(records) == 1
    assert records[0]["id"] == "fixture-companion-ai-001"
