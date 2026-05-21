from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_ci_workflow_declara_gates_do_issue_16():
    workflow = REPO_ROOT / '.github' / 'workflows' / 'ci.yml'
    conteudo = workflow.read_text()

    assert 'pull_request:' in conteudo
    assert 'push:' in conteudo
    assert 'branches: [main]' in conteudo
    assert 'python-version: "3.13"' in conteudo
    assert 'astral-sh/setup-uv' in conteudo
    assert 'uv sync --frozen' in conteudo
    assert 'ruff format --check .' in conteudo
    assert 'ruff check .' in conteudo
    assert 'mypy apps' in conteudo
    assert 'postgres:16' in conteudo
    assert 'pg_isready' in conteudo
    assert 'makemigrations --check --dry-run' in conteudo
    assert 'migrate --run-syncdb' in conteudo
    assert conteudo.count('seed_dev') >= 2
    assert 'pytest -q -ra --tb=short --strict-markers --disable-warnings' in conteudo
