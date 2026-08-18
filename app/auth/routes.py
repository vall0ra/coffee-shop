from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user

from app.models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
def index():
    if current_user.is_authenticated:
        if isinstance(current_user, User) and current_user.is_manager:
            return redirect(url_for("manager.dashboard"))
        return redirect(url_for("staff.dashboard"))
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if isinstance(current_user, User) and current_user.is_manager:
            return redirect(url_for("manager.dashboard"))
        return redirect(url_for("staff.dashboard"))

    role = request.args.get("role", "staff")
    if role not in ("staff", "manager"):
        role = "staff"

    if request.method == "POST":
        role = request.form.get("role", "staff")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please enter both a username and password.", "error")
            return render_template("auth/login.html", role=role, username=username)

        user = User.query.filter_by(username=username).first()

        if not user or not user.check_password(password):
            flash("Invalid username or password.", "error")
            return render_template("auth/login.html", role=role, username=username)

        if not user.active:
            flash("This account has been disabled. Contact your manager.", "error")
            return render_template("auth/login.html", role=role, username=username)

        if role == "manager" and user.role != "manager":
            flash("That account does not have manager access.", "error")
            return render_template("auth/login.html", role=role, username=username)

        if role == "staff" and user.role != "staff":
            flash("Please use the Manager login tab for this account.", "error")
            return render_template("auth/login.html", role=role, username=username)

        login_user(user)
        flash(f"Welcome back, {user.name.split(' ')[0]}!", "success")

        if user.is_manager:
            return redirect(url_for("manager.dashboard"))
        return redirect(url_for("staff.dashboard"))

    return render_template("auth/login.html", role=role, username="")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
