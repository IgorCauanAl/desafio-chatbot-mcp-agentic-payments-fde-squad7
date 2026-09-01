# Chatbot MCP de Pagamentos

Aplicação local de pagamentos agênticos construída para o desafio **Chatbot com Tools
MCP de Pagamentos**. O usuário faz login, conversa em linguagem natural com um agente
de IA e pode consultar produtos, registrar uma intenção e concluir uma compra simulada
com cartão ou Pix.

## Arquitetura

```text
Frontend React → Backend FastAPI (auth + agente + MCP client)
                         ↓
                  Servidor MCP (stdio)
                         ↓
                  API de pagamentos
```

- **Frontend:** React + Vite, com login e chat via WebSocket.
- **Backend:** FastAPI, JWT, SQLite/SQLAlchemy e orquestração do agente.
- **Modelo:** Groq REST API usando `qwen/qwen3.6-27b`.
- **MCP:** servidor local que expõe as três ferramentas de negócio.
- **Persistência:** SQLite para o ambiente local; intenções e compras são validadas no
  backend.

## Pré-requisitos

- Python 3.13+
- Node.js 20+
- Uma chave da API da Groq

## Configuração e execução

### Backend

```bash
cd backend
cp .env.example .env
```

Configure no `.env` valores próprios para `JWT_SECRET`, `REFRESH_SECRET` e
`GROQ_API_KEY`. O modelo utilizado na entrega é:

```dotenv
LLM_PROVIDER=groq
GROQ_API_BASE_URL=https://api.groq.com/openai/v1
GROQ_MODEL=qwen/qwen3.6-27b
MCP_SERVER_CWD=mcp-server/src
MCP_SERVER_MODULE=server_mcp.server
MAX_TOOL_ITERATIONS=5
```

Depois, inicialize e execute:

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

O backend ficará disponível em `http://localhost:8000`. A documentação OpenAPI está em
`http://localhost:8000/docs`.

### Frontend

Em outro terminal:

```bash
cd frontend
npm install
npm run dev
```

O frontend será exibido em `http://localhost:5173`. Para execução em domínios
diferentes, configure `VITE_API_URL` e `VITE_WS_URL` no arquivo `.env` do frontend.

### Usuários de demonstração

As credenciais abaixo são criadas apenas no ambiente local:

| Usuário | Senha | Limite |
|---|---|---:|
| `alice@example.com` | `alice123` | R$ 1.000,00 |
| `bob@example.com` | `bob12345` | R$ 100,00 |

## Tools MCP

### `listar_catalogo`

Lista os produtos disponíveis e aceita o filtro opcional `categoria`.

```json
{
  "categoria": "perifericos"
}
```

Retorna produtos com `id`, `nome`, `preco`, `moeda` e `estoque`.

### `registrar_intencao`

Registra uma intenção sem movimentar dinheiro:

```json
{
  "produto_id": "prod_003",
  "quantidade": 1
}
```

O backend calcula o valor total e retorna a intenção com status `pendente` e prazo de
expiração.

### `realizar_compra`

Executa uma intenção válida:

```json
{
  "intencao_id": "intencao-gerada-pelo-backend",
  "metodo_pagamento": "pix",
  "confirmado": true
}
```

Os métodos aceitos são `pix` e `cartao`. O preço não é aceito como argumento: é
recuperado da intenção registrada. Em caso de falha, a tool retorna erros de negócio
como `INTENCAO_INVALIDA`, `INTENCAO_EXPIRADA`, `INTENCAO_JA_PAGA`,
`LIMITE_EXCEDIDO` ou `METODO_INVALIDO`.

## Fluxo da conversa

1. O usuário realiza login e recebe um token JWT.
2. O frontend abre `WS /api/v1/chat/ws?token=<access_token>`.
3. O agente recebe o histórico completo da sessão e descobre as tools via MCP.
4. O agente consulta o catálogo quando necessário.
5. O agente registra a intenção antes de solicitar o pagamento.
6. O agente pede o método e a confirmação explícita do usuário.
7. O backend valida usuário, sessão, intenção, expiração, estoque e limite antes de
   concluir a compra.

O valor, o limite e a validade são controlados pelo backend. O modelo não pode inventar
uma intenção válida nem alterar o preço.

## Segurança e confiabilidade

- O chat exige autenticação; token ausente ou inválido encerra o WebSocket com código
  `1008`.
- Intenções são vinculadas ao usuário e ao `sid` da sessão JWT.
- Compras repetidas são recusadas por idempotência e estado da intenção.
- O histórico é separado por sessão e inclui mensagens, chamadas de ferramenta e
  resultados.
- Falhas da IA ou do MCP retornam eventos de erro sem encerrar a conexão quando
  possível.
- Logs estruturados e auditáveis registram cada chamada MCP com `user_id`, `session_id`,
  `tool_name`, timestamp, quantidade, valor, status e resultado. Tokens são redigidos e
  valores longos são truncados.

Exemplo de evento de auditoria:

```json
{
  "event": "mcp_tool_result",
  "user_id": "usr_alice",
  "session_id": "sessao-123",
  "tool_name": "realizar_compra",
  "quantity": 1,
  "amount": 249.9,
  "status": "aprovado",
  "result": "{\"status\":\"aprovado\", ...}"
}
```

## Testes e qualidade

```bash
cd backend
uv run ruff format --check .
uv run ruff check .
uv run mypy app
uv run pytest -q
```

```bash
cd frontend
npm run build
```

## Checklist da entrega

- [x] Frontend e backend locais.
- [x] Login e proteção do chat.
- [x] Três tools MCP descobertas pelo agente.
- [x] Compra com `cartao` e `pix`.
- [x] Validação de intenção por usuário e sessão.
- [x] Bloqueio de intenção inválida, expirada ou já paga.
- [x] Bloqueio de compra acima do limite.
- [x] Histórico completo enviado ao modelo.
- [x] Modelo documentado: `qwen/qwen3.6-27b`.
- [x] Logs auditáveis das chamadas MCP.

## Execução

As imagens abaixo registram a execução local da aplicação, desde a autenticação até os
fluxos de sucesso e de validação das regras de pagamento.

### Login

![Tela de login](docs/images/01-login.png)

### Consulta do catálogo

![Catálogo de produtos](docs/images/02-catalogo.png)

### Registro da intenção de compra

![Intenção de compra registrada](docs/images/03-intencao.png)

### Compra aprovada com cartão

![Compra aprovada com cartão](docs/images/04-pagamento-cartao.png)

### Compra aprovada com Pix

![Compra aprovada com Pix](docs/images/05-pagamento-pix.png)

### Compra bloqueada por limite excedido

![Limite excedido](docs/images/06-limite-excedido.png)

### Recusa de intenção inválida

![Intenção inválida](docs/images/07-intencao-invalida.png)

## Estrutura do projeto

```text
backend/       API, autenticação, banco, agente e testes
frontend/      Interface React do login e chat
mcp-server/    Servidor MCP e integrações com a API de pagamentos
```
