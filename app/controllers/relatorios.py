from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import func, select

from ..decorators import roles_required
from ..extensions import db
from ..models import Product, Sale, User
from ..services.stock import voided_ids
from ..timeutils import local_day_end_utc, local_day_start_utc

bp = Blueprint("relatorios", __name__)


@bp.route("/relatorios/vendas")
@login_required
@roles_required("admin")
def vendas():
    data_inicial = request.args.get("data_inicial", "").strip()
    data_final = request.args.get("data_final", "").strip()
    produto_id = request.args.get("produto_id", "").strip()
    vendedor_id = request.args.get("vendedor_id", "").strip()

    # Vendas anuladas por correção não entram em nenhum número do relatório.
    filtros = [Sale.id.not_in(voided_ids("venda"))]

    # Filtro por período
    try:
        if data_inicial:
            inicio = local_day_start_utc(datetime.strptime(data_inicial, "%Y-%m-%d").date())
            filtros.append(Sale.created_at >= inicio)

        if data_final:
            fim = local_day_end_utc(datetime.strptime(data_final, "%Y-%m-%d").date())
            filtros.append(Sale.created_at <= fim)

        if data_inicial and data_final:
            if data_inicial > data_final:
                raise ValueError

    except ValueError:
        flash("Informe um período válido para o relatório.", "error")
        return redirect(url_for("relatorios.vendas"))

    # Filtro por produto
    if produto_id:
        try:
            filtros.append(Sale.product_id == int(produto_id))
        except ValueError:
            flash("Produto inválido.", "error")
            return redirect(url_for("relatorios.vendas"))

    # Filtro por vendedor
    if vendedor_id:
        try:
            filtros.append(Sale.user_id == int(vendedor_id))
        except ValueError:
            flash("Vendedor inválido.", "error")
            return redirect(url_for("relatorios.vendas"))

    # Indicadores gerais
    indicadores = db.session.execute(
        select(
            func.count(Sale.id),
            func.coalesce(func.sum(Sale.quantity), 0),
            func.coalesce(func.sum(Sale.total), 0),
        ).where(*filtros)
    ).one()

    quantidade_vendas = indicadores[0]
    unidades_vendidas = indicadores[1]
    faturamento_total = indicadores[2]

    # Listagem das vendas
    lista_vendas = db.session.execute(
        select(Sale, Product, User)
        .join(Product, Sale.product_id == Product.id)
        .join(User, Sale.user_id == User.id)
        .where(*filtros)
        .order_by(Sale.created_at.desc())
    ).all()

    # Ranking de produtos por unidades vendidas
    produtos_mais_vendidos = db.session.execute(
        select(
            Product.name,
            func.sum(Sale.quantity).label("unidades"),
            func.sum(Sale.total).label("faturamento"),
        )
        .join(Product, Sale.product_id == Product.id)
        .where(*filtros)
        .group_by(Product.id, Product.name)
        .order_by(func.sum(Sale.quantity).desc())
        .limit(10)
    ).all()

    # Faturamento por vendedor
    faturamento_por_vendedor = db.session.execute(
        select(
            User.username,
            func.count(Sale.id).label("vendas"),
            func.sum(Sale.quantity).label("unidades"),
            func.sum(Sale.total).label("faturamento"),
        )
        .join(User, Sale.user_id == User.id)
        .where(*filtros)
        .group_by(User.id, User.username)
        .order_by(func.sum(Sale.total).desc())
    ).all()

    produtos = db.session.execute(select(Product).order_by(Product.name)).scalars().all()

    vendedores = db.session.execute(
        select(User).where(User.role == "vendedor").order_by(User.username)
    ).scalars().all()

    return render_template(
        "relatorios_vendas.html",
        vendas=lista_vendas,
        produtos=produtos,
        vendedores=vendedores,
        produtos_mais_vendidos=produtos_mais_vendidos,
        faturamento_por_vendedor=faturamento_por_vendedor,
        quantidade_vendas=quantidade_vendas,
        unidades_vendidas=unidades_vendidas,
        faturamento_total=faturamento_total,
        data_inicial=data_inicial,
        data_final=data_final,
        produto_id=produto_id,
        vendedor_id=vendedor_id,
    )
