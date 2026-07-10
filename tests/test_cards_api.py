def test_create_card(client):
    response = client.post("/cards", json={"status": "pending", "matched_name": "Lightning Bolt"})
    assert response.status_code == 201
    data = response.json()
    assert data["matched_name"] == "Lightning Bolt"
    assert data["status"] == "pending"
    assert "id" in data


def test_create_card_invalid_status_rejected_before_db(client):
    response = client.post("/cards", json={"status": "bogus"})
    assert response.status_code == 422


def test_list_cards_empty(client):
    response = client.get("/cards")
    assert response.status_code == 200
    assert response.json() == []


def test_get_card_not_found(client):
    response = client.get("/cards/999")
    assert response.status_code == 404


def test_full_card_lifecycle(client):
    create_resp = client.post("/cards", json={"status": "enriched", "matched_name": "Black Lotus"})
    card_id = create_resp.json()["id"]

    list_resp = client.get("/cards")
    assert len(list_resp.json()) == 1

    get_resp = client.get(f"/cards/{card_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["matched_name"] == "Black Lotus"

    delete_resp = client.delete(f"/cards/{card_id}")
    assert delete_resp.status_code == 204

    get_after_delete = client.get(f"/cards/{card_id}")
    assert get_after_delete.status_code == 404


def test_delete_missing_card_returns_404(client):
    response = client.delete("/cards/999")
    assert response.status_code == 404
