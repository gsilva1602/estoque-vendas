from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..decorators import roles_required
from ..extensions import db
from ..models import Product, StockEntry
from ..services.stock import (CorrectionError, annotate, check_can_correct, correct_entry,
                              parse_correction_input, register_entry, seconds_left)

bp = Blueprint("estoque", __name__)


@bp.route("/estoque", methods=["GET", "POST"])
@roles_required("admin", "estoquista")
def index():
    # Admin sees stock data on dashboard; only the stock clerk can make stock changes.
    if current_user.role == "admin":
        flash("O administrador consulta os indicadores de estoque pelo dashboard.", "warning")
        return redirect(url_for("dashboard.index"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        raw_price = request.form.get("unit_price", "0").strip().replace(",", ".")
        try:
            price = Decimal(raw_price)
            if not name or not category or price < 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            flash("Informe nome, categoria e preço válido (zero ou maior).", "error")
            return redirect(url_for("estoque.index"))
        product = Product(name=name, category=category, quantity=0, unit_price=price)
        db.session.add(product)
        try:
            db.session.commit()
            flash("Produto cadastrado. Registre a entrada para adicionar unidades ao estoque.", "success")
        except IntegrityError:
            db.session.rollback()
            flash("Não foi possível cadastrar o produto.", "error")
        return redirect(url_for("estoque.index"))
    products = db.session.scalars(select(Product).order_by(Product.name)).all()
    entries = db.session.scalars(select(StockEntry).order_by(StockEntry.created_at.desc()).limit(20)).all()
    entry_rows = annotate("entrada", entries, current_user)
    return render_template("estoque.html", products=products, entry_rows=entry_rows)


@bp.route("/estoque/entrada", methods=["POST"])
@roles_required("estoquista")
def stock_entry():
    try:
        product_id = int(request.form.get("product_id", ""))
        quantity = int(request.form.get("quantity", ""))
        if quantity <= 0:
            raise ValueError
    except ValueError:
        flash("Selecione um produto e informe uma quantidade inteira maior que zero.", "error")
        return redirect(url_for("estoque.index"))
    product = db.session.get(Product, product_id)
    if not product:
        flash("Produto não encontrado.", "error")
        return redirect(url_for("estoque.index"))
    register_entry(product, quantity, current_user)
    flash(f"Entrada registrada: +{quantity} unidade(s) de {product.name}.", "success")
    return redirect(url_for("estoque.index"))


@bp.route("/estoque/entrada/<int:entry_id>/corrigir", methods=["GET", "POST"])
@roles_required("estoquista")
def correct_entry_view(entry_id):
    entry = db.session.get(StockEntry, entry_id)
    if not entry:
        flash("Entrada não encontrada.", "error")
        return redirect(url_for("estoque.index"))
    try:
        check_can_correct("entrada", entry, current_user)
    except CorrectionError as exc:
        flash(str(exc), "error")
        return redirect(url_for("estoque.index"))

    values = {"quantity": "", "justification": ""}
    if request.method == "POST":
        values = {"quantity": request.form.get("quantity", ""),
                  "justification": request.form.get("justification", "")}
        try:
            new_quantity, justification = parse_correction_input(
                values["quantity"], values["justification"], entry.quantity)
            correct_entry(entry, new_quantity, justification, current_user)
        except CorrectionError as exc:
            flash(str(exc), "error")
        else:
            if new_quantity == 0:
                flash("Entrada cancelada e estoque ajustado. A justificativa ficou registrada.", "success")
            else:
                flash(f"Entrada corrigida de {entry.quantity} para {new_quantity} unidade(s). "
                      "A justificativa ficou registrada.", "success")
            return redirect(url_for("estoque.index"))

    return render_template(
        "corrigir.html",
        titulo="Corrigir entrada de estoque",
        tipo="entrada",
        record=entry,
        produto=entry.product.name,
        minutos=max(1, -(-int(seconds_left(entry)) // 60)),
        quantidade_label="Quantidade recebida (nova)",
        post_url=url_for("estoque.correct_entry_view", entry_id=entry.id),
        voltar_url=url_for("estoque.index"),
        values=values,
    )
