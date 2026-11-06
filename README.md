# Sistema de Estoque e Vendas — versão 2

Aplicação acadêmica em Flask com três perfis, cadastro de produtos, histórico de entradas e registro de vendas com baixa automática de estoque.

## Perfis e permissões

- **admin**: dashboard com indicadores de estoque e vendas, vendas recentes e estoque baixo; gerenciamento de usuários. Não registra vendas nem entradas.
- **vendedor**: registra vendas e consulta apenas as próprias vendas. Não acessa a tela de estoque nem o dashboard.
- **estoquista**: cadastra produtos, registra entradas de estoque e consulta o histórico de entradas. Não acessa vendas nem dashboard.

As permissões são verificadas no servidor, não apenas escondendo links na interface.

## Requisitos e execução local (Windows / PowerShell)

Requer Python 3.11+.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
flask --app app init-db
flask --app app create-user
flask --app app create-user
flask --app app create-user
flask --app app run --debug
```

No comando `create-user`, informe um nome, senha com pelo menos 8 caracteres e perfil `admin`, `vendedor` ou `estoquista`. Crie um usuário de cada perfil. Acesse `http://127.0.0.1:5000`.

## Regras implementadas

- Produtos têm nome, categoria, quantidade atual e preço unitário de venda.
- O estoque começa em zero; a quantidade é aumentada por uma entrada registrada pelo estoquista.
- Cada entrada grava produto, quantidade, data/hora e usuário responsável.
- Vendedores só podem vender produtos com saldo disponível.
- Quantidade inválida ou estoque insuficiente bloqueia a venda e apresenta aviso.
- Ao registrar venda, o sistema reduz o estoque e salva a venda na mesma transação.
- O histórico de vendas registra produto, quantidade, preço unitário, total, data/hora e vendedor.
- O preço é armazenado na venda, para preservar o valor praticado mesmo se o preço atual do produto mudar futuramente.

## Observações importantes

- `flask --app app init-db` cria tabelas novas; não é uma ferramenta de migração. Se você já tem um banco antigo da versão anterior, faça backup antes de atualizar. Para este protótipo, o caminho mais simples é iniciar com um banco vazio.
- `SECRET_KEY` deve ser definida como variável de ambiente em produção.
- O projeto usa Psycopg 3 e carrega `.env.local` automaticamente no desenvolvimento local. O Neon CLI gera `DATABASE_URL` (conexão pooled, usada pelo app) e `DATABASE_URL_UNPOOLED` (conexão direta, usada na migração). Para importar o banco SQLite atual para um PostgreSQL vazio, faça primeiro um backup de `instance/estoque.db` e execute:
  ```powershell
  flask --app app migrate-sqlite
  ```
  O comando usa `instance/estoque.db` por padrão (ou informe outro arquivo com `--source caminho`). Ele cria as tabelas que faltam, copia os dados preservando os IDs e ajusta as sequências do PostgreSQL. O destino precisa estar vazio; uma falha reverte a transação de cópia. A migração exige que o SQLite tenha as tabelas e colunas da versão atual do app.
- Para publicar sem custo neste projeto acadêmico, o arquivo `render.yaml` prepara um serviço web gratuito no Render. Crie um banco PostgreSQL no [plano gratuito da Neon](https://neon.com/pricing), copie a connection string e configure `DATABASE_URL` no serviço Render ao criar o [Blueprint](https://render.com/docs/blueprint-spec). O plano gratuito atual da Neon tem limites de uso e armazenamento; consulte os [termos atuais](https://neon.com/docs/introduction/plans) antes de usar.
- Faça a migração SQLite → Neon localmente antes de publicar. Depois conecte o repositório ao Render e crie o serviço a partir do Blueprint. Configure no Render os valores pooled e unpooled da Neon em `DATABASE_URL` e `DATABASE_URL_UNPOOLED`. O Render gera `SECRET_KEY` automaticamente e faz deploy a cada atualização da branch configurada. A aplicação inicia com `gunicorn wsgi:app`.
- Não use o Postgres gratuito do Render para este trabalho se precisar preservar os dados por mais de um mês: atualmente esses bancos expiram 30 dias após a criação. O serviço web gratuito do Render pode dormir após 15 minutos sem tráfego e levar cerca de um minuto para voltar. Consulte as [limitações do plano gratuito](https://render.com/docs/free); esses planos são para projetos acadêmicos/testes, não produção.
- O histórico registra datas pelo relógio do banco de dados. Confirme o fuso horário do ambiente de hospedagem antes de usar como registro oficial.
- Esta é uma base acadêmica inicial. Antes de produção, adicionar proteção CSRF, migrações com Flask-Migrate, testes automatizados, tratamento de concorrência de estoque e auditoria mais completa.
