"""Cadastro de produto, entradas, vendas e usuários, incluindo os registros no livro-razão."""
from sqlalchemy import func, select

from app.extensions import db
from app.models import Product, Sale, StockEntry, StockMovement, User


# ---------------------------------------------------------------- produtos

def test_cadastrar_produto_aceita_virgula_no_preco(est, consulta):
    resposta = est.post("/estoque", data={"name": "Cupcake Chocolate", "category": "Cupcake", "unit_price": "8,50"})
    assert resposta.status_code == 302
    nome, quantidade, preco = consulta(
        lambda: db.session.execute(select(Product.name, Product.quantity, Product.unit_price)).one())
    assert (nome, quantidade, float(preco)) == ("Cupcake Chocolate", 0, 8.5)


def test_cadastrar_produto_invalido_mostra_erro(est, html, consulta):
    resposta = est.post("/estoque", data={"name": "", "category": "x", "unit_price": "1"}, follow_redirects=True)
    assert "preço válido" in html(resposta)
    assert consulta(lambda: db.session.scalar(select(func.count(Product.id)))) == 0


def test_categoria_existente_e_sugerida_no_cadastro(est, novo_produto, html):
    novo_produto(nome="Produto existente", preco="1", estoque=0)

    conteudo = html(est.get("/estoque"))

    assert 'list="product-categories"' in conteudo
    assert '<option value="Cupcake">' in conteudo


def test_cadastrar_produto_aceita_categoria_nova(est, consulta):
    resposta = est.post(
        "/estoque",
        data={
            "name": "Novo produto",
            "category": "Categoria personalizada",
            "unit_price": "2.50",
        },
    )

    assert resposta.status_code == 302
    assert consulta(
        lambda: db.session.scalar(
            select(Product.category).where(Product.name == "Novo produto")
        )
    ) == "Categoria personalizada"


# ---------------------------------------------------------------- entradas

def test_entrada_soma_ao_saldo_e_grava_movimento(est, novo_produto, html, consulta):
    produto_id = novo_produto()
    resposta = est.post("/estoque/entrada", data={"product_id": produto_id, "quantity": "10"}, follow_redirects=True)
    assert "+10 unidade" in html(resposta)
    saldo = consulta(lambda: db.session.get(Product, produto_id).quantity)
    movimento = consulta(lambda: db.session.execute(
        select(StockMovement.movement_type, StockMovement.quantity,
               StockMovement.balance_before, StockMovement.balance_after)).one())
    assert saldo == 10
    assert tuple(movimento) == ("entrada", 10, 0, 10)


def test_entrada_invalida_e_recusada(est, novo_produto, html, consulta):
    produto_id = novo_produto()
    for quantidade in ("0", "-3", "abc", ""):
        resposta = est.post("/estoque/entrada", data={"product_id": produto_id, "quantity": quantidade},
                            follow_redirects=True)
        assert "maior que zero" in html(resposta)
    assert consulta(lambda: db.session.get(Product, produto_id).quantity) == 0
    assert consulta(lambda: db.session.scalar(select(func.count(StockMovement.id)))) == 0


def test_somente_estoquista_registra_entrada(vend, adm, novo_produto, html):
    produto_id = novo_produto()
    for cliente in (vend, adm):
        resposta = cliente.post("/estoque/entrada", data={"product_id": produto_id, "quantity": "5"},
                                follow_redirects=True)
        assert "não tem permissão" in html(resposta)


# ---------------------------------------------------------------- vendas

def test_venda_baixa_estoque_e_calcula_total(vend, novo_produto, html, consulta):
    produto_id = novo_produto(preco="8.50", estoque=10)
    resposta = vend.post("/vendas", data={"product_id": produto_id, "quantity": "3"}, follow_redirects=True)
    assert "Venda registrada" in html(resposta)
    assert consulta(lambda: db.session.get(Product, produto_id).quantity) == 7
    quantidade, total = consulta(lambda: db.session.execute(select(Sale.quantity, Sale.total)).one())
    assert (quantidade, float(total)) == (3, 25.5)


def test_venda_grava_movimento_com_saldos_e_responsavel(vend, novo_produto, consulta):
    produto_id = novo_produto(estoque=10)
    vend.post("/vendas", data={"product_id": produto_id, "quantity": "4"})
    tipo, delta, antes, depois, usuario = consulta(lambda: db.session.execute(
        select(StockMovement.movement_type, StockMovement.quantity, StockMovement.balance_before,
               StockMovement.balance_after, User.username)
        .join(User, StockMovement.user_id == User.id)
        .order_by(StockMovement.id.desc())).first())
    assert (tipo, delta, antes, depois, usuario) == ("venda", -4, 10, 6, "vend")


def test_venda_acima_do_estoque_e_recusada_sem_gravar_nada(vend, novo_produto, html, consulta):
    produto_id = novo_produto(estoque=5)
    movimentos_antes = consulta(lambda: db.session.scalar(select(func.count(StockMovement.id))))
    resposta = vend.post("/vendas", data={"product_id": produto_id, "quantity": "999"}, follow_redirects=True)
    assert "Estoque insuficiente" in html(resposta)
    assert consulta(lambda: db.session.get(Product, produto_id).quantity) == 5
    assert consulta(lambda: db.session.scalar(select(func.count(Sale.id)))) == 0
    assert consulta(lambda: db.session.scalar(select(func.count(StockMovement.id)))) == movimentos_antes


def test_venda_com_quantidade_invalida_e_recusada(vend, novo_produto, html):
    produto_id = novo_produto(estoque=5)
    for quantidade in ("0", "-1", "x"):
        resposta = vend.post("/vendas", data={"product_id": produto_id, "quantity": quantidade},
                             follow_redirects=True)
        assert "maior que zero" in html(resposta)


def test_admin_nao_registra_venda(adm, novo_produto, html):
    produto_id = novo_produto(estoque=5)
    resposta = adm.post("/vendas", data={"product_id": produto_id, "quantity": "1"}, follow_redirects=True)
    assert "Somente vendedores" in html(resposta)


def test_vendedor_ve_apenas_as_proprias_vendas(vend, vend2, novo_produto, html):
    produto_id = novo_produto(estoque=10)
    vend.post("/vendas", data={"product_id": produto_id, "quantity": "2"})
    assert "Minhas vendas" in html(vend.get("/vendas"))
    assert "Nenhuma venda registrada" in html(vend2.get("/vendas"))


# ---------------------------------------------------------------- usuários

def test_admin_cria_usuario(adm, html, consulta):
    resposta = adm.post("/usuarios", data={"username": "novo", "password": "12345678", "role": "vendedor"},
                        follow_redirects=True)
    assert "criado" in html(resposta)
    assert consulta(lambda: db.session.scalar(select(User.role).where(User.username == "novo"))) == "vendedor"


def test_usuario_duplicado_senha_curta_e_perfil_invalido(adm, html):
    assert "já existe" in html(adm.post(
        "/usuarios", data={"username": "adm", "password": "12345678", "role": "admin"}, follow_redirects=True))
    for dados in ({"username": "x", "password": "123", "role": "admin"},
                  {"username": "x", "password": "12345678", "role": "chefe"}):
        assert "senha com pelo menos 8" in html(adm.post("/usuarios", data=dados, follow_redirects=True))


def test_senha_fica_armazenada_com_hash(consulta):
    senha_hash = consulta(lambda: db.session.scalar(select(User.password_hash).where(User.username == "adm")))
    assert senha_hash != "senha12345"
    assert senha_hash.startswith(("scrypt:", "pbkdf2:"))


def test_entradas_aparecem_no_historico_do_estoque(est, novo_produto, html):
    novo_produto(estoque=7)
    assert "+7" in html(est.get("/estoque"))
    assert est.get("/estoque").status_code == 200


def test_total_de_entradas_e_vendas_confere(vend, novo_produto, consulta):
    produto_id = novo_produto(estoque=20)
    vend.post("/vendas", data={"product_id": produto_id, "quantity": "6"})
    entradas = consulta(lambda: db.session.scalar(select(func.sum(StockEntry.quantity))))
    vendas = consulta(lambda: db.session.scalar(select(func.sum(Sale.quantity))))
    assert entradas - vendas == consulta(lambda: db.session.get(Product, produto_id).quantity)
