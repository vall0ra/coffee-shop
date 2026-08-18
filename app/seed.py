from datetime import datetime, timedelta
import json
import random

from app import db
from app.models import (
    User, Member, Location, MenuItem, DrinkOption, Order, OrderItem
)

HOT_DRINKS = [
    ("Americano", 2.60), ("Cappuccino", 3.10), ("Latte", 3.10),
    ("Hot Chocolate", 3.30), ("Mocha", 3.40), ("Iced Latte", 3.40),
]

FILLINGS = [
    ("Beef Pastrami", 4.60), ("Brie and Bacon", 4.30), ("Cheese and Pickle", 3.50),
    ("Coronation Chicken", 4.10), ("Egg", 3.20), ("Grilled Chicken", 4.20),
    ("Ham and Cheese", 3.90), ("Prawn Marie", 4.80), ("Smoked Salmon", 4.90),
    ("Tuna", 3.80),
]

BREAD = [
    ("Brown", 0.00), ("Brown Baguette", 0.60), ("White", 0.00),
    ("White Baguette", 0.60), ("Wrap", 0.30),
]

SANDWICH_EXTRAS = [
    ("As on the menu", 0.00), ("Butter", 0.00), ("Cheese", 0.60),
    ("Chilli Jam", 0.40), ("Cucumber", 0.30), ("Lettuce", 0.20),
    ("Mango Chutney", 0.40), ("No Butter", 0.00), ("No Sauce", 0.00),
    ("Rocket", 0.30), ("Tomato", 0.30),
]

DRINK_OPTIONS = [
    ("Milk", 0.00), ("Oat Milk", 0.50), ("Skimmed Milk", 0.00),
    ("Soya Milk", 0.50), ("Coconut Milk", 0.50), ("Chocolate", 0.40),
    ("Extra Hot", 0.00), ("Own Cup", -0.25),
]

LOCATIONS = ["Garden Room", "Terrace Main", "Terrace Side"]


def seed_if_empty():
    if Location.query.first():
        return  # already seeded

    for name in LOCATIONS:
        db.session.add(Location(name=name, active=True))

    for name, price in HOT_DRINKS:
        db.session.add(MenuItem(name=name, category="Hot Drinks", price=price, active=True))
    for name, price in FILLINGS:
        db.session.add(MenuItem(name=name, category="Fillings", price=price, active=True))
    for name, price in BREAD:
        db.session.add(MenuItem(name=name, category="Bread", price=price, active=True))
    for name, price in SANDWICH_EXTRAS:
        db.session.add(MenuItem(name=name, category="Sandwich Extras", price=price, active=True))
    for name, price in DRINK_OPTIONS:
        db.session.add(DrinkOption(name=name, price_adjustment=price, active=True))

    manager = User(username="Manager#1", role="manager", name="Store Manager", active=True)
    manager.set_password("password123")
    db.session.add(manager)

    staff = User(username="staff1", role="staff", name="Alex Staff", active=True)
    staff.set_password("staffpass123")
    db.session.add(staff)

    member = Member(member_number="#1001", name="Demo Member", username="demo.member", active=True)
    member.set_password("memberpass123")
    db.session.add(member)

    db.session.commit()

    _seed_demo_orders(manager=None, staff=staff, member=member)


def _seed_demo_orders(manager, staff, member):
    """Create a handful of historical orders so dashboards show real numbers."""
    locations = Location.query.all()
    americano = MenuItem.query.filter_by(name="Americano").first()
    cappuccino = MenuItem.query.filter_by(name="Cappuccino").first()
    latte = MenuItem.query.filter_by(name="Latte").first()
    salmon = MenuItem.query.filter_by(name="Smoked Salmon").first()
    ham = MenuItem.query.filter_by(name="Ham and Cheese").first()
    mocha = MenuItem.query.filter_by(name="Mocha").first()

    demo_orders = [
        (americano, "drink", 1, [], "Card", "Confirmed", locations[0], 14, False),
        (cappuccino, "drink", 1, [{"name": "Oat Milk", "price": 0.5}], "Cash", "Delivered", locations[1], 5, False),
        (latte, "drink", 1, [], "Member Card", "Delivered", locations[1], 8, True),
        (salmon, "sandwich", 1, [{"name": "Brown", "price": 0.0}], "Card", "Delivered", locations[0], 2, True),
        (ham, "sandwich", 1, [{"name": "White", "price": 0.0}], "Cash", "Preparing", locations[2], 19, False),
        (mocha, "drink", 1, [{"name": "Chocolate", "price": 0.4}], "Card", "Cancelled", locations[2], 27, False),
    ]

    for idx, (item, item_type, qty, options, payment, status, location, table, allergy) in enumerate(demo_orders, start=1):
        opt_total = sum(o["price"] for o in options)
        unit_price = float(item.price) + opt_total
        total = round(unit_price * qty, 2)

        order = Order(
            order_number=f"#{10000 + idx}",
            staff_id=staff.id,
            member_id=member.id if idx % 3 == 0 else None,
            location_id=location.id,
            table_number=table,
            allergy_status=allergy,
            allergens_text="Dairy/Milk" if allergy else "",
            payment_method=payment,
            payment_status="Paid" if status != "Cancelled" else "Cancelled",
            order_status=status,
            total=total,
            amount_received=total if payment == "Cash" else None,
            change_due=0 if payment == "Cash" else None,
            created_at=datetime.utcnow() - timedelta(hours=idx * 3),
        )
        db.session.add(order)
        db.session.flush()

        db.session.add(OrderItem(
            order_id=order.id,
            menu_item_id=item.id,
            item_name=item.name,
            item_type=item_type,
            base_price=item.price,
            quantity=qty,
            total_price=total,
            options=json.dumps(options),
        ))

    db.session.commit()
