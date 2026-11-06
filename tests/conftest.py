"""Fixtures compartilhadas. Cada teste usa um banco SQLite novo, em pasta temporária."""
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, text

from app import create_app
from app.extensions import db
from app.models import Product, User
from app.services.stock import register_entry, utcnow

SENHA = "senha12345"
USUARIOS = [
    ("adm", "admin"),
    ("vend", "vendedor"),
    ("vend2", "vendedor"),
    ("est", "estoquista"),
    ("est2", "estoquista"),
]


@pytest.fixture(autouse=True)
def hash_de_senha_rapido(monkeypatch):
    """O hash padrão (scrypt) é lento de propósito; nos testes usamos um mais leve para a suíte ser rápida."""
    from werkzeug.security import generate_password_hash
    monkeypatch.setattr(
        "app.models.user.generate_password_hash",
        lambda senha: generate_password_hash(senha, method="pbkdf2:sha256:1000"),
    )


@pytest.fixture
def criar_app(tmp_path):
    """Fábrica de apps de teste. `tabelas` permite simular um banco antigo (só algumas tabelas)."""
    def _criar(nome_db="teste.db", tabelas=None):
        app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / nome_db}",
        })
        with app.app_context():
            if tabelas is None:
                db.create_all()
            else:
                db.metadata.create_all(db.engine, tables=[db.metadata.tables[t] for t in tabelas])
            for username, role in USUARIOS:
                usuario = User(username=username, role=role)
                usuario.set_password(SENHA)
                db.session.add(usuario)
            db.session.commit()
        return app
    return _criar


@pytest.fixture
def app(criar_app):
    return criar_app()


@pytest.fixture
def consulta(app):
    """Executa uma função dentro do contexto do app e devolve o resultado (use valores simples)."""
    def _consulta(funcao):
        with app.app_context():
            return funcao()
    return _consulta


@pytest.fixture
def login(app):
    def _login(username):
        cliente = app.test_client()
        resposta = cliente.post("/login", data={"username": username, "password": SENHA})
        assert resposta.status_code == 302, f"login de {username} falhou"
        return cliente
    return _login


@pytest.fixture
def adm(login):
    return login("adm")


@pytest.fixture
def vend(login):
    return login("vend")


@pytest.fixture
def vend2(login):
    return login("vend2")


@pytest.fixture
def est(login):
    return login("est")


@pytest.fixture
def est2(login):
    return login("est2")


@pytest.fixture
def novo_produto(app):
    """Cria um produto direto no banco; se `estoque` > 0, registra a entrada (como o usuário `est`)."""
    def _criar(nome="Cupcake Chocolate", preco="8.50", estoque=0):
        with app.app_context():
            produto = Product(name=nome, category="Cupcake", quantity=0, unit_price=Decimal(preco))
            db.session.add(produto)
            db.session.commit()
            if estoque:
                estoquista = db.session.scalar(select(User).where(User.username == "est"))
                register_entry(produto, estoque, estoquista)
            return produto.id
    return _criar


@pytest.fixture
def envelhecer(app):
    """Faz um lançamento parecer ter sido feito há N minutos (para testar o prazo de correção)."""
    def _envelhecer(tabela, registro_id, minutos):
        momento = (utcnow() - timedelta(minutes=minutos)).strftime("%Y-%m-%d %H:%M:%S")
        with app.app_context():
            db.session.execute(
                text(f"UPDATE {tabela} SET created_at = :t WHERE id = :i"),
                {"t": momento, "i": registro_id},
            )
            db.session.commit()
    return _envelhecer


@pytest.fixture
def html():
    return lambda resposta: resposta.data.decode()
