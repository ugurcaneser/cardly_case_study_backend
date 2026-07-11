def test_create_collection(client):
    response = client.post("/collections", json={"name": "Vintage"})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Vintage"
    assert data["card_count"] == 0


def test_create_collection_duplicate_name_rejected(client):
    client.post("/collections", json={"name": "Vintage"})
    response = client.post("/collections", json={"name": "Vintage"})
    assert response.status_code == 409


def test_collection_not_found(client):
    response = client.get("/collections/999")
    assert response.status_code == 404


def test_add_card_to_missing_collection(client):
    card_id = client.post("/cards", json={"status": "pending"}).json()["id"]
    response = client.post(f"/collections/999/cards/{card_id}")
    assert response.status_code == 404


def test_add_missing_card_to_collection(client):
    coll_id = client.post("/collections", json={"name": "Legacy"}).json()["id"]
    response = client.post(f"/collections/{coll_id}/cards/999")
    assert response.status_code == 404


def test_add_and_remove_card_from_collection(client):
    card_id = client.post("/cards", json={"status": "pending"}).json()["id"]
    coll_id = client.post("/collections", json={"name": "Modern"}).json()["id"]

    add_resp = client.post(f"/collections/{coll_id}/cards/{card_id}")
    assert add_resp.status_code == 201
    assert add_resp.json()["card_count"] == 1

    # adding the same card again is idempotent, not a duplicate row
    add_again = client.post(f"/collections/{coll_id}/cards/{card_id}")
    assert add_again.status_code == 201
    assert add_again.json()["card_count"] == 1

    list_resp = client.get("/collections")
    assert list_resp.json()[0]["card_count"] == 1

    remove_resp = client.delete(f"/collections/{coll_id}/cards/{card_id}")
    assert remove_resp.status_code == 200
    assert remove_resp.json()["card_count"] == 0

    remove_again = client.delete(f"/collections/{coll_id}/cards/{card_id}")
    assert remove_again.status_code == 404


def test_rename_collection(client):
    coll_id = client.post("/collections", json={"name": "Old Name"}).json()["id"]
    response = client.patch(f"/collections/{coll_id}", json={"name": "New Name"})
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


def test_rename_collection_to_existing_name_rejected(client):
    client.post("/collections", json={"name": "Taken"})
    coll_id = client.post("/collections", json={"name": "Other"}).json()["id"]
    response = client.patch(f"/collections/{coll_id}", json={"name": "Taken"})
    assert response.status_code == 409


def test_collections_are_scoped_per_device(client):
    client.post("/collections", json={"name": "Own Collection"})

    other_device_resp = client.get("/collections", headers={"X-Device-Id": "other-device"})
    assert other_device_resp.json() == []

    own_device_resp = client.get("/collections")
    assert len(own_device_resp.json()) == 1
    assert own_device_resp.json()[0]["name"] == "Own Collection"


def test_two_devices_can_each_have_a_collection_with_the_same_name(client):
    resp_a = client.post(
        "/collections", json={"name": "Vintage"}, headers={"X-Device-Id": "device-a"}
    )
    resp_b = client.post(
        "/collections", json={"name": "Vintage"}, headers={"X-Device-Id": "device-b"}
    )
    assert resp_a.status_code == 201
    assert resp_b.status_code == 201


def test_cannot_get_or_modify_another_devices_collection(client):
    coll_id = client.post(
        "/collections", json={"name": "Private"}, headers={"X-Device-Id": "device-a"}
    ).json()["id"]

    get_resp = client.get(f"/collections/{coll_id}", headers={"X-Device-Id": "device-b"})
    assert get_resp.status_code == 404

    rename_resp = client.patch(
        f"/collections/{coll_id}", json={"name": "Hijacked"}, headers={"X-Device-Id": "device-b"}
    )
    assert rename_resp.status_code == 404

    delete_resp = client.delete(f"/collections/{coll_id}", headers={"X-Device-Id": "device-b"})
    assert delete_resp.status_code == 404


def test_cannot_add_another_devices_card_to_your_collection(client):
    coll_id = client.post(
        "/collections", json={"name": "Mine"}, headers={"X-Device-Id": "device-a"}
    ).json()["id"]
    other_card_id = client.post(
        "/cards", json={"status": "pending"}, headers={"X-Device-Id": "device-b"}
    ).json()["id"]

    response = client.post(
        f"/collections/{coll_id}/cards/{other_card_id}", headers={"X-Device-Id": "device-a"}
    )
    assert response.status_code == 404


def test_delete_collection_cascades_membership_but_keeps_card(client, session):
    from sqlmodel import select

    from app.db.models import CollectionCard

    card_id = client.post("/cards", json={"status": "pending"}).json()["id"]
    coll_id = client.post("/collections", json={"name": "Standard"}).json()["id"]
    client.post(f"/collections/{coll_id}/cards/{card_id}")
    assert session.exec(select(CollectionCard)).all() != []

    delete_resp = client.delete(f"/collections/{coll_id}")
    assert delete_resp.status_code == 204

    # the membership row must actually be gone (not just silently orphaned by
    # a no-op delete), and the card itself must survive the collection delete
    assert session.exec(select(CollectionCard)).all() == []
    card_get = client.get(f"/cards/{card_id}")
    assert card_get.status_code == 200
