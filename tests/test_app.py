"""
Basic integration tests for the coffee shop app.
Run with: pytest tests/
"""
import json
import pytest

from app import create_app, db


@pytest.fixture
def client(tmp_path):
    app = create_app()
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{tmp_path}/test.db",
        WTF_CSRF_ENABLED=False,
    )
    with app.app_context():
        db.drop_all()
        db.create_all()
        from app.seed import seed_if_empty
        seed_if_empty()
    with app.test_client() as client:
        yield client


def login(client, role, username, password):
    return client.post("/login", data={"role": role, "username": username, "password": password}, follow_redirects=True)


def test_manager_login_success(client):
    r = login(client, "manager", "Manager#1", "password123")
    assert r.status_code == 200
    assert b"Sales Dashboard" in r.data or b"Today" in r.data


def test_manager_login_wrong_password(client):
    r = login(client, "manager", "Manager#1", "wrong")
    assert b"Invalid username or password" in r.data


def test_staff_login_success(client):
    r = login(client, "staff", "staff1", "staffpass123")
    assert r.status_code == 200


def test_staff_cannot_access_manager_pages(client):
    login(client, "staff", "staff1", "staffpass123")
    r = client.get("/manager/dashboard")
    assert r.status_code == 403


def test_menu_api_returns_categories(client):
    login(client, "staff", "staff1", "staffpass123")
    r = client.get("/staff/api/menu")
    data = r.get_json()
    assert "locations" in data
    assert len(data["hot_drinks"]) > 0
    assert len(data["fillings"]) > 0


def test_create_drink_order_with_options(client):
    login(client, "staff", "staff1", "staffpass123")
    menu = client.get("/staff/api/menu").get_json()
    americano = next(d for d in menu["hot_drinks"] if d["name"] == "Americano")
    own_cup = next(o for o in menu["drink_options"] if o["name"] == "Own Cup")

    payload = {
        "location_id": menu["locations"][0]["id"],
        "table_number": 1,
        "allergy_status": False,
        "allergens": [],
        "payment_method": "Card",
        "payment_confirmed": True,
        "items": [{"type": "drink", "menu_item_id": americano["id"], "option_ids": [own_cup["id"]], "quantity": 1}],
    }
    r = client.post("/staff/api/orders", data=json.dumps(payload), content_type="application/json")
    data = r.get_json()
    assert r.status_code == 200
    assert data["total"] == americano["price"] + own_cup["price"]  # 2.60 - 0.25 = 2.35


def test_table_number_validation(client):
    login(client, "staff", "staff1", "staffpass123")
    menu = client.get("/staff/api/menu").get_json()
    payload = {
        "location_id": menu["locations"][0]["id"],
        "table_number": 99,
        "payment_method": "Card",
        "payment_confirmed": True,
        "items": [{"type": "drink", "menu_item_id": menu["hot_drinks"][0]["id"], "option_ids": [], "quantity": 1}],
    }
    r = client.post("/staff/api/orders", data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 400


def test_cash_payment_change_calculation(client):
    login(client, "staff", "staff1", "staffpass123")
    menu = client.get("/staff/api/menu").get_json()
    americano = next(d for d in menu["hot_drinks"] if d["name"] == "Americano")
    payload = {
        "location_id": menu["locations"][0]["id"],
        "table_number": 2,
        "payment_method": "Cash",
        "amount_received": 5.00,
        "items": [{"type": "drink", "menu_item_id": americano["id"], "option_ids": [], "quantity": 1}],
    }
    r = client.post("/staff/api/orders", data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 200


def test_cash_insufficient_amount_rejected(client):
    login(client, "staff", "staff1", "staffpass123")
    menu = client.get("/staff/api/menu").get_json()
    americano = next(d for d in menu["hot_drinks"] if d["name"] == "Americano")
    payload = {
        "location_id": menu["locations"][0]["id"],
        "table_number": 3,
        "payment_method": "Cash",
        "amount_received": 0.50,
        "items": [{"type": "drink", "menu_item_id": americano["id"], "option_ids": [], "quantity": 1}],
    }
    r = client.post("/staff/api/orders", data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 400


def test_sandwich_price_calculation(client):
    login(client, "staff", "staff1", "staffpass123")
    menu = client.get("/staff/api/menu").get_json()
    filling = next(f for f in menu["fillings"] if f["name"] == "Tuna")
    bread = next(b for b in menu["bread"] if b["name"] == "White Baguette")
    extra = next(e for e in menu["extras"] if e["name"] == "Cheese")
    payload = {
        "location_id": menu["locations"][0]["id"],
        "table_number": 4,
        "payment_method": "Card",
        "payment_confirmed": True,
        "items": [{"type": "sandwich", "filling_id": filling["id"], "bread_id": bread["id"], "extra_ids": [extra["id"]], "quantity": 1}],
    }
    r = client.post("/staff/api/orders", data=json.dumps(payload), content_type="application/json")
    data = r.get_json()
    assert round(data["total"], 2) == round(filling["price"] + bread["price"] + extra["price"], 2)


def test_order_status_update(client):
    login(client, "staff", "staff1", "staffpass123")
    menu = client.get("/staff/api/menu").get_json()
    payload = {
        "location_id": menu["locations"][0]["id"],
        "table_number": 6,
        "payment_method": "Card",
        "payment_confirmed": True,
        "items": [{"type": "drink", "menu_item_id": menu["hot_drinks"][0]["id"], "option_ids": [], "quantity": 1}],
    }
    r = client.post("/staff/api/orders", data=json.dumps(payload), content_type="application/json")
    order_id = r.get_json()["order_id"]
    r2 = client.post(f"/staff/orders/{order_id}/status", data={"status": "Delivered"})
    assert r2.get_json()["status"] == "Delivered"


def test_manager_can_search_members(client):
    login(client, "manager", "Manager#1", "password123")
    r = client.get("/manager/members?q=1001")
    assert r.status_code == 200
    assert b"1001" in r.data


def test_manager_menu_management(client):
    login(client, "manager", "Manager#1", "password123")
    r = client.get("/manager/menu")
    assert r.status_code == 200


def test_manager_location_management(client):
    login(client, "manager", "Manager#1", "password123")
    r = client.post("/manager/locations/add", data={"name": "Rooftop"}, follow_redirects=True)
    assert r.status_code == 200
    assert b"Rooftop" in r.data
