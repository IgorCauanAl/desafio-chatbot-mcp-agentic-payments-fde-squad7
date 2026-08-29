# Backend — Pagamentos Agênticos

API FastAPI responsável por autenticação JWT, persistência e regras de segurança de
catálogo, intenções e compras. Todos os endpoints de negócio exigem `Bearer token`.

## Executar

```bash
cd backend
cp .env.example .env
# troque JWT_SECRET em .env
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

A documentação interativa fica em `http://localhost:8000/docs`. Na primeira execução,
o banco SQLite e os dados de demonstração são criados automaticamente:

- `alice@example.com` / `alice123` — limite R$ 1.000,00
- `bob@example.com` / `bob12345` — limite R$ 100,00

Essas credenciais existem apenas para o ambiente local. Em produção, substitua o banco
por PostgreSQL e provisione os usuários por um fluxo administrativo.

Para demonstração, o `lifespan` também inicializa um banco vazio. A migração Alembic é
o mecanismo canônico para ambientes persistentes.

## Contrato resumido

| Método | Endpoint | Uso |
|---|---|---|
| `POST` | `/api/v1/auth/tokens` | Login e emissão do JWT |
| `GET` | `/api/v1/products` | Catálogo paginado, filtro `category` |
| `POST` | `/api/v1/purchase-intentions` | Registra intenção e calcula o total |
| `GET` | `/api/v1/purchase-intentions/{id}` | Consulta uma intenção da sessão |
| `POST` | `/api/v1/purchases` | Compra com `pix` ou `cartao` |
| `GET` | `/health` | Liveness |
| `GET` | `/api/v1/health` | Readiness do banco |

`POST /purchases` exige o header `Idempotency-Key`. A intenção fica vinculada ao
usuário **e ao `sid` da sessão JWT** que a criou. O valor e o preço nunca são aceitos
do cliente. Erros de negócio usam os códigos do desafio: `INTENCAO_INVALIDA`,
`INTENCAO_EXPIRADA`, `INTENCAO_JA_PAGA`, `LIMITE_EXCEDIDO` e `METODO_INVALIDO`.

## Qualidade

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy app
uv run pytest -q
```
