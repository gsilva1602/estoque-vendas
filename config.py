import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name(".env.local"))

def _normalize_database_url(database_url):
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = _normalize_database_url(
        os.environ.get("DATABASE_URL", "sqlite:///estoque.db")
    )
    DATABASE_URL_UNPOOLED = _normalize_database_url(
        os.environ.get("DATABASE_URL_UNPOOLED", "")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # O banco guarda UTC; as telas mostram (e os filtros de data usam) este fuso.
    APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "America/Sao_Paulo")

    # Prazo (em minutos, contado a partir do lançamento) para o autor corrigir o próprio erro.
    CORRECTION_WINDOW_MINUTES = int(os.environ.get("CORRECTION_WINDOW_MINUTES", "30"))
