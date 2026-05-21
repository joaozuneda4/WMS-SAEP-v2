import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def _bloco_job(conteudo: str, job_name: str) -> str:
    pattern = re.compile(
        rf'(?ms)^  {re.escape(job_name)}:\n(?P<body>.*?)(?=^  [a-z0-9-]+:|\Z)',
    )
    match = pattern.search(conteudo)
    assert match is not None, f'Job {job_name} não encontrado no workflow.'
    return match.group('body')


def test_ci_workflow_declara_gates_do_issue_16():
    workflow = REPO_ROOT / '.github' / 'workflows' / 'ci.yml'
    conteudo = workflow.read_text()
    conteudo_normalizado = ' '.join(conteudo.split())
    migrations = _bloco_job(conteudo, 'migrations')
    pytest_job = _bloco_job(conteudo, 'pytest')

    assert re.search(
        r'^on:\n\s+pull_request:\n\s+branches: \[main\]\n\s+push:\n\s+branches: \[main\]$',
        conteudo,
        re.MULTILINE,
    )
    assert re.search(r'^permissions:\n\s+contents: read$', conteudo, re.MULTILINE)
    assert conteudo.count('persist-credentials: false') >= 5
    assert 'python-version: "3.13"' in conteudo
    assert 'astral-sh/setup-uv' in conteudo
    assert 'uv sync --frozen' in conteudo
    assert 'ruff format --check .' in conteudo
    assert 'ruff check .' in conteudo
    assert 'mypy apps' in conteudo
    assert conteudo_normalizado.count('needs: [ruff-format, ruff-check, mypy]') == 2
    assert 'postgres:16' in conteudo
    assert 'pg_isready' in conteudo
    assert 'uv run python manage.py makemigrations' in conteudo
    assert 'makemigrations --check --dry-run' in conteudo
    assert 'migrate --run-syncdb' in conteudo
    assert conteudo.count('seed_dev') >= 2
    assert 'pytest -q -ra --tb=short --strict-markers --disable-warnings' in conteudo
    assert 'DEBUG: "true"' in migrations
    assert 'DEBUG:' not in pytest_job
