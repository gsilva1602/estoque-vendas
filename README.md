# Controle de Estoque e Vendas

Aplicação web acadêmica para cadastro de produtos, controle de entradas e vendas, histórico de movimentações e relatórios. Foi desenvolvida com Python, Flask e SQLAlchemy; pode usar SQLite localmente e PostgreSQL na hospedagem.

## Perfis

- **Administrador:** consulta o painel, relatórios e gerencia usuários.
- **Vendedor:** registra vendas e consulta as próprias vendas.
- **Estoquista:** cadastra produtos, registra entradas e consulta movimentações.

As permissões também são validadas no servidor.

## Inicialização local (Windows / PowerShell)

Requisitos: Python 3.11 ou superior e Git.

1. Clone o repositório e entre na pasta:

   ```powershell
   git clone https://github.com/gsilva1602/estoque-vendas.git
   cd estoque-vendas
   ```

2. Crie e ative um ambiente virtual e instale as dependências:

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

3. Crie as tabelas e cadastre usuários. O comando pede nome, senha (mínimo de 8 caracteres) e perfil:

   ```powershell
   flask --app app init-db
   flask --app app create-user
   ```

   Execute `create-user` novamente para cadastrar outros perfis, se necessário. Crie pelo menos um administrador.

4. Inicie o servidor local:

   ```powershell
   flask --app app run --debug
   ```

5. Acesse <http://127.0.0.1:5000> e entre com o usuário criado.

Por padrão, a execução local usa SQLite em `instance/estoque.db`, que é criado quando necessário. Esse banco local é independente do banco Neon usado pelo site publicado.

## Usar PostgreSQL/Neon localmente

Para apontar a cópia local da aplicação ao PostgreSQL, crie um arquivo `.env.local` na raiz do projeto com as variáveis abaixo e os valores de conexão exibidos no painel Neon:

```dotenv
DATABASE_URL=postgresql://USUARIO:SENHA@HOST-POOLER/BASE?sslmode=require
DATABASE_URL_UNPOOLED=postgresql://USUARIO:SENHA@HOST/BASE?sslmode=require
SECRET_KEY=uma-chave-local-aleatoria
```

Use a URL **pooled** em `DATABASE_URL` para as requisições da aplicação e a URL **direct/unpooled** em `DATABASE_URL_UNPOOLED` para operações de migração. Não use URLs do console web ou da Data API. O app carrega `.env.local` automaticamente; variáveis já definidas no ambiente têm precedência. Esse arquivo é ignorado pelo Git: nunca publique credenciais.

Para inicializar um banco Neon novo, configure temporariamente `DATABASE_URL` com a URL direct e execute `flask --app app init-db` e `flask --app app create-user`. Depois, use a pooled `DATABASE_URL` para rodar a aplicação. `init-db` cria tabelas ausentes, mas não atualiza tabelas existentes nem transfere dados.

### Importar dados de um SQLite existente

Faça um backup do arquivo SQLite. Configure `DATABASE_URL` para PostgreSQL e, de preferência, `DATABASE_URL_UNPOOLED` para a URL direct da Neon. Em seguida:

```powershell
flask --app app migrate-sqlite
```

O comando importa por padrão `instance/estoque.db`; use `--source caminho\para\outro.db` para outro arquivo. O destino deve estar vazio nas tabelas da aplicação. Os dados e IDs são preservados e as sequências do PostgreSQL são atualizadas. Não execute esse comando contra o Neon do site se ele já contém os dados: a importação não sobrescreve tabelas que já tenham registros. O SQLite precisa ter as tabelas e colunas da versão atual do app.

## Testes

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

## Publicação (Render + Neon)

O arquivo `render.yaml` configura o serviço web do Render. Para criar ou conectar o serviço:

1. Crie um banco PostgreSQL na Neon e copie as URLs pooled e direct.
2. No Render, conecte este repositório e crie/sincronize o Blueprint usando `render.yaml` e a branch `main`.
3. Configure `DATABASE_URL` com a URL pooled e `DATABASE_URL_UNPOOLED` com a URL direct da Neon. Deixe o Render gerar `SECRET_KEY`.
4. Para um banco Neon novo, inicialize as tabelas e crie o primeiro usuário usando os comandos Flask localmente com a URL direct. Não é necessário repetir isso se o banco já foi inicializado e contém dados.
5. Confirme que o deploy iniciou e acesse a URL `.onrender.com` apresentada pelo Render.

O Render pode fazer deploy automaticamente quando novas alterações são enviadas à branch conectada. O serviço gratuito pode suspender-se quando inativo e demorar para responder ao primeiro acesso. Planos e limites gratuitos podem mudar; consulte as [limitações do Render](https://render.com/docs/free) e os [planos da Neon](https://neon.com/docs/introduction/plans).

## Observações

- Configure uma `SECRET_KEY` aleatória fora do código em qualquer ambiente compartilhado ou hospedado. O valor padrão serve apenas para desenvolvimento local.
- O banco armazena datas em UTC e as telas as exibem no fuso configurado em `APP_TIMEZONE` (padrão: `America/Sao_Paulo`).
- `init-db` cria tabelas, mas não é uma ferramenta de migrações de esquema. Faça backup antes de qualquer operação de migração de dados.
- Esta aplicação foi feita para fins acadêmicos; não foi preparada ou auditada para uso em produção comercial.
