# ADR-0012 — Estratégia de CI no GitHub Actions

## Status

Proposto

## Contexto

Projeto sem CI automatizado. Mudanças em models, policies, services e migrations exigem validação manual antes de merge. ADR-0010 exige testes contra banco real. ADR-0004 pressupõe services transacionais com policies bem-definidas. Falta barreira automática que valide formatação, lint, type safety e integridade antes de main.

Riscos sem CI:
- Lint diverge entre devs.
- Type hints negligencionadas.
- Testes faltam ou quebram silenciosamente.
- Migrations inconsistentes.
- seed_dev não é testado (ADR-0009).
- Branch principal sem garantia de qualidade.

## Decisão

### Triggers

CI roda em:
- `pull_request` para `main` (obrigatório pra merge)
- `push` para `main` (rede de segurança + status oficial)

Não roda em: `push` para branches `feat/*`, `fix/*` (ponto de controle é PR); `schedule` (sem necessidade atual).

### Jobs e ordem (fail-fast)

```
Setup/Cache
  ↓
Quality gates baratos (paralelo):
  - ruff format --check
  - ruff check
  - mypy
  ↓
Backend (após quality):
  - tests (PostgreSQL real)
  - migrations check
```

Qualquer falha em quality → não roda backend. Falha em lint poupa tempo rodando testes caros.

### Quality checks

**Formatter + Linter:**
```
ruff format --check .
ruff check .
```

**Type checker:**
```
mypy apps
```

Policy de tipagem: gradual. Obrigatório em `services.py`, `policies.py`, `selectors.py`, `transitions.py`. Opcional em models/views/forms/testes.

Sem auto-commit de formatação. CI falha; dev arruma localmente (`ruff format . && ruff check . --fix`).

### Stack

- **Python**: 3.13 (conforme `pyproject.toml`)
- **Django**: 6.0.x (conforme `pyproject.toml`)

Sem matrix multi-versão. Stack é versionado no projeto; upgrade é tarefa explícita (novo ADR/PR).

### Dependências

- **Gerenciador**: `uv` (conforme `RTK.md`)
- **Lockfile**: `uv.lock` obrigatório
- **Instalação CI**: `uv sync --frozen`
- **Cache**: `~/.cache/uv`, chave por `uv.lock`

Se `uv.lock` não existir no commit inicial do CI, será gerado e commitado antes.

### Banco de dados no CI

- **Imagem**: PostgreSQL 16
- **Driver**: GitHub Actions service container
- **Configuração**: `POSTGRES_DB=wms_saep_test`, `POSTGRES_USER=postgres`, `POSTGRES_PASSWORD=postgres`
- **Health check**: `pg_isready`

SQLite fora (projeto usa `select_for_update`, constraints reais, FKs — requer PostgreSQL).

### Testes e migrations

Ordem no CI:

```bash
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py migrate --run-syncdb
SEED_DEV_HABILITADO=true uv run python manage.py seed_dev
SEED_DEV_HABILITADO=true uv run python manage.py seed_dev  # 2ª execução
uv run pytest
```

**Contrato:**
- `makemigrations --check`: valida que models e migrações estão sincronizadas.
- `migrate`: aplica schema em banco limpo.
- `seed_dev` 2x: valida que bootstrap canônico é idempotente (ADR-0009).
- `pytest`: executa suíte com fixtures próprias. Testes **não dependem** do seed.

Se `seed_dev` não existir, pulá-lo nesta fase.

### Branch protection

Configuração em `main`:

```
✓ Require a pull request before merging
✓ Require status checks to pass before merging
  (ruff format, ruff check, mypy, tests, migrations)
✓ Require branches to be up to date before merging
✗ Require code reviews
✗ Require signed commits
```

PR é o ponto de controle. Merge só com CI verde.

### Documentação

**ADR-0012** (este arquivo): decisões estruturais e trade-offs.

**docs/ci-pipeline.md**: manual operacional — como rodar localmente, debugar, evoluir.

Agentes implementando CI: seguem ADR para decisões, docs/ci-pipeline.md para operação.

## Consequências

- Toda mudança em models, políticas, migrations ou serviços passa por validação automática.
- Formatação/lint/type são disciplina primeiro, não overhead.
- PostgreSQL real no CI valida constraints e select_for_update.
- Testes contra DB real (ADR-0010) rodados automaticamente.
- Seed canônico é testado (não apenas documentado).
- Branch principal é sempre "verde" ou em transição explícita.

## Reversibilidade e critérios de evolução

Nenhuma decisão aqui é irreversível. Todas podem ser reavaliadas conforme projeto evolua.

**Decidimos revisáveis:**

| Decisão | Quando reavaliar |
|---------|------------------|
| `pull_request` + `push main` | Se houver CI redundante ou custo de compute evidente |
| Fail-fast por camadas | Se a ordem resultar em feedback confuso |
| Ruff + mypy | Se a equipe adotar ferramenta padrão diferente |
| Python 3.13 + Django 6.0 (sem matrix) | Quando upgrade entrar no roadmap e houver suporte multi-versão |
| PostgreSQL service | Se precisar de múltiplos serviços (Redis, Celery) ou extensões |
| uv + uv.lock | Apenas se o projeto abandonar `uv` ou houver incompatibilidade operacional |
| Branch protection sem review obrigatório | Quando a equipe crescer ou houver requisitos de governança |
| Sem schedule | Se surgirem testes lentos, integrações externas instáveis ou regressões intermitentes |

**Trade-off aceito:**

Simplicidade inicial + feedback rápido para projeto piloto > cobertura exaustiva. Conforme projeto ganhe escala ou requisitos, adicionar matrix, Docker Compose, schedule, reviews.

## Documentação futura

- `docs/ci-pipeline.md`: como rodar/debugar/evoluir
- `.github/workflows/ci.yml`: implementação do workflow
- Seção em `docs/CONVENTIONS.md` (se necessário): contrato de dependências e uv

---

**Próximas tarefas:**
1. Criar `docs/ci-pipeline.md`
2. Implementar `.github/workflows/ci.yml`
3. Gerar/versionar `uv.lock` se não existir
4. Configurar branch protection em `main` no GitHub
