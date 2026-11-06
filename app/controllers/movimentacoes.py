from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..decorators import roles_required
from ..extensions import db
from ..models import MOVEMENT_LABELS, MOVEMENT_TYPES, Product, StockMovement
from ..timeutils import local_day_end_utc, local_day_start_utc

bp = Blueprint("movimentacoes", __name__)

BADGE_CLASS = {
    "entrada": "status-ok",
    "venda": "status-low",
    "estorno": "status-empty",
    "ajuste": "status-empty",
}


def _detalhe(mov):
    if mov.movement_type == "entrada":
        base = "Reposição de estoque"
    elif mov.movement_type == "venda" and mov.sale is not None:
        base = f"Venda registrada: R$ {mov.sale.total:.2f}"
    elif mov.movement_type == "estorno":
        base = "Estorno de lançamento corrigido"
    else:
        base = "Ajuste"
    if mov.justification:
        return f"{base} · Justificativa: {mov.justification}"
    return base


@bp.route("/movimentacoes")
@roles_required("admin", "estoquista")
def index():
    produto_id = request.args.get("produto", type=int)
    tipo = request.args.get("tipo", "").strip()
    inicio = request.args.get("inicio", "").strip()
    fim = request.args.get("fim", "").strip()

    query = select(StockMovement).options(
        selectinload(StockMovement.product),
        selectinload(StockMovement.user),
        selectinload(StockMovement.sale),
    )

    if produto_id:
        query = query.where(StockMovement.product_id == produto_id)

    if tipo in MOVEMENT_TYPES:
        query = query.where(StockMovement.movement_type == tipo)

    if inicio:
        try:
            data_inicio = local_day_start_utc(datetime.strptime(inicio, "%Y-%m-%d").date())
            query = query.where(StockMovement.created_at >= data_inicio)
        except ValueError:
            flash("Data inicial inválida.", "error")
            return redirect(url_for("movimentacoes.index"))

    if fim:
        try:
            data_fim = local_day_end_utc(datetime.strptime(fim, "%Y-%m-%d").date())
            query = query.where(StockMovement.created_at <= data_fim)
        except ValueError:
            flash("Data final inválida.", "error")
            return redirect(url_for("movimentacoes.index"))

    movimentos = db.session.scalars(
        query.order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
    ).all()

    historico = [
        {
            "data": m.created_at,
            "tipo": MOVEMENT_LABELS[m.movement_type],
            "classe": BADGE_CLASS[m.movement_type],
            "produto": m.product.name,
            "produto_id": m.product_id,
            "quantidade": m.quantity,
            "saldo_antes": m.balance_before,
            "saldo_depois": m.balance_after,
            "responsavel": m.user.username if m.user else "Sistema",
            "detalhe": _detalhe(m),
        }
        for m in movimentos
    ]

    produtos = db.session.scalars(select(Product).order_by(Product.name)).all()

    return render_template(
        "movimentacoes.html",
        historico=historico,
        produtos=produtos,
        tipos=[(t, MOVEMENT_LABELS[t]) for t in MOVEMENT_TYPES],
        produto_selecionado=produto_id,
        tipo_selecionado=tipo,
        inicio=inicio,
        fim=fim,
    )
