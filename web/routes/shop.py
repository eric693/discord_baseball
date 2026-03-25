from flask import Blueprint, render_template, request, redirect, url_for, flash
from web.app import login_required, admin_required
from database import db

bp = Blueprint("shop", __name__)


@bp.route("/")
@login_required
def index():
    with db() as c:
        items  = c.execute("SELECT * FROM shop_items ORDER BY is_active DESC, created_at DESC").fetchall()
        orders = c.execute(
            "SELECT o.*,i.name as item_name,m.username FROM shop_orders o "
            "JOIN shop_items i ON o.item_id=i.id JOIN members m ON o.discord_id=m.discord_id "
            "ORDER BY o.created_at DESC LIMIT 30").fetchall()
    return render_template("shop/index.html", items=list(items), orders=list(orders))


@bp.route("/add", methods=["POST"])
@admin_required
def add_item():
    name  = request.form.get("name", "").strip()
    desc  = request.form.get("description", "")
    cost  = int(request.form.get("cost", 0))
    stock = int(request.form.get("stock", -1))
    if not name or cost <= 0:
        flash("名稱與費用為必填，費用須大於 0"); return redirect(url_for("shop.index"))
    with db() as c:
        c.execute("INSERT INTO shop_items(name,description,cost,stock) VALUES(?,?,?,?)", (name, desc, cost, stock))
    flash(f"商品「{name}」已新增")
    return redirect(url_for("shop.index"))


@bp.route("/<int:item_id>/toggle", methods=["POST"])
@admin_required
def toggle_item(item_id):
    with db() as c:
        row = c.execute("SELECT is_active FROM shop_items WHERE id=?", (item_id,)).fetchone()
        c.execute("UPDATE shop_items SET is_active=? WHERE id=?", (0 if row["is_active"] else 1, item_id))
    flash("商品狀態已更新")
    return redirect(url_for("shop.index"))


@bp.route("/order/<int:order_id>/complete", methods=["POST"])
@admin_required
def complete_order(order_id):
    with db() as c:
        c.execute("UPDATE shop_orders SET status='completed' WHERE id=?", (order_id,))
    flash(f"訂單 #{order_id} 已標記完成")
    return redirect(url_for("shop.index"))
