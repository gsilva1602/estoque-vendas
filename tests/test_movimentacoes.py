"""Tela de movimentações (livro-razão) e comando de carga do histórico antigo."""
import re

import pytest
from sqlalchemy import func, inspect, select, text

from app.extensions import db
from app.models import StockMovement


def total_de_linhas(pagina):
    return int(re.search(r"encontradas: (\d+)", pagina).group(1))


# ---------------------------------------------------------------- tela

@pytest.fixture
def historico(vend, novo_produto):
    """Produto com entrada de 10 e venda de 4: o livro-razão fica com 2 linhas."""
    produto_id = novo_produto(estoque=10)
    vend.post("/vendas", data={"product_id": produto_id, "quantity": "4"})
    return produto_id


def test_tela_mostra_saldo_antes_e_depois(adm, historico, html):
    pagina = html(adm.get("/movimentacoes"))
    assert "0 → 10" in pagina
    assert "10 → 6" in pagina
    assert total_de_linhas(pagina) == 2


def test_estoquista_tambem_consulta(est, historico):
    assert est.get("/movimentacoes").status_code == 200


@pytest.mark.parametrize("tipo,esperado", [("entrada", 1), ("venda", 1), ("estorno", 0), ("ajuste", 0)])
def test_filtro_por_tipo(adm, historico, html, tipo, esperado):
    assert total_de_linhas(html(adm.get("/movimentacoes", query_string={"tipo": tipo}))) == esperado


def test_filtro_por_produto(adm, historico, novo_produto, html):
    outro = novo_produto(nome="Brigadeiro", estoque=3)
    assert total_de_linhas(html(adm.get("/movimentacoes", query_string={"produto": outro}))) == 1
    assert total_de_linhas(html(adm.get("/movimentacoes", query_string={"produto": historico}))) == 2


def test_data_invalida_e_tratada(adm, html):
    assert "Data inicial inválida" in html(adm.get("/movimentacoes?inicio=xx", follow_redirects=True))
    assert "Data final inválida" in html(adm.get("/movimentacoes?fim=xx", follow_redirects=True))


# ---------------------------------------------------------------- carga do histórico (backfill)

@pytest.fixture
def app_antigo(criar_app):
    """Banco como era antes do livro-razão: sem as tabelas novas e com dados inseridos direto.

    Usuários: adm=1, vend=2, vend2=3, est=4, est2=5.
    Produto 1 fecha com o histórico (20). Produto 2 diverge (histórico 12, saldo 20).
    Produto 3 não tem nada. Produto 4 tem saldo 5 sem nenhum histórico.
    """
    app = criar_app("antigo.db", tabelas=["user", "product", "stock_entry", "sale"])
    comandos = [
        "INSERT INTO product(id,name,category,quantity,unit_price) VALUES "
        "(1,'Cupcake Chocolate','Cupcake',20,8.50),(2,'Cupcake Morango','Cupcake',20,9.00),"
        "(3,'Brigadeiro','Doce',0,3.00),(4,'Cookie','Biscoito',5,6.00)",
        "INSERT INTO stock_entry(product_id,quantity,created_at,user_id) VALUES "
        "(1,10,'2026-10-01 10:00:00',4),(1,20,'2026-10-03 09:00:00',4),(2,15,'2026-10-01 10:00:00',4)",
        "INSERT INTO sale(product_id,quantity,unit_price,total,created_at,user_id) VALUES "
        "(1,4,8.50,34.00,'2026-10-02 11:00:00',2),(1,6,8.50,51.00,'2026-10-03 09:00:00',2),"
        "(2,3,9.00,27.00,'2026-10-01 15:00:00',2)",
    ]
    with app.app_context():
        for comando in comandos:
            db.session.execute(text(comando))
        db.session.commit()
    return app


def executar(app, *argumentos):
    return app.test_cli_runner().invoke(args=list(argumentos))


def movimentos(app, produto_id=None):
    with app.app_context():
        consulta = select(StockMovement.movement_type, StockMovement.quantity, StockMovement.balance_after,
                          StockMovement.user_id).order_by(StockMovement.id)
        if produto_id:
            consulta = consulta.where(StockMovement.product_id == produto_id)
        return [tuple(linha) for linha in db.session.execute(consulta)]


def test_init_db_cria_so_as_tabelas_novas_e_preserva_os_dados(app_antigo):
    with app_antigo.app_context():
        antes = {t: db.session.scalar(text(f"select count(*) from {t}")) for t in ("user", "product", "stock_entry", "sale")}
    assert executar(app_antigo, "init-db").exit_code == 0
    with app_antigo.app_context():
        tabelas = inspect(db.engine).get_table_names()
        depois = {t: db.session.scalar(text(f"select count(*) from {t}")) for t in antes}
    assert "stock_movement" in tabelas and "stock_correction" in tabelas
    assert antes == depois


def test_dry_run_mostra_divergencias_sem_gravar(app_antigo):
    executar(app_antigo, "init-db")
    resultado = executar(app_antigo, "backfill-movements", "--dry-run")
    assert resultado.exit_code == 0
    assert "DIVERGÊNCIA" in resultado.output and "dry-run" in resultado.output
    assert movimentos(app_antigo) == []


def test_carga_ordena_por_data_e_poe_entrada_antes_da_venda_no_empate(app_antigo):
    executar(app_antigo, "init-db")
    assert executar(app_antigo, "backfill-movements").exit_code == 0
    sequencia = [(tipo, delta, saldo) for tipo, delta, saldo, _ in movimentos(app_antigo, 1)]
    assert sequencia == [("entrada", 10, 10), ("venda", -4, 6), ("entrada", 20, 26), ("venda", -6, 20)]


def test_carga_cria_ajuste_do_sistema_quando_historico_diverge(app_antigo):
    executar(app_antigo, "init-db")
    executar(app_antigo, "backfill-movements")
    ajustes = [(delta, saldo, usuario) for tipo, delta, saldo, usuario in movimentos(app_antigo) if tipo == "ajuste"]
    assert sorted(ajustes) == [(5, 5, None), (8, 20, None)]


def test_carga_e_idempotente(app_antigo):
    executar(app_antigo, "init-db")
    executar(app_antigo, "backfill-movements")
    total = len(movimentos(app_antigo))
    resultado = executar(app_antigo, "backfill-movements")
    assert "pulado" in resultado.output
    assert len(movimentos(app_antigo)) == total == 8


def test_saldo_final_do_livro_razao_confere_com_cada_produto(app_antigo):
    executar(app_antigo, "init-db")
    executar(app_antigo, "backfill-movements")
    with app_antigo.app_context():
        for produto_id, saldo in db.session.execute(text("select id, quantity from product")):
            linhas = movimentos(app_antigo, produto_id)
            assert (linhas[-1][2] if linhas else 0) == saldo


def test_novas_operacoes_continuam_a_cadeia_apos_a_carga(app_antigo, login):
    executar(app_antigo, "init-db")
    executar(app_antigo, "backfill-movements")
    cliente = app_antigo.test_client()
    cliente.post("/login", data={"username": "est", "password": "senha12345"})
    cliente.post("/estoque/entrada", data={"product_id": "1", "quantity": "5"})
    with app_antigo.app_context():
        ultimo = db.session.execute(
            select(StockMovement.balance_before, StockMovement.balance_after)
            .where(StockMovement.product_id == 1).order_by(StockMovement.id.desc())).first()
    assert tuple(ultimo) == (20, 25)
