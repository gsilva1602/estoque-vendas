from datetime import datetime, timezone
from pathlib import Path

import click
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db
from .models import ROLES, Product, Sale, StockEntry, StockMovement, User
from .database_migration import copy_sqlite_data


def _utcnow():
    # created_at do banco usa CURRENT_TIMESTAMP (UTC, sem fuso); mantemos o mesmo padrão.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def register_commands(app):
    @app.cli.command("init-db")
    def init_db():
        """Cria as tabelas que ainda não existem (não altera as existentes)."""
        db.create_all()
        print("Banco inicializado.")

    @app.cli.command("migrate-sqlite")
    @click.option(
        "--source",
        "source_path",
        type=click.Path(exists=True, dir_okay=False, path_type=Path),
        default=Path(app.instance_path) / "estoque.db",
        show_default=True,
        help="Arquivo SQLite que será importado.",
    )
    def migrate_sqlite(source_path):
        """Copia os dados do SQLite para o PostgreSQL configurado em DATABASE_URL."""
        if db.engine.dialect.name != "postgresql":
            raise click.ClickException(
                "Configure DATABASE_URL com um PostgreSQL antes de executar esta migração."
            )

        unpooled_url = app.config.get("DATABASE_URL_UNPOOLED")
        target_engine = db.engine
        try:
            if unpooled_url:
                target_engine = create_engine(unpooled_url)
            db.metadata.create_all(target_engine)
            copied_rows = copy_sqlite_data(source_path, target_engine, db.metadata)
        except (RuntimeError, SQLAlchemyError, ValueError) as error:
            raise click.ClickException(str(error)) from error
        finally:
            if target_engine is not db.engine:
                target_engine.dispose()

        for table_name, count in copied_rows.items():
            click.echo(f"{table_name}: {count} registro(s)")
        click.echo("Migração concluída.")

    @app.cli.command("create-user")
    def create_user():
        username = input("Usuário: ").strip()
        password = input("Senha (mínimo 8 caracteres): ")
        role = input("Perfil (admin/vendedor/estoquista): ").strip().lower()
        if not username or len(password) < 8 or role not in ROLES:
            print("Dados inválidos. Verifique o usuário, a senha e o perfil.")
            return
        if db.session.scalar(select(User).where(User.username == username)):
            print("Esse usuário já existe.")
            return
        user = User(username=username, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f"Usuário '{username}' criado com perfil '{role}'.")

    @app.cli.command("backfill-movements")
    @click.option("--dry-run", is_flag=True, help="Mostra o que seria feito, sem gravar nada.")
    def backfill_movements(dry_run):
        """Carrega entradas e vendas já existentes na tabela de movimentações.

        Produtos que já têm movimentações são pulados, então o comando pode ser repetido.
        Se o histórico não fechar com o saldo atual do produto, é criado um lançamento
        de 'ajuste' do sistema com a diferença, para o saldo do livro-razão bater.
        """
        total_mov = total_ajustes = 0
        for product in db.session.scalars(select(Product).order_by(Product.id)).all():
            ja_tem = db.session.scalar(
                select(StockMovement.id).where(StockMovement.product_id == product.id).limit(1)
            )
            if ja_tem:
                print(f"[{product.id}] {product.name}: já possui movimentações, pulado.")
                continue

            entradas = db.session.scalars(
                select(StockEntry).where(StockEntry.product_id == product.id)
            ).all()
            vendas = db.session.scalars(
                select(Sale).where(Sale.product_id == product.id)
            ).all()

            # Mesma data/hora: a entrada vem antes da venda (não se vende o que não entrou).
            eventos = [(e.created_at, 0, e.id, e) for e in entradas]
            eventos += [(v.created_at, 1, v.id, v) for v in vendas]
            eventos.sort(key=lambda x: x[:3])

            saldo = 0
            negativo = False
            for created_at, tipo, _id, origem in eventos:
                delta = origem.quantity if tipo == 0 else -origem.quantity
                db.session.add(StockMovement(
                    product=product,
                    movement_type="entrada" if tipo == 0 else "venda",
                    quantity=delta,
                    balance_before=saldo,
                    balance_after=saldo + delta,
                    user_id=origem.user_id,
                    stock_entry=origem if tipo == 0 else None,
                    sale=origem if tipo == 1 else None,
                    created_at=created_at,
                ))
                saldo += delta
                negativo = negativo or saldo < 0
            total_mov += len(eventos)

            linha = f"[{product.id}] {product.name}: {len(entradas)} entrada(s), {len(vendas)} venda(s)"
            if negativo:
                linha += " | ATENÇÃO: o histórico passa por saldo negativo"
            if saldo != product.quantity:
                diferenca = product.quantity - saldo
                db.session.add(StockMovement(
                    product=product,
                    movement_type="ajuste",
                    quantity=diferenca,
                    balance_before=saldo,
                    balance_after=product.quantity,
                    user_id=None,
                    justification=(
                        "Conciliação da carga inicial: o saldo atual do produto "
                        f"({product.quantity}) diferia do histórico ({saldo})."
                    ),
                    created_at=_utcnow(),
                ))
                total_ajustes += 1
                linha += f" | DIVERGÊNCIA: histórico = {saldo}, saldo atual = {product.quantity} (ajuste {diferenca:+d})"
            print(linha)

        if dry_run:
            db.session.rollback()
            print(f"\n[dry-run] Nada foi gravado. Seriam criados {total_mov} movimento(s) e {total_ajustes} ajuste(s).")
        else:
            db.session.commit()
            print(f"\nConcluído: {total_mov} movimento(s) carregado(s) e {total_ajustes} ajuste(s) de conciliação.")
