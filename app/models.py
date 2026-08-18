import json
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app import db

ALLERGEN_OPTIONS = [
    "Celery", "Dairy/Milk", "Eggs", "Fish", "Gluten", "Lupin", "Mustard",
    "Nuts", "Peanuts", "Sesame", "Shellfish", "Soya", "Sulphites", "Wheat",
]

MENU_CATEGORIES = [
    "Hot Drinks", "Drinks", "Fillings", "Sandwiches", "Sandwich Extras", "Bread",
]

ORDER_STATUSES = ["Pending", "Preparing", "Confirmed", "Delivered", "Cancelled"]
PAYMENT_METHODS = ["Card", "Cash", "Member Card"]


class User(db.Model, UserMixin):
    """Staff and manager login accounts."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'manager' or 'staff'
    name = db.Column(db.String(120), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship("Order", backref="staff", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        # Namespaced id so Flask-Login can distinguish User vs Member sessions
        return f"user:{self.id}"

    @property
    def is_manager(self):
        return self.role == "manager"


class Member(db.Model, UserMixin):
    """Loyalty / member accounts. Created only by managers."""
    __tablename__ = "members"

    id = db.Column(db.Integer, primary_key=True)
    member_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(64), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)
    active = db.Column(db.Boolean, default=True, nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship("Order", backref="member", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return f"member:{self.id}"


class Location(db.Model):
    __tablename__ = "locations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)

    orders = db.relationship("Order", backref="location", lazy=True)


class MenuItem(db.Model):
    __tablename__ = "menu_items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(40), nullable=False)  # one of MENU_CATEGORIES
    price = db.Column(db.Numeric(6, 2), nullable=False, default=0)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DrinkOption(db.Model):
    """Milk types, chocolate, extra hot, own cup, etc. Applied to drinks."""
    __tablename__ = "drink_options"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    price_adjustment = db.Column(db.Numeric(6, 2), nullable=False, default=0)
    active = db.Column(db.Boolean, default=True, nullable=False)


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    staff_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey("members.id"), nullable=True)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=False)
    table_number = db.Column(db.Integer, nullable=False)

    allergy_status = db.Column(db.Boolean, default=False, nullable=False)
    allergens_text = db.Column(db.String(255), default="", nullable=False)

    payment_method = db.Column(db.String(20), nullable=True)
    payment_status = db.Column(db.String(20), default="Pending", nullable=False)
    order_status = db.Column(db.String(20), default="Pending", nullable=False)

    total = db.Column(db.Numeric(8, 2), nullable=False, default=0)
    amount_received = db.Column(db.Numeric(8, 2), nullable=True)
    change_due = db.Column(db.Numeric(8, 2), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = db.relationship("OrderItem", backref="order", lazy=True, cascade="all, delete-orphan")

    def allergen_list(self):
        return [a for a in self.allergens_text.split(",") if a] if self.allergens_text else []


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey("menu_items.id"), nullable=True)
    item_name = db.Column(db.String(120), nullable=False)
    item_type = db.Column(db.String(20), nullable=False, default="drink")  # drink | sandwich
    base_price = db.Column(db.Numeric(6, 2), nullable=False, default=0)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    total_price = db.Column(db.Numeric(8, 2), nullable=False, default=0)
    options = db.Column(db.Text, nullable=True)  # JSON list of {"name": ..., "price": ...}

    def options_list(self):
        if not self.options:
            return []
        try:
            return json.loads(self.options)
        except (ValueError, TypeError):
            return []
