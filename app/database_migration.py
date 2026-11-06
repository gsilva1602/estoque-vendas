from pathlib import Path

from sqlalchemy import Integer, create_engine, func, inspect, select, text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.schema import MetaData


def copy_sqlite_data(source_path: Path, target_engine: Engine, metadata: MetaData) -> dict[str, int]:
    """Copies all current application tables from SQLite into an empty database."""
    source_path = source_path.resolve()
    if not source_path.is_file():
        raise ValueError(f"Arquivo SQLite não encontrado: {source_path}")

    source_engine = create_engine(URL.create("sqlite", database=str(source_path)))
    try:
        source_inspector = inspect(source_engine)
        source_tables = set(source_inspector.get_table_names())
        tables = metadata.sorted_tables
        missing_tables = [table.name for table in tables if table.name not in source_tables]
        if missing_tables:
            raise ValueError(
                "O SQLite não contém todas as tabelas desta versão: "
                + ", ".join(missing_tables)
            )

        for table in tables:
            source_columns = {
                column["name"] for column in source_inspector.get_columns(table.name)
            }
            missing_columns = [
                column.name for column in table.columns if column.name not in source_columns
            ]
            if missing_columns:
                raise ValueError(
                    f"A tabela SQLite '{table.name}' não contém as colunas: "
                    + ", ".join(missing_columns)
                )

        with source_engine.connect() as source_connection:
            with target_engine.begin() as target_connection:
                for table in tables:
                    if target_connection.execute(select(table).limit(1)).first() is not None:
                        raise ValueError(
                            f"O destino não está vazio: a tabela '{table.name}' já contém dados."
                        )

                copied_rows: dict[str, int] = {}
                for table in tables:
                    result = source_connection.execute(select(table)).mappings()
                    count = 0
                    while batch := result.fetchmany(500):
                        target_connection.execute(
                            table.insert(), [dict(row) for row in batch]
                        )
                        count += len(batch)
                    copied_rows[table.name] = count

                if target_engine.dialect.name == "postgresql":
                    _advance_postgresql_sequences(target_connection, tables)

        return copied_rows
    except SQLAlchemyError as error:
        raise RuntimeError(f"Falha ao copiar os dados do SQLite: {error}") from error
    finally:
        source_engine.dispose()


def _advance_postgresql_sequences(connection, tables) -> None:
    for table in tables:
        primary_keys = list(table.primary_key.columns)
        if len(primary_keys) != 1 or not isinstance(primary_keys[0].type, Integer):
            continue

        primary_key = primary_keys[0]
        sequence = connection.scalar(
            text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
            {"table_name": table.fullname, "column_name": primary_key.name},
        )
        if sequence is None:
            continue

        maximum = connection.scalar(select(func.max(primary_key)))
        if maximum is not None:
            connection.execute(
                text("SELECT setval(CAST(:sequence_name AS regclass), :last_value, true)"),
                {"sequence_name": sequence, "last_value": maximum},
            )
