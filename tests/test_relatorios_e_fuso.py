"""Relatório de vendas e fuso horário (o banco guarda UTC; a tela e os filtros usam Brasília)."""
import re
from datetime import date, datetime

import pytest
from sqlalchemy import text

from app.extensions import db
from app.timeutils import format_local, local_day_end_utc, local_day_start_utc


# ---------------------------------------------------------------- funções de fuso

def test_formata_utc_como_horario_de_brasilia(app):
    with app.app_context():
        assert format_local(datetime(2026, 11, 5, 1, 30, 0)) == "04/11/2026 22:30:00"
        assert format_local(datetime(2026, 11, 4, 15, 0, 0), "%d/%m/%Y %H:%M") == "04/11/2026 12:00"
        assert format_local(None) == ""


def test_limites_do_dia_local_em_utc(app):
    with app.app_context():
        assert local_day_start_utc(date(2026, 11, 4)) == datetime(2026, 11, 4, 3, 0, 0)
        assert local_day_end_utc(date(2026, 11, 4)) == datetime(2026, 11, 5, 2, 59, 59, 999999)


# ---------------------------------------------------------------- telas e filtros

@pytest.fixture
def vendas_nas_bordas(app):
    """Três vendas perto da virada do dia (usuários: vend=2, est=4).

    A: 04/11 22:30 local (= 05/11 01:30 UTC)   B: 03/11 23:30 local (= 04/11 02:30 UTC)
    C: 04/11 00:05 local (= 04/11 03:05 UTC)
    """
    comandos = [
        "INSERT INTO product(id,name,category,quantity,unit_price) VALUES (1,'Cupcake','Cupcake',44,10.00)",
        "INSERT INTO sale(id,product_id,quantity,unit_price,total,created_at,user_id) VALUES "
        "(1,1,1,10,10,'2026-11-05 01:30:00',2),(2,1,2,10,20,'2026-11-04 02:30:00',2),(3,1,3,10,30,'2026-11-04 03:05:00',2)",
        "INSERT INTO stock_entry(id,product_id,quantity,created_at,user_id) VALUES (1,1,50,'2026-11-05 01:30:00',4)",
        "INSERT INTO stock_movement(product_id,movement_type,quantity,balance_before,balance_after,user_id,stock_entry_id,created_at) "
        "VALUES (1,'entrada',50,0,50,4,1,'2026-11-05 01:30:00')",
        "INSERT INTO stock_movement(product_id,movement_type,quantity,balance_before,balance_after,user_id,sale_id,created_at) "
        "VALUES (1,'venda',-1,50,49,2,1,'2026-11-05 01:30:00'),(1,'venda',-2,49,47,2,2,'2026-11-04 02:30:00'),"
        "(1,'venda',-3,47,44,2,3,'2026-11-04 03:05:00')",
    ]
    with app.app_context():
        for comando in comandos:
            db.session.execute(text(comando))
        db.session.commit()


@pytest.mark.parametrize("cliente,rota", [
    ("adm", "/dashboard"), ("adm", "/movimentacoes"), ("adm", "/relatorios/vendas"),
    ("vend", "/vendas"), ("est", "/estoque"),
])
def test_telas_mostram_horario_de_brasilia(request, vendas_nas_bordas, html, cliente, rota):
    pagina = html(request.getfixturevalue(cliente).get(rota))
    assert "04/11/2026 22:30" in pagina
    assert "05/11/2026 01:30" not in pagina


def numeros_do_relatorio(adm, **filtros):
    pagina = adm.get("/relatorios/vendas", query_string=filtros).data.decode()
    vendas = int(re.search(r"Vendas realizadas</h3>\s*<p>(\d+)</p>", pagina).group(1))
    faturamento = float(re.search(r"Faturamento total</h3>\s*<p>\s*R\$ ([\d.]+)", pagina).group(1))
    return vendas, faturamento


@pytest.mark.parametrize("inicial,final,vendas,faturamento", [
    ("2026-11-04", "2026-11-04", 2, 40.0),     # A e C: B foi no dia 03 local
    ("2026-11-03", "2026-11-03", 1, 20.0),     # só B
    ("2026-11-05", "2026-11-05", 0, 0.0),      # A foi 22h30 do dia 04 local, não do 05
    ("2026-11-03", "2026-11-04", 3, 60.0),
])
def test_relatorio_filtra_pelo_dia_local(adm, vendas_nas_bordas, inicial, final, vendas, faturamento):
    assert numeros_do_relatorio(adm, data_inicial=inicial, data_final=final) == (vendas, faturamento)


def test_relatorio_so_com_data_inicial_ou_so_final(adm, vendas_nas_bordas):
    assert numeros_do_relatorio(adm, data_inicial="2026-11-04") == (2, 40.0)
    assert numeros_do_relatorio(adm, data_final="2026-11-03") == (1, 20.0)


@pytest.mark.parametrize("inicio,fim,tipo,esperado", [
    ("2026-11-04", "2026-11-04", None, 3),      # entrada + venda A + venda C
    ("2026-11-03", "2026-11-03", None, 1),      # venda B
    ("2026-11-05", "2026-11-05", None, 0),
    ("2026-11-04", "2026-11-04", "venda", 2),
])
def test_movimentacoes_filtra_pelo_dia_local(adm, vendas_nas_bordas, html, inicio, fim, tipo, esperado):
    parametros = {"inicio": inicio, "fim": fim, **({"tipo": tipo} if tipo else {})}
    pagina = html(adm.get("/movimentacoes", query_string=parametros))
    assert int(re.search(r"encontradas: (\d+)", pagina).group(1)) == esperado


# ---------------------------------------------------------------- relatório de vendas

def test_relatorio_periodo_invertido_e_invalido(adm, html):
    resposta = adm.get("/relatorios/vendas?data_inicial=2026-11-05&data_final=2026-11-01", follow_redirects=True)
    assert "período válido" in html(resposta)


def test_relatorio_filtra_por_vendedor_e_produto(adm, vend, vend2, novo_produto):
    novo_produto(nome="Cupcake", preco="10.00", estoque=30)
    novo_produto(nome="Brigadeiro", preco="3.00", estoque=30)
    vend.post("/vendas", data={"product_id": "1", "quantity": "2"})     # R$ 20
    vend2.post("/vendas", data={"product_id": "1", "quantity": "1"})    # R$ 10
    vend2.post("/vendas", data={"product_id": "2", "quantity": "4"})    # R$ 12
    assert numeros_do_relatorio(adm) == (3, 42.0)
    assert numeros_do_relatorio(adm, vendedor_id="3") == (2, 22.0)      # vend2 tem id 3
    assert numeros_do_relatorio(adm, produto_id="1") == (2, 30.0)
    assert numeros_do_relatorio(adm, produto_id="2", vendedor_id="2") == (0, 0.0)


def test_relatorio_so_para_admin(vend, est, html):
    for cliente in (vend, est):
        assert "não tem permissão" in html(cliente.get("/relatorios/vendas", follow_redirects=True))
