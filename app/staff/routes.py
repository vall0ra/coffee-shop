import json
from decimal import Decimal

from flask import Blueprint, render_template, jsonify, request, abort
from flask_login import login_required, current_user

from app import db
from app.models import (
    Location, MenuItem, DrinkOption, Order, OrderItem, Member,
    ALLERGEN_OPTIONS, ORDER_STATUSES,
)
from app.utils import role_required, next_order_number

staff_bp = Blueprint("staff", __name__, url_prefix="/staff")

ONGOING_STATUSES = ["Pending", "Preparing", "Confirmed"]


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@staff_bp.route("/dashboard")
@login_required
@role_required("staff", "manager")
def dashboard():
    tab = request.args.get("tab", "ongoing")

    query = Order.query.filter_by(staff_id=current_user.id)
    if tab == "delivered":
        orders = query.filter_by(order_status="Delivered").order_by(Order.updated_at.desc()).all()
    elif tab == "cancelled":
        orders = query.filter_by(order_status="Cancelled").order_by(Order.updated_at.desc()).all()
    else:
        tab = "ongoing"
        orders = query.filter(Order.order_status.in_(ONGOING_STATUSES)).order_by(Order.created_at.desc()).all()

    return render_template("staff/dashboard.html", orders=orders, tab=tab)


@staff_bp.route("/orders/new")
@login_required
@role_required("staff", "manager")
def new_order():
    return render_template("staff/new_order.html")


@staff_bp.route("/orders/<int:order_id>")
@login_required
@role_required("staff", "manager")
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template("staff/order_detail.html", order=order)


@staff_bp.route("/orders/<int:order_id>/status", methods=["POST"])
@login_required
@role_required("staff", "manager")
def update_status(order_id):
    order = Order.query.get_or_404(order_id)
    status = request.form.get("status")
    if status not in ORDER_STATUSES:
        abort(400)
    order.order_status = status
    if status == "Cancelled":
        order.payment_status = "Cancelled"
    db.session.commit()
    return jsonify({"ok": True, "status": order.order_status})


# ---------------------------------------------------------------------------
# JSON API used by the order wizard (order.js)
# ---------------------------------------------------------------------------

def _decimal_to_float(value):
    return float(value) if isinstance(value, Decimal) else value


@staff_bp.route("/api/menu")
@login_required
@role_required("staff", "manager")
def api_menu():
    locations = [
        {"id": l.id, "name": l.name}
        for l in Location.query.filter_by(active=True).order_by(Location.name).all()
    ]

    def items_for(category):
        rows = MenuItem.query.filter_by(category=category, active=True).order_by(MenuItem.name).all()
        return [{"id": i.id, "name": i.name, "price": _decimal_to_float(i.price)} for i in rows]

    drink_options = [
        {"id": o.id, "name": o.name, "price": _decimal_to_float(o.price_adjustment)}
        for o in DrinkOption.query.filter_by(active=True).order_by(DrinkOption.id).all()
    ]

    return jsonify({
        "locations": locations,
        "hot_drinks": items_for("Hot Drinks"),
        "drinks": items_for("Drinks"),
        "fillings": items_for("Fillings"),
        "bread": items_for("Bread"),
        "extras": items_for("Sandwich Extras"),
        "drink_options": drink_options,
        "allergens": ALLERGEN_OPTIONS,
    })


@staff_bp.route("/api/members/search")
@login_required
@role_required("staff", "manager")
def api_members_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": []})
    rows = Member.query.filter(
        Member.active == True,  # noqa: E712
        db.or_(Member.member_number.ilike(f"%{q}%"), Member.name.ilike(f"%{q}%")),
    ).limit(10).all()
    return jsonify({"results": [{"id": m.id, "member_number": m.member_number, "name": m.name} for m in rows]})


@staff_bp.route("/api/orders", methods=["POST"])
@login_required
@role_required("staff", "manager")
def api_create_order():
    data = request.get_json(force=True, silent=True) or {}

    location = Location.query.get(data.get("location_id"))
    if not location or not location.active:
        return jsonify({"error": "Please choose a valid location."}), 400

    try:
        table_number = int(data.get("table_number"))
    except (TypeError, ValueError):
        return jsonify({"error": "Please choose a table number."}), 400
    if table_number < 1 or table_number > 30:
        return jsonify({"error": "Table number must be between 1 and 30."}), 400

    raw_items = data.get("items") or []
    if not raw_items:
        return jsonify({"error": "Add at least one item before placing the order."}), 400

    allergy_status = bool(data.get("allergy_status"))
    allergens = data.get("allergens") or []
    allergens = [a for a in allergens if a in ALLERGEN_OPTIONS]
    if not allergy_status:
        allergens = []

    member = None
    if data.get("member_id"):
        member = Member.query.get(data.get("member_id"))

    payment_method = data.get("payment_method")
    if payment_method not in ("Card", "Cash", "Member Card"):
        return jsonify({"error": "Please choose a payment method."}), 400

    order_items = []
    total = Decimal("0.00")

    for raw in raw_items:
        item_type = raw.get("type")
        quantity = max(1, int(raw.get("quantity", 1)))

        if item_type == "drink":
            menu_item = MenuItem.query.get(raw.get("menu_item_id"))
            if not menu_item or not menu_item.active or menu_item.category not in ("Hot Drinks", "Drinks"):
                return jsonify({"error": "One of the drinks selected is no longer available."}), 400

            option_ids = raw.get("option_ids") or []
            options = DrinkOption.query.filter(DrinkOption.id.in_(option_ids), DrinkOption.active == True).all()  # noqa: E712
            option_payload = [{"name": o.name, "price": _decimal_to_float(o.price_adjustment)} for o in options]

            unit_price = menu_item.price + sum((o.price_adjustment for o in options), Decimal("0.00"))
            line_total = unit_price * quantity

            order_items.append(OrderItem(
                menu_item_id=menu_item.id,
                item_name=menu_item.name,
                item_type="drink",
                base_price=menu_item.price,
                quantity=quantity,
                total_price=line_total,
                options=json.dumps(option_payload),
            ))
            total += line_total

        elif item_type == "sandwich":
            filling = MenuItem.query.get(raw.get("filling_id"))
            bread = MenuItem.query.get(raw.get("bread_id"))
            if not filling or not bread or filling.category != "Fillings" or bread.category != "Bread":
                return jsonify({"error": "Please choose a filling and bread for the sandwich."}), 400

            extra_ids = raw.get("extra_ids") or []
            extras = MenuItem.query.filter(
                MenuItem.id.in_(extra_ids), MenuItem.category == "Sandwich Extras", MenuItem.active == True  # noqa: E712
            ).all()

            option_payload = [{"name": bread.name, "price": _decimal_to_float(bread.price)}]
            option_payload += [{"name": e.name, "price": _decimal_to_float(e.price)} for e in extras]

            unit_price = filling.price + bread.price + sum((e.price for e in extras), Decimal("0.00"))
            line_total = unit_price * quantity

            order_items.append(OrderItem(
                menu_item_id=filling.id,
                item_name=f"{filling.name} Sandwich",
                item_type="sandwich",
                base_price=filling.price,
                quantity=quantity,
                total_price=line_total,
                options=json.dumps(option_payload),
            ))
            total += line_total
        else:
            return jsonify({"error": "Unrecognised item type."}), 400

    amount_received = None
    change_due = None
    payment_status = "Pending"

    if payment_method == "Cash":
        try:
            amount_received = Decimal(str(data.get("amount_received", "0")))
        except Exception:
            return jsonify({"error": "Enter a valid cash amount."}), 400
        if amount_received < total:
            return jsonify({"error": "Amount received is less than the order total."}), 400
        change_due = amount_received - total
        payment_status = "Paid"
    else:
        # Card / Member Card — demo mode uses a clearly labelled simulated payment
        if not data.get("payment_confirmed"):
            return jsonify({"error": "Please confirm the card payment before placing the order."}), 400
        payment_status = "Paid (Simulated)"

    order = Order(
        order_number=next_order_number(),
        staff_id=current_user.id,
        member_id=member.id if member else None,
        location_id=location.id,
        table_number=table_number,
        allergy_status=allergy_status,
        allergens_text=",".join(allergens),
        payment_method=payment_method,
        payment_status=payment_status,
        order_status="Pending",
        total=total,
        amount_received=amount_received,
        change_due=change_due,
    )
    order.items = order_items
    db.session.add(order)
    db.session.commit()

    return jsonify({"ok": True, "order_id": order.id, "order_number": order.order_number, "total": _decimal_to_float(total)})
