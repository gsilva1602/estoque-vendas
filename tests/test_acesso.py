"""Login, redirecionamentos e permissões por perfil (admin, vendedor, estoquista)."""
import pytest

ROTAS = ["/dashboard", "/estoque", "/vendas", "/movimentacoes", "/usuarios", "/relatorios/vendas"]

PERMITIDAS = [
    ("adm", "/dashboard"), ("adm", "/vendas"), ("adm", "/movimentacoes"),
    ("adm", "/relatorios/vendas"), ("adm", "/usuarios"),
    ("vend", "/vendas"),
    ("est", "/estoque"), ("est", "/movimentacoes"),
]

NEGADAS = [
    ("vend", "/estoque"), ("vend", "/movimentacoes"), ("vend", "/usuarios"), ("vend", "/relatorios/vendas"),
    ("est", "/vendas"), ("est", "/usuarios"), ("est", "/relatorios/vendas"),
]


@pytest.mark.parametrize("rota", ROTAS)
def test_visitante_e_enviado_para_o_login(app, rota):
    resposta = app.test_client().get(rota)
    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]


def test_login_com_senha_errada_mostra_erro(app, html):
    resposta = app.test_client().post("/login", data={"username": "adm", "password": "errada"})
    assert "Usuário ou senha inválidos" in html(resposta)


def test_login_correto_leva_ao_dashboard(app):
    resposta = app.test_client().post("/login", data={"username": "adm", "password": "senha12345"})
    assert resposta.status_code == 302
    assert resposta.headers["Location"].endswith("/dashboard")


@pytest.mark.parametrize("usuario,destino", [("vend", "/vendas"), ("est", "/estoque")])
def test_dashboard_redireciona_vendedor_e_estoquista(request, usuario, destino):
    resposta = request.getfixturevalue(usuario).get("/dashboard")
    assert resposta.status_code == 302
    assert resposta.headers["Location"].endswith(destino)


@pytest.mark.parametrize("usuario,rota", PERMITIDAS)
def test_perfil_acessa_o_que_lhe_cabe(request, usuario, rota):
    assert request.getfixturevalue(usuario).get(rota).status_code == 200


@pytest.mark.parametrize("usuario,rota", NEGADAS)
def test_perfil_nao_acessa_area_de_outro(request, html, usuario, rota):
    resposta = request.getfixturevalue(usuario).get(rota, follow_redirects=True)
    assert "não tem permissão" in html(resposta)


def test_admin_consulta_estoque_pelo_dashboard(adm):
    resposta = adm.get("/estoque")
    assert resposta.status_code == 302
    assert resposta.headers["Location"].endswith("/dashboard")


def test_logout_encerra_a_sessao(adm):
    resposta = adm.post("/logout")
    assert resposta.status_code == 302
    assert adm.get("/dashboard").status_code == 302
