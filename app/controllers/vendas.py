from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import select

from ..decorators import roles_required
from ..extensions import db
from ..models import Product, Sale
from ..services.stock import (CorrectionError, annotate, check_can_correct, correct_sale,
                              parse_correction_input, register_sale, seconds_left)

bp = Blueprint("vendas", __name__)


@bp.route("/vendas", methods=["GET", "POST"])
@roles_required("admin", "vendedor")
def index():
    if request.method == "POST":
        if current_user.role != "vendedor":
            flash("Somente vendedores podem registrar vendas.", "error")
            return redirect(url_for("vendas.index"))
        try:
            product_id = int(request.form.get("product_id", ""))
            quantity = int(request.form.get("quantity", ""))
            if quantity <= 0:
                raise ValueError
        except ValueError:
            flash("Selecione um produto e informe uma quantidade inteira maior que zero.", "error")
            return redirect(url_for("vendas.index"))
        product = db.session.get(Product, product_id)
        if not product:
            flash("Produto não encontrado.", "error")
            return redirect(url_for("vendas.index"))
        if product.quantity < quantity:
            flash(f"Estoque insuficiente para {product.name}. Disponível: {product.quantity} unidade(s).", "error")
            return redirect(url_for("vendas.index"))
        register_sale(product, quantity, current_user)
        flash("Venda registrada e estoque atualizado.", "success")
        return redirect(url_for("vendas.index"))
    products = db.session.scalars(select(Product).where(Product.quantity > 0).order_by(Product.name)).all()
    query = select(Sale).order_by(Sale.created_at.desc()).limit(100)
    if current_user.role == "vendedor":
        query = select(Sale).where(Sale.user_id == current_user.id).order_by(Sale.created_at.desc()).limit(100)
    sales = db.session.scalars(query).all()
    sale_rows = annotate("venda", sales, current_user)
    return render_template("vendas.html", products=products, sale_rows=sale_rows,
                           can_sell=current_user.role == "vendedor")


@bp.route("/vendas/<int:sale_id>/corrigir", methods=["GET", "POST"])
@roles_required("vendedor")
def correct_sale_view(sale_id):
    sale = db.session.get(Sale, sale_id)
    if not sale:
        flash("Venda não encontrada.", "error")
        return redirect(url_for("vendas.index"))
    try:
        check_can_correct("venda", sale, current_user)
    except CorrectionError as exc:
        flash(str(exc), "error")
        return redirect(url_for("vendas.index"))

    values = {"quantity": "", "justification": ""}
    if request.method == "POST":
        values = {"quantity": request.form.get("quantity", ""),
                  "justification": request.form.get("justification", "")}
        try:
            new_quantity, justification = parse_correction_input(
                values["quantity"], values["justification"], sale.quantity)
            old_quantity = sale.quantity
            correct_sale(sale, new_quantity, justification, current_user)
        except CorrectionError as exc:
            flash(str(exc), "error")
        else:
            if new_quantity == 0:
                flash("Venda cancelada e estoque devolvido. A justificativa ficou registrada.", "success")
            else:
                flash(f"Venda corrigida de {old_quantity} para {new_quantity} unidade(s). "
                      "A justificativa ficou registrada.", "success")
            return redirect(url_for("vendas.index"))

    return render_template(
        "corrigir.html",
        titulo="Corrigir venda",
        tipo="venda",
        record=sale,
        produto=sale.product.name,
        minutos=max(1, -(-int(seconds_left(sale)) // 60)),
        quantidade_label="Quantidade vendida (nova)",
        post_url=url_for("vendas.correct_sale_view", sale_id=sale.id),
        voltar_url=url_for("vendas.index"),
        values=values,
    )
