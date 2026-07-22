"""Testes de regressão para #86 — tokens semânticos dentro dos componentes.

Garante duas coisas que o critério de aceite da issue pede como "busca
automatizável":

1. Nenhuma classe de cor de paleta crua (blue/red/amber/green/teal) volta a
   aparecer dentro de apps/core/templates/components/ ou
   apps/core/templates/core/partials/_messages.html.
2. Os tokens novos do @theme realmente compilam pra CSS utilizável — roda
   `npm run css:build` e confere que as custom properties e as utilities
   usadas pelos templates existem no app.css gerado.
"""

import pathlib
import re
import shutil
import subprocess

import pytest

BASE_DIR = pathlib.Path(__file__).resolve().parents[3]
TAILWIND_CLI = BASE_DIR / 'node_modules' / '.bin' / 'tailwindcss'
COMPONENTS_DIR = BASE_DIR / 'apps' / 'core' / 'templates' / 'components'
MESSAGES_TEMPLATE = (
    BASE_DIR / 'apps' / 'core' / 'templates' / 'core' / 'partials' / '_messages.html'
)
INPUT_CSS = BASE_DIR / 'apps' / 'core' / 'static' / 'core' / 'css' / 'input.css'
APP_CSS = BASE_DIR / 'apps' / 'core' / 'static' / 'core' / 'css' / 'app.css'

CLASSE_CRUA_RE = re.compile(
    r'(?:bg|text|border|ring|divide)-(?:blue|red|amber|green|teal)-\d'
)

TOKENS_NOVOS = [
    '--color-primary-muted-strong',
    '--color-primary-border-strong',
    '--color-primary-text-emphasis',
    '--color-primary-text-strong',
    '--color-danger-muted-strong',
    '--color-danger-border-strong',
    '--color-danger-border-input',
    '--color-danger-accent',
    '--color-danger-hover',
    '--color-danger-active',
    '--color-danger-text-emphasis',
    '--color-danger-text-strong',
    '--color-warning-muted-strong',
    '--color-warning-border-strong',
    '--color-warning-text-subtle',
    '--color-warning-text-strong',
    '--color-success-text-emphasis',
    '--color-success-text-strong',
    '--color-return-text-strong',
]

# Amostra de utilities consumidas pelos templates que precisam ter sido
# realmente geradas pelo build (nome errado/typo no @theme não quebra o
# grep de cor crua, só a ausência da utility no app.css).
UTILITIES_ESPERADAS = [
    'bg-primary-muted-strong',
    'bg-danger-muted-strong',
    'bg-warning-muted-strong',
    'text-primary-text-strong',
    'text-danger-text-strong',
    'text-warning-text-strong',
    'text-success-text-strong',
    'text-return-text-strong',
    'text-success-text',
    'text-return-text',
    'border-danger-border-strong',
    'focus-visible:ring-danger-accent',
    'bg-warning-subtle',
]

# Tokens declarados no @theme mas sem consumidor real em nenhum template
# hoje (toda a família info-*, usada só pelo alert/messages "info" que na
# verdade consome primary-*). Não devem ter utility compilada — se
# aparecerem, algo (doc, teste) vazou pro scan.
UTILITIES_DORMANTES = [
    '.bg-info{',
    '.bg-info-subtle{',
    '.bg-info-muted{',
    '.border-info-border{',
    '.text-info-text{',
]


def _arquivos_alvo():
    arquivos = sorted(COMPONENTS_DIR.rglob('*.html'))
    arquivos.append(MESSAGES_TEMPLATE)
    return arquivos


@pytest.mark.parametrize('arquivo', _arquivos_alvo(), ids=lambda p: p.name)
def test_zero_cor_crua_de_marca_no_arquivo(arquivo):
    conteudo = arquivo.read_text(encoding='utf-8')
    ocorrencias = CLASSE_CRUA_RE.findall(conteudo)
    assert ocorrencias == [], (
        f'{arquivo.relative_to(BASE_DIR)} ainda usa cor crua de marca: {ocorrencias}'
    )


def test_tokens_novos_documentados_existem_no_input_css():
    conteudo = INPUT_CSS.read_text(encoding='utf-8')
    faltando = [token for token in TOKENS_NOVOS if token not in conteudo]
    assert faltando == [], f'Tokens ausentes em input.css: {faltando}'


@pytest.mark.skipif(
    not TAILWIND_CLI.exists() and shutil.which('tailwindcss') is None,
    reason=(
        'Tailwind CLI não instalado (node_modules ausente) — ambiente sem '
        '`npm install`, ex. job de CI só-Python. Rodar localmente após '
        '`npm install` para validar o build.'
    ),
)
def test_css_build_gera_tokens_e_utilities_novas():
    resultado = subprocess.run(
        ['npm', 'run', 'css:build'],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert resultado.returncode == 0, (
        f'npm run css:build falhou:\nstdout={resultado.stdout}\nstderr={resultado.stderr}'
    )

    app_css = APP_CSS.read_text(encoding='utf-8')

    tokens_faltando = [token for token in TOKENS_NOVOS if token not in app_css]
    assert tokens_faltando == [], (
        f'Tokens novos não aparecem no app.css compilado (typo ou @theme '
        f'não reconhecido): {tokens_faltando}'
    )

    def _utility_compilada(nome):
        # Seletor real: classe com ':' de variante escapado (\:), seguido de
        # '{' (regra própria) ou ':' (pseudo-classe, ex. :focus-visible) —
        # nunca um sufixo de identificador (ex. '-strong'), pra não casar
        # por substring dentro de uma utility maior (#88).
        seletor = re.escape('.' + nome.replace(':', '\\:'))
        return re.search(seletor + r'[{:]', app_css) is not None

    utilities_faltando = [u for u in UTILITIES_ESPERADAS if not _utility_compilada(u)]
    assert utilities_faltando == [], (
        f'Utilities esperadas ausentes no app.css — Tailwind não gerou a '
        f'classe (nome errado no template ou token não usado): {utilities_faltando}'
    )

    utilities_dormantes_vazadas = [
        seletor for seletor in UTILITIES_DORMANTES if seletor in app_css
    ]
    assert utilities_dormantes_vazadas == [], (
        f'Utility de token dormente (sem consumidor real em templates) '
        f'apareceu no app.css — provável vazamento do content scan do '
        f'Tailwind (ex. exemplo de classe escrito por extenso em docs/*.md '
        f'ou apps/*/tests/*.py, não excluído via @source not em '
        f'input.css): {utilities_dormantes_vazadas}'
    )
