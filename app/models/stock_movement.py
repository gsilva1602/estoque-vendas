from ..extensions import db

MOVEMENT_TYPES = ("entrada", "venda", "estorno", "ajuste")

MOVEMENT_LABELS = {
    "entrada": "Entrada",
    "venda": "Venda",
    "estorno": "Estorno",
    "ajuste": "Ajuste",
}


class StockMovement(db.Model):
    """Livro-razão do estoque: cada alteração de saldo vira uma linha, nunca é editada.

    quantity é sempre o delta com sinal (+ entra, - sai).
    user_id é nulo apenas para lançamentos feitos pelo próprio sistema (carga inicial).
    reverses_movement_id será usado pelos estornos (etapa 3).
    """

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)
    movement_type = db.Column(db.String(20), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    balance_before = db.Column(db.Integer, nullable=False)
    balance_after = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    justification = db.Column(db.Text, nullable=True)
    stock_entry_id = db.Column(db.Integer, db.ForeignKey("stock_entry.id"), nullable=True, index=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sale.id"), nullable=True, index=True)
    reverses_movement_id = db.Column(db.Integer, db.ForeignKey("stock_movement.id"), nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.current_timestamp(), index=True
    )

    product = db.relationship("Product")
    user = db.relationship("User")
    stock_entry = db.relationship("StockEntry")
    sale = db.relationship("Sale")
    reverses = db.relationship("StockMovement", remote_side=[id])
