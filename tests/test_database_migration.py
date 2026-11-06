from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import URL

from app.database_migration import copy_sqlite_data
from app.extensions import db
from app.models import Product, User


def test_copy_sqlite_data_preserves_records_and_refuses_nonempty_target(
    app, tmp_path
):
    with app.app_context():
        user = db.session.scalar(select(User).where(User.username == "adm"))
        db.session.add(
            Product(
                name="Produto para migrar",
                category="Teste",
                quantity=12,
                unit_price=10,
            )
        )
        db.session.commit()

        source_path = Path(db.engine.url.database)
        target_path = tmp_path / "destino.db"
        target_engine = create_engine(URL.create("sqlite", database=str(target_path)))
        db.metadata.create_all(target_engine)

        copied_rows = copy_sqlite_data(source_path, target_engine, db.metadata)

        assert copied_rows["user"] == 5
        assert copied_rows["product"] == 1
        with target_engine.connect() as connection:
            copied_user = connection.execute(
                select(db.metadata.tables["user"].c.username).where(
                    db.metadata.tables["user"].c.id == user.id
                )
            ).scalar_one()
            copied_product_count = connection.scalar(
                select(func.count()).select_from(db.metadata.tables["product"])
            )
        assert copied_user == "adm"
        assert copied_product_count == 1

        with pytest.raises(ValueError, match="destino não está vazio"):
            copy_sqlite_data(source_path, target_engine, db.metadata)
        target_engine.dispose()


def test_migration_cli_requires_postgresql(app):
    result = app.test_cli_runner().invoke(args=["migrate-sqlite"])

    assert result.exit_code != 0
    assert "Configure DATABASE_URL com um PostgreSQL" in result.output
