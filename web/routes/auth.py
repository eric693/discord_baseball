import hashlib
from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from database import db

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if "admin_id" in session:
        return redirect(url_for("dashboard.index"))
    if request.method == "POST":
        u  = request.form.get("username", "")
        pw = request.form.get("password", "")
        ph = hashlib.sha256(pw.encode()).hexdigest()
        with db() as c:
            row = c.execute("SELECT * FROM admins WHERE username=? AND password_hash=?", (u, ph)).fetchone()
        if row:
            session["admin_id"]       = row["id"]
            session["admin_username"] = row["username"]
            session["admin_role"]     = row["role"]
            return redirect(url_for("dashboard.index"))
        flash("帳號或密碼錯誤")
    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
