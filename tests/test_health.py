def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "SUVANÉ Research RAG"
    assert payload["version"] == "0.2.0"
    assert payload["status"] == "ok"
