"""Correção de entradas e vendas pelo autor: prazo, justificativa, estorno e saldo."""
import re
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.extensions import db
from app.models import Product, Sale, StockCorrection, StockEntry, StockMovement
from app.timeutils import format_local

JUST = "Digitei o valor errado na hora do lançamento"


def corrigir_entrada(cliente, entrada_id, quantidade, justificativa=JUST):
    return cliente.post(f"/estoque/entrada/{entrada_id}/corrigir",
                        data={"quantity": str(quantidade), "justification": justificativa},
                        follow_redirects=True)


def corrigir_venda(cliente, venda_id, quantidade, justificativa=JUST):
    return cliente.post(f"/vendas/{venda_id}/corrigir",
                        data={"quantity": str(quantidade), "justification": justificativa},
                        follow_redirects=True)


@pytest.fixture
def contar(consulta):
    return lambda modelo: consulta(lambda: db.session.scalar(select(func.count(modelo.id))))


@pytest.fixture
def saldo(consulta):
    return lambda produto_id=1: consulta(lambda: db.session.get(Product, produto_id).quantity)


@pytest.fixture
def entrada_10(novo_produto):
    """Produto 1 com a entrada nº 1 de 10 unidades."""
    return novo_produto(estoque=10)


@pytest.fixture
def venda_de_3(novo_produto, vend):
    """Produto 1 com 20 unidades e a venda nº 1 de 3 unidades (R$ 8,50 cada) feita por `vend`."""
    produto_id = novo_produto(preco="8.50", estoque=20)
    vend.post("/vendas", data={"product_id": produto_id, "quantity": "3"})
    return produto_id


def sequencia_do_livro_razao(consulta, produto_id=1):
    return consulta(lambda: [
        (m.movement_type, m.quantity, m.balance_after)
        for m in db.session.scalars(
            select(StockMovement).where(StockMovement.product_id == produto_id).order_by(StockMovement.id))])


# ================================================================ entradas

@pytest.mark.parametrize("quantidade,justificativa,mensagem", [
    ("abc", JUST, "número inteiro"),
    ("-1", JUST, "negativa"),
    ("10", JUST, "igual à atual"),
    ("7", "curta", "mínimo de 10 caracteres"),
    ("7", "   ", "mínimo de 10 caracteres"),
])
def test_entrada_dados_invalidos_nao_alteram_nada(est, entrada_10, html, contar, saldo,
                                                  quantidade, justificativa, mensagem):
    resposta = corrigir_entrada(est, 1, quantidade, justificativa)
    assert mensagem in html(resposta)
    assert saldo() == 10
    assert contar(StockCorrection) == 0 and contar(StockEntry) == 1 and contar(StockMovement) == 1


def test_corrigir_entrada_preserva_o_original_e_registra_estorno(est, entrada_10, envelhecer, html, consulta, saldo):
    envelhecer("stock_entry", 1, 10)       # lançada há 10 min: a substituta tem de herdar ESTA data, não a de agora
    resposta = corrigir_entrada(est, 1, 7)
    assert "corrigida de 10 para 7" in html(resposta)
    assert saldo() == 7

    entradas = consulta(lambda: [(e.quantity, e.created_at) for e in db.session.scalars(select(StockEntry).order_by(StockEntry.id))])
    assert [q for q, _ in entradas] == [10, 7]
    assert entradas[0][1] == entradas[1][1]          # a substituta herda a data original
    assert sequencia_do_livro_razao(consulta) == [("entrada", 10, 10), ("entrada", 7, 17), ("estorno", -10, 7)]

    estorno_aponta_para_original = consulta(lambda: (
        lambda m: m[2].reverses_movement_id == m[0].id and m[2].stock_entry_id == 1)(
        db.session.scalars(select(StockMovement).order_by(StockMovement.id)).all()))
    assert estorno_aponta_para_original


def test_correcao_fica_registrada_com_autor_e_justificativa(est, entrada_10, consulta):
    corrigir_entrada(est, 1, 7)
    c = consulta(lambda: (lambda x: (x.kind, x.original_record_id, x.new_record_id, x.old_quantity,
                                     x.new_quantity, x.user.username, x.justification))(
        db.session.scalars(select(StockCorrection)).one()))
    assert c == ("entrada", 1, 2, 10, 7, "est", JUST)


def test_lista_mostra_situacao_e_justificativa(est, entrada_10, html):
    corrigir_entrada(est, 1, 7)
    pagina = html(est.get("/estoque"))
    assert "Substituída" in pagina and "Corrigida" in pagina and JUST in pagina


def test_entrada_anulada_nao_pode_ser_corrigida_de_novo(est, entrada_10, html, contar, saldo):
    corrigir_entrada(est, 1, 7)
    resposta = corrigir_entrada(est, 1, 5)
    assert "já foi corrigido" in html(resposta)
    assert saldo() == 7 and contar(StockCorrection) == 1


def test_substituta_pode_ser_corrigida_de_novo(est, entrada_10, html, saldo):
    corrigir_entrada(est, 1, 7)
    resposta = corrigir_entrada(est, 2, 8)
    assert "de 7 para 8" in html(resposta)
    assert saldo() == 8


def test_cancelar_entrada_com_quantidade_zero(est, entrada_10, html, consulta, saldo):
    resposta = corrigir_entrada(est, 1, 0)
    assert "cancelada" in html(resposta)
    assert saldo() == 0
    correcao = consulta(lambda: db.session.scalars(select(StockCorrection)).one())
    assert correcao.new_record_id is None and correcao.replacement_movement_id is None
    assert "Cancelada" in html(est.get("/estoque"))


# ---------------------------------------------------------------- prazo

def test_entrada_fora_do_prazo_nao_pode_ser_corrigida(est, entrada_10, envelhecer, html, saldo):
    envelhecer("stock_entry", 1, 31)
    resposta = corrigir_entrada(est, 1, 7)
    assert "prazo de 30 minutos" in html(resposta)
    assert saldo() == 10
    assert "/estoque/entrada/1/corrigir" not in html(est.get("/estoque"))


def test_entrada_dentro_do_prazo_pode_ser_corrigida(est, entrada_10, envelhecer, html, saldo):
    envelhecer("stock_entry", 1, 29)
    assert "/estoque/entrada/1/corrigir" in html(est.get("/estoque"))
    assert "de 10 para 7" in html(corrigir_entrada(est, 1, 7))
    assert saldo() == 7


def test_prazo_pode_ser_configurado(app, est, entrada_10, envelhecer, html):
    app.config["CORRECTION_WINDOW_MINUTES"] = 120
    envelhecer("stock_entry", 1, 90)
    assert "de 10 para 7" in html(corrigir_entrada(est, 1, 7))


# ---------------------------------------------------------------- quem pode

def test_outro_estoquista_nao_corrige_entrada_alheia(est2, entrada_10, html, saldo):
    assert "feitos por você" in html(corrigir_entrada(est2, 1, 7))
    assert saldo() == 10


@pytest.mark.parametrize("perfil", ["vend", "adm"])
def test_vendedor_e_admin_nao_corrigem_entradas(request, entrada_10, html, saldo, perfil):
    cliente = request.getfixturevalue(perfil)
    assert "não tem permissão" in html(cliente.get("/estoque/entrada/1/corrigir", follow_redirects=True))
    assert "não tem permissão" in html(corrigir_entrada(cliente, 1, 7))
    assert saldo() == 10


def test_entrada_inexistente(est, html):
    assert "não encontrada" in html(est.get("/estoque/entrada/9999/corrigir", follow_redirects=True))


# ---------------------------------------------------------------- saldo nunca negativo

def test_corrigir_entrada_que_deixaria_saldo_negativo_e_bloqueado(est, vend, entrada_10, html, saldo, contar):
    vend.post("/vendas", data={"product_id": "1", "quantity": "9"})      # sobra 1
    correcoes, movimentos = contar(StockCorrection), contar(StockMovement)
    resposta = corrigir_entrada(est, 1, 5)                                # 1 + (5 - 10) = -4
    assert "negativo" in html(resposta)
    assert saldo() == 1
    assert (contar(StockCorrection), contar(StockMovement)) == (correcoes, movimentos)


def test_corrigir_entrada_deixando_saldo_exatamente_zero_e_permitido(est, vend, entrada_10, html, saldo, consulta):
    vend.post("/vendas", data={"product_id": "1", "quantity": "9"})      # sobra 1
    assert "de 10 para 9" in html(corrigir_entrada(est, 1, 9))            # 1 + (9 - 10) = 0
    assert saldo() == 0
    assert consulta(lambda: db.session.scalar(select(func.min(StockMovement.balance_after)))) >= 0


# ================================================================ vendas

def test_corrigir_venda_mantem_preco_e_ajusta_estoque(vend, venda_de_3, envelhecer, html, consulta, saldo):
    assert saldo() == 17
    envelhecer("sale", 1, 10)               # vendida há 10 min: a substituta tem de herdar esta data

    def reajustar_preco_do_produto():       # o preço do cadastro muda depois da venda
        db.session.get(Product, 1).unit_price = Decimal("12.00")
        db.session.commit()
    consulta(reajustar_preco_do_produto)

    assert "de 3 para 5" in html(corrigir_venda(vend, 1, 5))
    assert saldo() == 15
    original, nova = consulta(lambda: [
        (s.quantity, float(s.unit_price), float(s.total), s.created_at, s.user_id)
        for s in db.session.scalars(select(Sale).order_by(Sale.id))])
    assert original[:3] == (3, 8.5, 25.5)                                 # original intacta
    assert nova[:3] == (5, 8.5, 42.5)                                     # preço da época (não os R$ 12,00 atuais)
    assert nova[3] == original[3] and nova[4] == original[4]              # mesma data e vendedor


def test_estorno_de_venda_devolve_estoque_e_aponta_para_original(vend, venda_de_3, consulta):
    corrigir_venda(vend, 1, 5)
    movimentos = consulta(lambda: [
        (m.movement_type, m.quantity, m.sale_id, m.reverses_movement_id, m.id)
        for m in db.session.scalars(select(StockMovement).where(StockMovement.sale_id == 1).order_by(StockMovement.id))])
    assert [(t, q) for t, q, *_ in movimentos] == [("venda", -3), ("estorno", 3)]
    assert movimentos[1][3] == movimentos[0][4]


def test_cancelar_venda_devolve_o_estoque(vend, venda_de_3, html, saldo):
    assert "cancelada" in html(corrigir_venda(vend, 1, 0))
    assert saldo() == 20


def test_aumentar_venda_alem_do_estoque_e_bloqueado(vend, venda_de_3, html, saldo):
    resposta = corrigir_venda(vend, 1, 25)       # 17 + 3 - 25 < 0
    assert "insuficiente" in html(resposta)
    assert saldo() == 17


def test_outro_vendedor_nao_corrige_venda_alheia(vend2, venda_de_3, html, saldo):
    assert "feitos por você" in html(corrigir_venda(vend2, 1, 2))
    assert saldo() == 17


@pytest.mark.parametrize("perfil", ["est", "adm"])
def test_estoquista_e_admin_nao_corrigem_vendas(request, venda_de_3, html, perfil):
    cliente = request.getfixturevalue(perfil)
    assert "não tem permissão" in html(cliente.get("/vendas/1/corrigir", follow_redirects=True))


def test_venda_fora_do_prazo_nao_pode_ser_corrigida(vend, venda_de_3, envelhecer, html):
    envelhecer("sale", 1, 31)
    assert "prazo de 30 minutos" in html(corrigir_venda(vend, 1, 1))


def test_venda_anulada_nao_pode_ser_corrigida_de_novo(vend, venda_de_3, html):
    corrigir_venda(vend, 1, 5)
    assert "já foi corrigido" in html(corrigir_venda(vend, 1, 1))


def test_lista_de_vendas_mostra_situacoes_e_admin_nao_ve_botao(vend, adm, venda_de_3, html):
    corrigir_venda(vend, 1, 5)
    corrigir_venda(vend, 2, 0)
    pagina = html(vend.get("/vendas"))
    assert "Substituída" in pagina and "Cancelada" in pagina
    pagina_admin = html(adm.get("/vendas"))
    assert "Cancelada" in pagina_admin and "/corrigir" not in pagina_admin


# ---------------------------------------------------------------- números oficiais ignoram anuladas

def numeros_do_relatorio(adm):
    pagina = adm.get("/relatorios/vendas").data.decode()
    vendas = int(re.search(r"Vendas realizadas</h3>\s*<p>(\d+)</p>", pagina).group(1))
    unidades = int(re.search(r"Unidades vendidas</h3>\s*<p>(\d+)</p>", pagina).group(1))
    faturamento = float(re.search(r"Faturamento total</h3>\s*<p>\s*R\$ ([\d.]+)", pagina).group(1))
    return vendas, unidades, faturamento


def test_dashboard_e_relatorio_ignoram_vendas_anuladas(vend, adm, novo_produto, html):
    novo_produto(preco="8.50", estoque=50)
    vend.post("/vendas", data={"product_id": "1", "quantity": "9"})     # R$ 76,50
    vend.post("/vendas", data={"product_id": "1", "quantity": "3"})     # R$ 25,50 -> será corrigida
    corrigir_venda(vend, 2, 5)                                          # vira R$ 42,50
    assert numeros_do_relatorio(adm) == (2, 14, 119.0)
    painel = html(adm.get("/dashboard"))
    assert "R$ 119.00" in painel
    assert vendas_registradas_no_painel(painel) == 2
    assert "R$ 25.50" not in painel                                     # a venda anulada não aparece nem em "recentes"

    corrigir_venda(vend, 3, 0)                                          # cancela a corrigida
    assert numeros_do_relatorio(adm) == (1, 9, 76.5)
    painel = html(adm.get("/dashboard"))
    assert "R$ 76.50" in painel
    assert vendas_registradas_no_painel(painel) == 1
    assert "R$ 42.50" not in painel


def vendas_registradas_no_painel(pagina):
    return int(re.search(r"Vendas registradas</span><strong>(\d+)</strong>", pagina).group(1))


def test_ultima_entrada_do_dashboard_ignora_entrada_cancelada(est, adm, entrada_10, envelhecer, consulta, html):
    est.post("/estoque/entrada", data={"product_id": "1", "quantity": "5"})        # entrada nº 2, mais recente
    envelhecer("stock_entry", 1, 120)
    envelhecer("stock_entry", 2, 5)
    mais_antiga = consulta(lambda: format_local(db.session.get(StockEntry, 1).created_at))
    mais_nova = consulta(lambda: format_local(db.session.get(StockEntry, 2).created_at))
    assert mais_nova in html(adm.get("/dashboard"))

    corrigir_entrada(est, 2, 0)                                                     # cancela a mais recente
    painel = html(adm.get("/dashboard"))
    assert mais_antiga in painel and mais_nova not in painel


def test_livro_razao_mostra_estornos_com_justificativa(est, adm, entrada_10, html):
    corrigir_entrada(est, 1, 7)
    pagina = html(adm.get("/movimentacoes"))
    assert "Estorno" in pagina and f"Justificativa: {JUST}" in pagina
    assert "encontradas: 1" in html(adm.get("/movimentacoes?tipo=estorno"))


# ================================================================ coerência geral

def test_cadeia_do_livro_razao_continua_correta_apos_varias_operacoes(est, vend, novo_produto, consulta):
    novo_produto(estoque=10)
    corrigir_entrada(est, 1, 7)
    est.post("/estoque/entrada", data={"product_id": "1", "quantity": "5"})
    vend.post("/vendas", data={"product_id": "1", "quantity": "4"})
    corrigir_venda(vend, 1, 2)
    corrigir_entrada(est, 3, 0)

    def verificar():
        produto = db.session.get(Product, 1)
        linhas = db.session.scalars(select(StockMovement).where(StockMovement.product_id == 1)
                                    .order_by(StockMovement.id)).all()
        assert linhas[0].balance_before == 0
        for anterior, atual in zip(linhas, linhas[1:]):
            assert atual.balance_before == anterior.balance_after
        assert all(m.balance_after - m.balance_before == m.quantity for m in linhas)
        assert all(m.balance_after >= 0 for m in linhas)
        assert linhas[-1].balance_after == produto.quantity == sum(m.quantity for m in linhas)
        assert all(c.estorno_movement.movement_type == "estorno"
                   and c.estorno_movement.justification == c.justification
                   for c in db.session.scalars(select(StockCorrection)))
    consulta(verificar)
