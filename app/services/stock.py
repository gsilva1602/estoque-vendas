"""Regras de estoque. Toda alteração de saldo passa por record_movement."""
import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from flask import current_app
from sqlalchemy import or_, select

from ..extensions import db
from ..models import Sale, StockCorrection, StockEntry, StockMovement

MIN_JUSTIFICATION = 10
MAX_JUSTIFICATION = 500


class InsufficientStock(Exception):
    """A operação deixaria o saldo do produto negativo."""


class CorrectionError(Exception):
    """Correção não permitida. A mensagem já está pronta para ser mostrada ao usuário."""


def utcnow():
    # created_at do banco usa CURRENT_TIMESTAMP (UTC, sem fuso); usamos o mesmo padrão.
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------- movimentos

def record_movement(product, movement_type, delta, user_id, *, justification=None,
                    stock_entry=None, sale=None, reverses=None):
    """Aplica delta ao saldo do produto e grava a linha no livro-razão.

    Não faz commit: quem chama decide, para que tudo fique na mesma transação.
    """
    before = product.quantity
    after = before + delta
    if after < 0:
        raise InsufficientStock(
            f"Saldo insuficiente para {product.name}: disponível {before}, movimento {delta}."
        )
    product.quantity = after
    movement = StockMovement(
        product=product,
        movement_type=movement_type,
        quantity=delta,
        balance_before=before,
        balance_after=after,
        user_id=user_id,
        justification=justification,
        stock_entry=stock_entry,
        sale=sale,
        reverses=reverses,
    )
    db.session.add(movement)
    return movement


def register_entry(product, quantity, user):
    entry = StockEntry(product_id=product.id, quantity=quantity, user_id=user.id)
    db.session.add(entry)
    record_movement(product, "entrada", quantity, user.id, stock_entry=entry)
    db.session.commit()
    return entry


def register_sale(product, quantity, user):
    unit_price = Decimal(product.unit_price)
    sale = Sale(product_id=product.id, quantity=quantity, unit_price=unit_price,
                total=unit_price * quantity, user_id=user.id)
    db.session.add(sale)
    record_movement(product, "venda", -quantity, user.id, sale=sale)
    db.session.commit()
    return sale


# ---------------------------------------------------------------- correções

def voided_ids(kind):
    """Subconsulta com os ids de entradas ("entrada") ou vendas ("venda") anuladas por correção."""
    return select(StockCorrection.original_record_id).where(StockCorrection.kind == kind)


def is_voided(kind, record_id):
    return db.session.scalar(
        select(StockCorrection.id).where(
            StockCorrection.kind == kind, StockCorrection.original_record_id == record_id
        ).limit(1)
    ) is not None


def seconds_left(record, now=None):
    window = timedelta(minutes=current_app.config["CORRECTION_WINDOW_MINUTES"])
    return (record.created_at + window - (now or utcnow())).total_seconds()


def check_can_correct(kind, record, user, now=None):
    """Levanta CorrectionError se o usuário não puder corrigir este lançamento agora."""
    if record.user_id != user.id:
        raise CorrectionError("Você só pode corrigir lançamentos feitos por você.")
    if is_voided(kind, record.id):
        raise CorrectionError(
            "Este lançamento já foi corrigido ou cancelado e não pode ser alterado novamente. "
            "Se precisar, corrija o lançamento que o substituiu."
        )
    if seconds_left(record, now) <= 0:
        minutes = current_app.config["CORRECTION_WINDOW_MINUTES"]
        raise CorrectionError(
            f"O prazo de {minutes} minutos para corrigir este lançamento já acabou. "
            "Procure o administrador."
        )


def can_correct(kind, record, user, now=None):
    try:
        check_can_correct(kind, record, user, now)
        return True
    except CorrectionError:
        return False


def parse_correction_input(raw_quantity, raw_justification, old_quantity):
    try:
        quantity = int(str(raw_quantity).strip())
    except ValueError:
        raise CorrectionError(
            "Informe a nova quantidade como número inteiro (use 0 para cancelar o lançamento)."
        )
    if quantity < 0:
        raise CorrectionError("A nova quantidade não pode ser negativa.")
    if quantity == old_quantity:
        raise CorrectionError("A nova quantidade é igual à atual; não há o que corrigir.")
    justification = (raw_justification or "").strip()
    if len(justification) < MIN_JUSTIFICATION:
        raise CorrectionError(
            f"Descreva o motivo da correção (mínimo de {MIN_JUSTIFICATION} caracteres)."
        )
    if len(justification) > MAX_JUSTIFICATION:
        raise CorrectionError(f"A justificativa pode ter no máximo {MAX_JUSTIFICATION} caracteres.")
    return quantity, justification


def _original_movement(*, entry=None, sale=None):
    query = select(StockMovement)
    if entry is not None:
        query = query.where(
            StockMovement.stock_entry_id == entry.id, StockMovement.movement_type == "entrada"
        )
    else:
        query = query.where(
            StockMovement.sale_id == sale.id, StockMovement.movement_type == "venda"
        )
    movement = db.session.scalars(query.order_by(StockMovement.id)).first()
    if movement is None:
        raise CorrectionError("Movimentação original não encontrada. Procure o administrador.")
    return movement


def correct_entry(entry, new_quantity, justification, user, now=None):
    """Corrige a quantidade de uma entrada (0 cancela). Estorno + novo lançamento, tudo ou nada."""
    check_can_correct("entrada", entry, user, now)
    product, old = entry.product, entry.quantity
    if product.quantity + (new_quantity - old) < 0:
        raise CorrectionError(
            f"Não é possível corrigir: o estoque atual de {product.name} ({product.quantity}) "
            "ficaria negativo, pois parte dessas unidades já saiu. Procure o administrador."
        )
    original_movement = _original_movement(entry=entry)

    replacement = replacement_movement = None
    try:
        # O novo lançamento entra primeiro, para o saldo do livro-razão nunca ficar negativo.
        if new_quantity > 0:
            replacement = StockEntry(product_id=product.id, quantity=new_quantity,
                                     user_id=entry.user_id, created_at=entry.created_at)
            db.session.add(replacement)
            replacement_movement = record_movement(
                product, "entrada", new_quantity, user.id,
                justification=justification, stock_entry=replacement)
        estorno = record_movement(
            product, "estorno", -old, user.id,
            justification=justification, stock_entry=entry, reverses=original_movement)
        db.session.flush()
        db.session.add(StockCorrection(
            kind="entrada", original_record_id=entry.id,
            new_record_id=replacement.id if replacement else None,
            old_quantity=old, new_quantity=new_quantity,
            estorno_movement=estorno, replacement_movement=replacement_movement,
            user_id=user.id, justification=justification))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return replacement


def correct_sale(sale, new_quantity, justification, user, now=None):
    """Corrige a quantidade de uma venda (0 cancela). O preço unitário original é mantido."""
    check_can_correct("venda", sale, user, now)
    product, old = sale.product, sale.quantity
    if product.quantity + old - new_quantity < 0:
        raise CorrectionError(
            f"Estoque insuficiente para aumentar esta venda: {product.name} tem "
            f"{product.quantity} unidade(s) disponível(is) além das {old} já vendidas."
        )
    original_movement = _original_movement(sale=sale)

    replacement = replacement_movement = None
    try:
        # O estorno devolve o estoque primeiro; depois a venda corrigida o consome de novo.
        estorno = record_movement(
            product, "estorno", old, user.id,
            justification=justification, sale=sale, reverses=original_movement)
        if new_quantity > 0:
            unit_price = Decimal(sale.unit_price)
            replacement = Sale(product_id=product.id, quantity=new_quantity, unit_price=unit_price,
                               total=unit_price * new_quantity, user_id=sale.user_id,
                               created_at=sale.created_at)
            db.session.add(replacement)
            replacement_movement = record_movement(
                product, "venda", -new_quantity, user.id,
                justification=justification, sale=replacement)
        db.session.flush()
        db.session.add(StockCorrection(
            kind="venda", original_record_id=sale.id,
            new_record_id=replacement.id if replacement else None,
            old_quantity=old, new_quantity=new_quantity,
            estorno_movement=estorno, replacement_movement=replacement_movement,
            user_id=user.id, justification=justification))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return replacement


def annotate(kind, records, user, now=None):
    """Prepara as linhas das listas: situação do lançamento e se o usuário pode corrigi-lo."""
    ids = [r.id for r in records]
    corrections = []
    if ids:
        corrections = db.session.scalars(
            select(StockCorrection).where(
                StockCorrection.kind == kind,
                or_(StockCorrection.original_record_id.in_(ids),
                    StockCorrection.new_record_id.in_(ids)),
            )
        ).all()
    voided = {c.original_record_id: c for c in corrections}
    replacements = {c.new_record_id: c for c in corrections if c.new_record_id}

    rows = []
    for record in records:
        if record.id in voided:
            c = voided[record.id]
            status = "Cancelada" if c.new_quantity == 0 else "Substituída"
            row = {"status": status, "classe": "status-empty", "note": c.justification,
                   "can_correct": False, "minutes_left": 0}
        else:
            c = replacements.get(record.id)
            allowed = can_correct(kind, record, user, now)
            row = {"status": "Corrigida" if c else "Ativa",
                   "classe": "status-low" if c else "status-ok",
                   "note": c.justification if c else "",
                   "can_correct": allowed,
                   "minutes_left": max(1, math.ceil(seconds_left(record, now) / 60)) if allowed else 0}
        row["record"] = record
        rows.append(row)
    return rows
