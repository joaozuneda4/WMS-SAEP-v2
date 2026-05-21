# CI Pipeline — Manual operacional

Implementação das decisões em ADR-0012. Este documento é guia prático: como rodar localmente, entender falhas, evoluir pipeline.

## Execução local (antes de PR)

Rodar o mesmo pipeline do CI localmente:

```bash
# Setup
uv sync --frozen

# Quality gates (rápido)
uv run ruff format --check .
uv run ruff check .
uv run mypy apps

# Backend (exige PostgreSQL rodando)
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py migrate --run-syncdb
SEED_DEV_HABILITADO=true uv run python manage.py seed_dev
SEED_DEV_HABILITADO=true uv run python manage.py seed_dev
uv run pytest
```

Se algo falhar localmente, não abre PR até corrigir.

## Falhas comuns e como corrigir

### ruff format falha

```bash
uv run ruff format .
uv run ruff check . --fix
git add .
```

Depois roda novamente o pipeline. Não commita formatação isolada em PR — formato é disciplina, não mudança funcional.

### ruff check falha (import sort, regras)

```bash
uv run ruff check . --fix
git add .
```

Alguns erros exigem correção manual. Confira output de `uv run ruff check .` para detalhes.

### mypy falha

Type hints são obrigatórios em `services.py`, `policies.py`, `selectors.py`, `transitions.py`.

Exemplo erro:
```
apps/requisicoes/services.py:42: error: Argument 1 to "criar_requisicao" has incompatible type
```

Adicione type hints à assinatura:

```python
def criar_requisicao(
    *,
    ator_id: int,
    beneficiario_id: int,
) -> Requisicao:
    ...
```

Se uma importação causar erro, adicione `# type: ignore` como último recurso e documente o motivo.

### makemigrations --check falha

Você editou um model e não gerou migração.

```bash
uv run python manage.py makemigrations
# Verifica se gerou arquivo
git add apps/<app>/migrations/
```

Depois:

```bash
uv run python manage.py makemigrations --check --dry-run
```

### migrate falha

PostgreSQL pode estar fora ou mal-configurado. Confirme:

```bash
# Ou via Docker, ou rodando pg localmente
psql -U postgres -d wms_saep_test -c "SELECT 1"
```

Se DB não existir:

```bash
createdb -U postgres wms_saep_test
```

Depois reexecuta migrate.

### seed_dev falha

ADR-0009 define contrato. Se seed falhar na primeira execução:

```bash
SEED_DEV_HABILITADO=true uv run python manage.py seed_dev --verbosity 2
```

`--verbosity 2` dá mais detalhe. Confira:
- Dados mínimos são válidos?
- Constraints estão sendo respeitadas?
- Campos obrigatórios existem?

**Importante:** seed_dev roda 2x no CI. Se falhar na segunda execução (idempotência), é erro de design do seed. Não mude o código do teste; corrija o seed.

### pytest falha

Pode ser teste floppy, fixture faltando, ou bug real.

Reexecuta:

```bash
uv run pytest -xvs apps/<app>/tests/test_<module>.py::test_<name>
```

Flags:
- `-x`: para no primeiro erro
- `-v`: verbose (mostra nomes dos testes)
- `-s`: mostra stdout (print/logging)

Se falhar novamente, é bug real — não é floppy. Investiga e corrige o código.

Se passa na segunda tentativa, é floppy. Marque com `@pytest.mark.flaky(reruns=2)` e abre issue para investigar.

## Atualizar dependências

Se editou `pyproject.toml` (novas dependências):

```bash
uv lock
git add uv.lock
```

Não commita `pyproject.toml` e `uv.lock` separadamente. Se divergirem, CI falha com:

```
uv sync --frozen
error: the lock file is out of date
```

Solução:

```bash
uv lock
git add uv.lock
```

Depois reexecuta CI localmente.

## CI no GitHub Actions

Quando abre PR contra `main`:

1. GitHub dispara workflow `.github/workflows/ci.yml`
2. Checks rodam na order: quality → migrations → tests
3. Status aparece em "Checks" na PR
4. Se algum check falha, merge é bloqueado
5. Clica em "Show all checks" → "Details" para ver output

Output completo fica em Actions tab.

### Como debugar falha no CI

Se CI falha mas local passa:

1. Confira a branch é branch da PR (não `main`)
2. Rebase da branch contra `main` atualizada
3. Reexecuta pipeline local
4. Se ainda passar, force push para PR (CI roda novamente)

Se CI falha e local falha:

- Siga seções acima ("Falhas comuns")
- Commita correção
- Força push para PR
- CI reexecuta automaticamente

### Status checks obrigatórios

Em `main`, esses checks são obrigatórios:

```
- ruff format
- ruff check
- mypy
- pytest
- migrations
```

PR só pode ser mergeado com todos verdes.

## Evoluir o pipeline

Se precisar adicionar:

### Novo linter / rule

Edite `.github/workflows/ci.yml` (job `quality`). Reexecuta localmente antes.

Atualiza `docs/ci-pipeline.md` com comando local correspondente.

### Novo stage (ex: security scan)

Adiciona novo job em workflow. Define `needs: quality` ou `needs: backend` para ordem.

### Schedule noturno

Confira ADR-0012 — quando reavaliar. Se motivo existe, adiciona trigger `schedule` em workflow.

### Matrix multi-versão

Confira ADR-0012. Se Django upgrade entra no roadmap, adiciona strategy.matrix em workflow.

## Variáveis de ambiente e Secrets

CI usa:

- `DJANGO_SETTINGS_MODULE=config.settings.test`
- `DATABASE_URL=postgres://postgres:postgres@localhost:5432/wms_saep_test` (ou equivalente)
- `SEED_DEV_HABILITADO=true` (para seed_dev rodar)

Se código precisar de secrets (API keys, tokens):

1. Adiciona em GitHub Secrets
2. Expõe em workflow: `secrets: inherit` ou `env: ${{ secrets.VAR }}`
3. Documenta em ADR ou neste arquivo

**Nunca commita secrets em código.**

## SLA esperado

Tempo típico do pipeline:

- ruff format: ~5s
- ruff check: ~10s
- mypy: ~15s
- makemigrations --check: ~2s
- migrate: ~5s
- seed_dev (2x): ~10s
- pytest: ~30-60s (depende de DB setup)

**Total:** ~1-2 minutos.

Se passar de 5 minutos, algo está fora do padrão. Confira:
- PostgreSQL service health check
- Cache do uv funcionando
- Testes com fixtures pesadas

## Reporting

Logs completos do CI:

1. Abre Actions tab no repo
2. Clica no workflow `CI`
3. Clica na run (associada ao commit/PR)
4. Clica no job que falhou
5. Expande step com erro

Copia output inteiro (não snippets). Cria issue com contexto se necessário.

---

**Próxima leitura:** ADR-0012 para decisões.
