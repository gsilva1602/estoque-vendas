# Guia de uso — Estoque & Vendas

Sistema acadêmico para acompanhar produtos, entradas de estoque e vendas. Este guia é para quem já tem acesso ao site.

## Acessar o sistema

Abra [Estoque & Vendas](https://estoque-vendas-j21j.onrender.com) no navegador e entre com o usuário e a senha fornecidos pelo administrador. Não há cadastro público: se ainda não recebeu uma conta ou esqueceu a senha, solicite ajuda ao administrador do sistema.

O sistema mostra apenas as áreas permitidas para o perfil da sua conta. Para encerrar o acesso, use **Sair** no cabeçalho.

## Administrador

### Acompanhar o painel

Em **Dashboard**, consulte os indicadores de produtos cadastrados, unidades em estoque, vendas registradas e valor vendido. A página também apresenta vendas recentes e a posição do estoque. Produtos com até 5 unidades são indicados como estoque baixo; produtos sem unidades aparecem como sem estoque.

O administrador acompanha os dados, mas não registra vendas nem entradas de estoque.

### Consultar relatórios

Em **Relatório de vendas**, selecione opcionalmente as datas inicial e final, o produto e/ou o vendedor e clique em **Filtrar relatório**. Use **Limpar filtros** para retornar à consulta sem filtros. O relatório reúne faturamento, quantidade de vendas e unidades vendidas, além de rankings por produto e vendedor e o detalhamento das vendas do período.

### Gerenciar usuários

Em **Usuários**, preencha o nome, uma senha de pelo menos 8 caracteres e o perfil da nova conta:

- **Administrador:** painel, relatórios e gerenciamento de usuários.
- **Vendedor:** registro de vendas e consulta das próprias vendas.
- **Estoquista:** cadastro de produtos, entradas e histórico de movimentações.

Revise o perfil antes de criar a conta e compartilhe os dados de acesso com a pessoa de forma segura.

## Estoquista

### Cadastrar produtos

Em **Estoque**, use **Cadastrar produto** para informar nome, categoria e preço unitário de venda. O cadastro começa com quantidade zero; cadastrar o produto não adiciona unidades ao estoque.

### Registrar uma entrada

Na mesma página, em **Registrar entrada**, escolha o produto, informe a quantidade recebida (maior que zero) e clique em **Adicionar ao estoque**. A quantidade disponível é atualizada e a entrada fica registrada no histórico com data e responsável. O vendedor poderá selecionar o produto para venda quando houver saldo.

### Consultar e corrigir entradas

Confira os produtos cadastrados e as entradas recentes em **Estoque**. Acesse **Movimentações** para consultar entradas, vendas, estornos e ajustes; filtre por produto, tipo ou período e use **Limpar** para remover os filtros.

Se você registrou uma entrada incorreta, poderá corrigi-la pela própria tela dentro de 30 minutos. Informe a nova quantidade e uma justificativa de pelo menos 10 caracteres. Use quantidade zero para cancelar a entrada. A alteração e a justificativa permanecem no histórico; o lançamento original não é apagado.

## Vendedor

### Registrar uma venda

Em **Vendas**, selecione um produto disponível, informe a quantidade (maior que zero) e clique em **Finalizar venda**. A aplicação valida o saldo e, se a operação for aceita, registra a venda e desconta as unidades do estoque. O preço usado é o preço unitário cadastrado; o total e o preço ficam gravados na venda.

Se o produto não aparecer, ele pode estar sem estoque. Peça ao estoquista para registrar uma entrada. Se a quantidade solicitada exceder o saldo, a venda não será registrada; tente novamente com uma quantidade disponível.

### Consultar e corrigir suas vendas

A seção **Minhas vendas** mostra as suas vendas recentes. Se você registrou uma venda incorreta, poderá corrigi-la dentro de 30 minutos, com uma justificativa de pelo menos 10 caracteres. Use quantidade zero para cancelar: as unidades correspondentes são devolvidas ao estoque. A correção fica registrada no histórico.

## No celular

A aplicação pode ser acessada pelo navegador do celular. O menu se reorganiza para telas menores; cartões, formulários e filtros passam a ocupar uma coluna quando necessário. Em tabelas largas, deslize horizontalmente dentro da tabela para consultar as demais colunas.

## Observações

- As permissões são verificadas pelo sistema. Um perfil não consegue acessar as operações de outro apenas digitando o endereço da página.
- O horário exibido segue o fuso configurado para a aplicação; a referência padrão é **America/Sao_Paulo**.
- O serviço gratuito pode levar mais tempo para responder depois de um período sem acessos.
- Este projeto foi desenvolvido para fins acadêmicos.
