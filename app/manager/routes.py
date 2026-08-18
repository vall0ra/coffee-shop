import csv
import io
from datetime import datetime, timedelta, time
from decimal import Decimal

from flask import (
    Blueprint, render_template, request, jsonify, redirect, url_for, flash, abort, Response, send_file
)
from flask_login import login_required, current_user

from app import db
from app.models import (
    Order, OrderItem, Location, MenuItem, DrinkOption, User, Member, MENU_CATEGORIES
)
from app.utils import role_required
from app.sales_utils import resolve_range, sales_summary, day_bounds

manager_bp = Blueprint("manager", __name__, url_prefix="/manager")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@manager_bp.route("/dashboard")
@login_required
@role_required("manager")
def dashboard():
    today = datetime.utcnow().date()
    s, e = day_bounds(today)
    summary = sales_summary(s, e)

    card_total = summary["payment_totals"].get("Card", Decimal("0.00")) + summary["payment_totals"].get("Card (Simulated)", Decimal("0.00"))
    member_total = summary["payment_totals"].get("Member Card", Decimal("0.00"))

    products_sorted = sorted(summary["product_totals"].items(), key=lambda kv: kv[1]["qty"], reverse=True)[:8]
    locations_sorted = sorted(summary["location_totals"].items(), key=lambda kv: kv[1]["total"], reverse=True)

    return render_template(
        "manager/dashboard.html",
        summary=summary,
        card_total=card_total,
        member_total=member_total,
        products=products_sorted,
        locations=locations_sorted,
    )


# ---------------------------------------------------------------------------
# Sales History
# ---------------------------------------------------------------------------

@manager_bp.route("/sales-history")
@login_required
@role_required("manager")
def sales_history():
    period = request.args.get("period", "today")
    start_str = request.args.get("start")
    end_str = request.args.get("end")

    s, e, label = resolve_range(period, start_str, end_str)
    summary = sales_summary(s, e)

    products_sorted = sorted(summary["product_totals"].items(), key=lambda kv: kv[1]["revenue"], reverse=True)
    locations_sorted = sorted(summary["location_totals"].items(), key=lambda kv: kv[1]["total"], reverse=True)

    return render_template(
        "manager/sales_history.html",
        summary=summary,
        products=products_sorted,
        locations=locations_sorted,
        period=period,
        label=label,
        start_str=start_str or "",
        end_str=end_str or "",
    )


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@manager_bp.route("/reports")
@login_required
@role_required("manager")
def reports():
    order_query = request.args.get("q", "").strip()
    start_str = request.args.get("start")
    end_str = request.args.get("end")

    found_order = None
    if order_query:
        found_order = Order.query.filter(
            db.or_(Order.order_number.ilike(f"%{order_query}%"))
        ).first()

    summary = None
    label = None
    if start_str and end_str:
        s, e, label = resolve_range("custom", start_str, end_str)
        summary = sales_summary(s, e)
        products_sorted = sorted(summary["product_totals"].items(), key=lambda kv: kv[1]["revenue"], reverse=True)
        locations_sorted = sorted(summary["location_totals"].items(), key=lambda kv: kv[1]["total"], reverse=True)
    else:
        products_sorted = []
        locations_sorted = []

    return render_template(
        "manager/reports.html",
        order_query=order_query,
        found_order=found_order,
        summary=summary,
        products=products_sorted,
        locations=locations_sorted,
        label=label,
        start_str=start_str or "",
        end_str=end_str or "",
    )


@manager_bp.route("/reports/export.csv")
@login_required
@role_required("manager")
def export_csv():
    start_str = request.args.get("start")
    end_str = request.args.get("end")
    if not (start_str and end_str):
        flash("Choose a date range before exporting.", "error")
        return redirect(url_for("manager.reports"))

    s, e, label = resolve_range("custom", start_str, end_str)
    summary = sales_summary(s, e)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Sales Report", label])
    writer.writerow([])
    writer.writerow(["Total Revenue", f"{summary['total_sales']:.2f}"])
    writer.writerow(["Total Orders", summary["order_count"]])
    writer.writerow(["Average Order Value", f"{summary['avg_order']:.2f}"])
    writer.writerow([])
    writer.writerow(["Order #", "Member", "Date/Time", "Location", "Table", "Payment", "Status", "Total"])
    for o in summary["orders"]:
        writer.writerow([
            o.order_number,
            o.member.member_number if o.member else "",
            o.created_at.strftime("%Y-%m-%d %H:%M"),
            o.location.name,
            o.table_number,
            o.payment_method,
            o.order_status,
            f"{o.total:.2f}",
        ])

    output = buf.getvalue().encode("utf-8")
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=sales-report-{s.date()}-to-{e.date()}.csv"},
    )


@manager_bp.route("/reports/export.xlsx")
@login_required
@role_required("manager")
def export_xlsx():
    from openpyxl import Workbook

    start_str = request.args.get("start")
    end_str = request.args.get("end")
    if not (start_str and end_str):
        flash("Choose a date range before exporting.", "error")
        return redirect(url_for("manager.reports"))

    s, e, label = resolve_range("custom", start_str, end_str)
    summary = sales_summary(s, e)

    wb = Workbook()
    ws = wb.active
    ws.title = "Sales Report"
    ws.append(["Sales Report", label])
    ws.append([])
    ws.append(["Total Revenue", float(summary["total_sales"])])
    ws.append(["Total Orders", summary["order_count"]])
    ws.append(["Average Order Value", float(summary["avg_order"])])
    ws.append([])
    ws.append(["Order #", "Member", "Date/Time", "Location", "Table", "Payment", "Status", "Total"])
    for o in summary["orders"]:
        ws.append([
            o.order_number,
            o.member.member_number if o.member else "",
            o.created_at.strftime("%Y-%m-%d %H:%M"),
            o.location.name,
            o.table_number,
            o.payment_method,
            o.order_status,
            float(o.total),
        ])

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return send_file(
        stream,
        as_attachment=True,
        download_name=f"sales-report-{s.date()}-to-{e.date()}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ---------------------------------------------------------------------------
# Orders management
# ---------------------------------------------------------------------------

@manager_bp.route("/orders")
@login_required
@role_required("manager")
def orders():
    status_filter = request.args.get("status", "All")
    q = request.args.get("q", "").strip()

    query = Order.query
    if status_filter == "Pending":
        query = query.filter(Order.order_status.in_(["Pending", "Preparing", "Confirmed"]))
    elif status_filter == "Completed":
        query = query.filter(Order.order_status == "Delivered")
    elif status_filter == "Cancelled":
        query = query.filter(Order.order_status == "Cancelled")

    if q:
        query = query.join(Member, isouter=True).filter(
            db.or_(Order.order_number.ilike(f"%{q}%"), Member.member_number.ilike(f"%{q}%"))
        )

    order_list = query.order_by(Order.created_at.desc()).limit(200).all()
    return render_template("manager/orders.html", orders=order_list, status_filter=status_filter, q=q)


@manager_bp.route("/orders/<int:order_id>")
@login_required
@role_required("manager")
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template("manager/order_detail.html", order=order)


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------

@manager_bp.route("/members")
@login_required
@role_required("manager")
def members():
    q = request.args.get("q", "").strip()
    query = Member.query
    if q:
        query = query.filter(db.or_(Member.member_number.ilike(f"%{q}%"), Member.name.ilike(f"%{q}%")))
    member_list = query.order_by(Member.joined_at.desc()).all()
    return render_template("manager/members.html", members=member_list, q=q)


@manager_bp.route("/members/create", methods=["POST"])
@login_required
@role_required("manager")
def member_create():
    member_number = request.form.get("member_number", "").strip()
    name = request.form.get("name", "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    confirm = request.form.get("confirm_password", "")

    if not all([member_number, name, username, password]):
        flash("All fields are required to create a member.", "error")
        return redirect(url_for("manager.members"))
    if password != confirm:
        flash("Passwords do not match.", "error")
        return redirect(url_for("manager.members"))
    if Member.query.filter_by(member_number=member_number).first():
        flash("That member number is already in use.", "error")
        return redirect(url_for("manager.members"))
    if Member.query.filter_by(username=username).first():
        flash("That username is already in use.", "error")
        return redirect(url_for("manager.members"))

    member = Member(member_number=member_number, name=name, username=username, active=True)
    member.set_password(password)
    db.session.add(member)
    db.session.commit()
    flash(f"Member {member_number} created.", "success")
    return redirect(url_for("manager.members"))


@manager_bp.route("/members/<int:member_id>/orders")
@login_required
@role_required("manager")
def member_orders(member_id):
    member = Member.query.get_or_404(member_id)
    order_list = Order.query.filter_by(member_id=member.id).order_by(Order.created_at.desc()).all()
    return render_template("manager/member_orders.html", member=member, orders=order_list)


@manager_bp.route("/members/<int:member_id>/toggle", methods=["POST"])
@login_required
@role_required("manager")
def member_toggle(member_id):
    member = Member.query.get_or_404(member_id)
    member.active = not member.active
    db.session.commit()
    return jsonify({"ok": True, "active": member.active})


@manager_bp.route("/members/<int:member_id>/reset-password", methods=["POST"])
@login_required
@role_required("manager")
def member_reset_password(member_id):
    member = Member.query.get_or_404(member_id)
    new_password = request.form.get("password", "")
    if not new_password or len(new_password) < 6:
        flash("New password must be at least 6 characters.", "error")
        return redirect(url_for("manager.members"))
    member.set_password(new_password)
    db.session.commit()
    flash(f"Password reset for {member.member_number}.", "success")
    return redirect(url_for("manager.members"))


# ---------------------------------------------------------------------------
# Menu Management
# ---------------------------------------------------------------------------

@manager_bp.route("/menu")
@login_required
@role_required("manager")
def menu():
    items_by_category = {
        cat: MenuItem.query.filter_by(category=cat).order_by(MenuItem.name).all() for cat in MENU_CATEGORIES
    }
    drink_options = DrinkOption.query.order_by(DrinkOption.name).all()
    return render_template(
        "manager/menu.html", items_by_category=items_by_category, categories=MENU_CATEGORIES, drink_options=drink_options
    )


@manager_bp.route("/menu/add", methods=["POST"])
@login_required
@role_required("manager")
def menu_add():
    category = request.form.get("category")
    name = request.form.get("name", "").strip()
    price = request.form.get("price", "0")

    if category not in MENU_CATEGORIES or not name:
        flash("Please provide a category and name.", "error")
        return redirect(url_for("manager.menu"))
    try:
        price = Decimal(price)
    except Exception:
        flash("Please enter a valid price.", "error")
        return redirect(url_for("manager.menu"))

    db.session.add(MenuItem(name=name, category=category, price=price, active=True))
    db.session.commit()
    flash(f"Added {name} to {category}.", "success")
    return redirect(url_for("manager.menu"))


@manager_bp.route("/menu/<int:item_id>/update", methods=["POST"])
@login_required
@role_required("manager")
def menu_update(item_id):
    item = MenuItem.query.get_or_404(item_id)
    name = request.form.get("name", "").strip()
    price = request.form.get("price")
    if name:
        item.name = name
    if price is not None:
        try:
            item.price = Decimal(price)
        except Exception:
            pass
    db.session.commit()
    return jsonify({"ok": True})


@manager_bp.route("/menu/<int:item_id>/toggle", methods=["POST"])
@login_required
@role_required("manager")
def menu_toggle(item_id):
    item = MenuItem.query.get_or_404(item_id)
    item.active = not item.active
    db.session.commit()
    return jsonify({"ok": True, "active": item.active})


@manager_bp.route("/menu/<int:item_id>/delete", methods=["POST"])
@login_required
@role_required("manager")
def menu_delete(item_id):
    item = MenuItem.query.get_or_404(item_id)
    used = OrderItem.query.filter_by(menu_item_id=item.id).first()
    if used:
        # Preserve historical order accuracy — soft delete instead
        item.active = False
        db.session.commit()
        return jsonify({"ok": True, "soft_deleted": True})
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True, "soft_deleted": False})


@manager_bp.route("/menu/drink-options/add", methods=["POST"])
@login_required
@role_required("manager")
def drink_option_add():
    name = request.form.get("name", "").strip()
    price = request.form.get("price", "0")
    if not name:
        flash("Please provide an option name.", "error")
        return redirect(url_for("manager.menu"))
    try:
        price = Decimal(price)
    except Exception:
        flash("Please enter a valid price adjustment.", "error")
        return redirect(url_for("manager.menu"))
    db.session.add(DrinkOption(name=name, price_adjustment=price, active=True))
    db.session.commit()
    flash(f"Added drink option {name}.", "success")
    return redirect(url_for("manager.menu"))


@manager_bp.route("/menu/drink-options/<int:option_id>/toggle", methods=["POST"])
@login_required
@role_required("manager")
def drink_option_toggle(option_id):
    option = DrinkOption.query.get_or_404(option_id)
    option.active = not option.active
    db.session.commit()
    return jsonify({"ok": True, "active": option.active})


@manager_bp.route("/menu/drink-options/<int:option_id>/delete", methods=["POST"])
@login_required
@role_required("manager")
def drink_option_delete(option_id):
    option = DrinkOption.query.get_or_404(option_id)
    db.session.delete(option)
    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

@manager_bp.route("/locations")
@login_required
@role_required("manager")
def locations():
    location_list = Location.query.order_by(Location.name).all()
    return render_template("manager/locations.html", locations=location_list)


@manager_bp.route("/locations/add", methods=["POST"])
@login_required
@role_required("manager")
def location_add():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Please enter a location name.", "error")
        return redirect(url_for("manager.locations"))
    if Location.query.filter_by(name=name).first():
        flash("A location with that name already exists.", "error")
        return redirect(url_for("manager.locations"))
    db.session.add(Location(name=name, active=True))
    db.session.commit()
    flash(f"Added location {name}.", "success")
    return redirect(url_for("manager.locations"))


@manager_bp.route("/locations/<int:location_id>/toggle", methods=["POST"])
@login_required
@role_required("manager")
def location_toggle(location_id):
    location = Location.query.get_or_404(location_id)
    location.active = not location.active
    db.session.commit()
    return jsonify({"ok": True, "active": location.active})
