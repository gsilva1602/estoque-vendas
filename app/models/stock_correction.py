from ..extensions import db


class StockCorrection(db.Model):
    """Ato de correção de uma entrada ou venda feito pelo próprio autor, dentro do prazo.

    O lançamento original nunca é alterado: ele é anulado por um estorno e, se a nova
    quantidade for maior que zero, substituído por um novo registro (new_record_id).
    new_quantity == 0 significa cancelamento.
    kind: "entrada" (ids de stock_entry) ou "venda" (ids de sale).
    """

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(10), nullable=False, index=True)
    original_record_id = db.Column(db.Integer, nullable=False, index=True)
    new_record_id = db.Column(db.Integer, nullable=True, index=True)
    old_quantity = db.Column(db.Integer, nullable=False)
    new_quantity = db.Column(db.Integer, nullable=False)
    estorno_movement_id = db.Column(db.Integer, db.ForeignKey("stock_movement.id"), nullable=False)
    replacement_movement_id = db.Column(db.Integer, db.ForeignKey("stock_movement.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    justification = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.current_timestamp())

    user = db.relationship("User")
    estorno_movement = db.relationship("StockMovement", foreign_keys=[estorno_movement_id])
    replacement_movement = db.relationship("StockMovement", foreign_keys=[replacement_movement_id])
