import pytest

from config import _normalize_database_url


@pytest.mark.parametrize(
    ("database_url", "expected"),
    [
        (
            "postgres://user:pass@localhost:5432/estoque",
            "postgresql+psycopg://user:pass@localhost:5432/estoque",
        ),
        (
            "postgresql://user:pass@localhost:5432/estoque",
            "postgresql+psycopg://user:pass@localhost:5432/estoque",
        ),
        (
            "postgresql+psycopg://user:pass@localhost:5432/estoque",
            "postgresql+psycopg://user:pass@localhost:5432/estoque",
        ),
        ("sqlite:///estoque.db", "sqlite:///estoque.db"),
    ],
)
def test_normalize_database_url(database_url, expected):
    assert _normalize_database_url(database_url) == expected
