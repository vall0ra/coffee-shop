from datetime import datetime, timedelta, time
from decimal import Decimal

from sqlalchemy import func

from app import db
from app.models import Order, OrderItem, Location


def day_bounds(d):
    start = datetime.combine(d, time.min)
    end = datetime.combine(d, time.max)
    return start, end


def resolve_range(period, start_str=None, end_str=None):
    """Return (start_datetime, end_datetime, label) for a named or custom period."""
    today = datetime.utcnow().date()

    if period == "today":
        s, e = day_bounds(today)
        return s, e, "Today"
    if period == "yesterday":
        y = today - timedelta(days=1)
        s, e = day_bounds(y)
        return s, e, "Yesterday"
    if period == "this_week":
        monday = today - timedelta(days=today.weekday())
        s, _ = day_bounds(monday)
        _, e = day_bounds(today)
        return s, e, "This Week"
    if period == "last_week":
        this_monday = today - timedelta(days=today.weekday())
        last_monday = this_monday - timedelta(days=7)
        last_sunday = this_monday - timedelta(days=1)
        s, _ = day_bounds(last_monday)
        _, e = day_bounds(last_sunday)
        return s, e, "Last Week"
    if period == "this_month":
        first = today.replace(day=1)
        s, _ = day_bounds(first)
        _, e = day_bounds(today)
        return s, e, "This Month"
    if period == "last_month":
        first_this = today.replace(day=1)
        last_month_end = first_this - timedelta(days=1)
        first_last = last_month_end.replace(day=1)
        s, _ = day_bounds(first_last)
        _, e = day_bounds(last_month_end)
        return s, e, "Last Month"
    if period == "custom" and start_str and end_str:
        try:
            sd = datetime.strptime(start_str, "%Y-%m-%d").date()
            ed = datetime.strptime(end_str, "%Y-%m-%d").date()
        except ValueError:
            sd = ed = today
        s, _ = day_bounds(sd)
        _, e = day_bounds(ed)
        return s, e, f"{sd.strftime('%d %b %Y')} - {ed.strftime('%d %b %Y')}"

    # default: today
    s, e = day_bounds(today)
    return s, e, "Today"


def sales_summary(start, end, exclude_cancelled=True):
    q = Order.query.filter(Order.created_at >= start, Order.created_at <= end)
    if exclude_cancelled:
        q = q.filter(Order.order_status != "Cancelled")
    orders = q.all()

    total_sales = sum((o.total for o in orders), Decimal("0.00"))
    order_count = len(orders)
    avg_order = (total_sales / order_count) if order_count else Decimal("0.00")

    items_sold = sum((sum(i.quantity for i in o.items) for o in orders), 0)

    payment_totals = {}
    for o in orders:
        key = o.payment_method or "Unknown"
        payment_totals[key] = payment_totals.get(key, Decimal("0.00")) + o.total

    location_totals = {}
    for o in orders:
        loc_name = o.location.name if o.location else "Unknown"
        entry = location_totals.setdefault(loc_name, {"orders": 0, "total": Decimal("0.00")})
        entry["orders"] += 1
        entry["total"] += o.total

    product_totals = {}
    for o in orders:
        for item in o.items:
            entry = product_totals.setdefault(item.item_name, {"qty": 0, "revenue": Decimal("0.00")})
            entry["qty"] += item.quantity
            entry["revenue"] += item.total_price

    return {
        "orders": orders,
        "total_sales": total_sales,
        "order_count": order_count,
        "avg_order": avg_order,
        "items_sold": items_sold,
        "payment_totals": payment_totals,
        "location_totals": location_totals,
        "product_totals": product_totals,
    }
