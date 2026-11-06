"""Fuso horário: o banco guarda UTC (sem fuso); a tela mostra o horário local."""
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from flask import current_app


def local_tz():
    return ZoneInfo(current_app.config["APP_TIMEZONE"])


def to_local(value):
    """datetime UTC sem fuso (como vem do banco) -> datetime no horário local."""
    return value.replace(tzinfo=timezone.utc).astimezone(local_tz())


def format_local(value, fmt="%d/%m/%Y %H:%M:%S"):
    if value is None:
        return ""
    return to_local(value).strftime(fmt)


def local_day_start_utc(day):
    """Início (00:00:00) do dia local, convertido para UTC sem fuso, para filtrar no banco."""
    return (datetime.combine(day, time.min, tzinfo=local_tz())
            .astimezone(timezone.utc).replace(tzinfo=None))


def local_day_end_utc(day):
    """Fim (23:59:59.999999) do dia local, convertido para UTC sem fuso."""
    return (datetime.combine(day, time.max, tzinfo=local_tz())
            .astimezone(timezone.utc).replace(tzinfo=None))
