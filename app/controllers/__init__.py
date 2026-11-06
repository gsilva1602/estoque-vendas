def register_blueprints(app):
    from . import auth, dashboard, estoque, movimentacoes, relatorios, usuarios, vendas

    for module in (auth, dashboard, estoque, vendas, usuarios, movimentacoes, relatorios):
        app.register_blueprint(module.bp)
