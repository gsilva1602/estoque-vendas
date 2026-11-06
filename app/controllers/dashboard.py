from decimal import Decimal

from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import case, func, select

from ..extensions import db
from ..models import Product, Sale, StockEntry
from ..services.stock import voided_ids

bp = Blueprint("dashboard", __name__)


@bp.route("/dashboard")
@login_required
def index():
    if current_user.role != "admin":
        if current_user.role == "vendedor":
            return redirect(url_for("vendas.index"))
        return redirect(url_for("estoque.index"))

    product_count = db.session.scalar(select(func.count(Product.id))) or 0

    units_in_stock = db.session.scalar(
        select(func.coalesce(func.sum(Product.quantity), 0))
    ) or 0

    # Vendas e entradas anuladas por correção ficam de fora dos indicadores.
    active_sale = Sale.id.not_in(voided_ids("venda"))

    sales_count = db.session.scalar(select(func.count(Sale.id)).where(active_sale)) or 0

    sales_total = db.session.scalar(
        select(func.coalesce(func.sum(Sale.total), 0)).where(active_sale)
    ) or Decimal("0.00")

    recent_sales = db.session.scalars(
        select(Sale).where(active_sale).order_by(Sale.created_at.desc()).limit(8)
    ).all()

    # Última entrada registrada para cada produto.
    latest_entries = (
        select(
            StockEntry.product_id,
            func.max(StockEntry.created_at).label("last_entry"),
        )
        .where(StockEntry.id.not_in(voided_ids("entrada")))
        .group_by(StockEntry.product_id)
        .subquery()
    )

    # Todos os produtos, ordenados pela entrada mais recente.
    stock_products = db.session.execute(
        select(Product, latest_entries.c.last_entry)
        .outerjoin(latest_entries, Product.id == latest_entries.c.product_id)
        .order_by(
            case((latest_entries.c.last_entry.is_(None), 1), else_=0),
            latest_entries.c.last_entry.desc(),
            Product.name.asc(),
        )
    ).all()

    low_stock_count = db.session.scalar(
        select(func.count(Product.id)).where(Product.quantity <= 5)
    ) or 0

    return render_template(
        "dashboard.html",
        product_count=product_count,
        units_in_stock=units_in_stock,
        sales_count=sales_count,
        sales_total=sales_total,
        recent_sales=recent_sales,
        stock_products=stock_products,
        low_stock_count=low_stock_count,
    )
