"""Testes diretos de components/alert.html (sem DB, sem view)."""

import copy
from pathlib import Path

import pytest
from django.conf import settings
from django.template.loader import render_to_string
from django.test import override_settings

FIXTURES_DIR = Path(__file__).resolve().parent / 'fixtures'


def _templates_com_fixtures():
    templates = copy.deepcopy(settings.TEMPLATES)
    templates[0]['DIRS'] = [FIXTURES_DIR, *templates[0].get('DIRS', [])]
    return templates


com_fixture_body_template = override_settings(TEMPLATES=_templates_com_fixtures())


def _render(**ctx):
    ctx.setdefault('message', 'Mensagem de teste')
    return render_to_string('components/alert.html', ctx)


def test_variant_padrao_info_usa_role_status():
    html = _render()
    assert 'role="status"' in html
    assert 'border-primary-border' in html
    assert 'bg-primary-subtle' in html
    assert 'text-primary-text-emphasis' in html


@pytest.mark.parametrize(
    'variant,role_esperado,classes_esperadas',
    [
        (
            'success',
            'status',
            [
                'border-success-border',
                'bg-success-subtle',
                'text-success-text-emphasis',
            ],
        ),
        (
            'warning',
            'alert',
            ['border-warning-border', 'bg-warning-subtle', 'text-warning-text'],
        ),
        (
            'danger',
            'alert',
            ['border-danger-border', 'bg-danger-subtle', 'text-danger-text-emphasis'],
        ),
    ],
)
def test_variante_define_role_e_cor(variant, role_esperado, classes_esperadas):
    html = _render(variant=variant)
    assert f'role="{role_esperado}"' in html
    for classe in classes_esperadas:
        assert classe in html


def test_role_override_sobrescreve_padrao_da_variante():
    html = _render(variant='warning', role='note')
    assert 'role="note"' in html
    assert 'role="alert"' not in html


def test_icone_e_exibido_por_padrao():
    html = _render()
    assert '<svg' in html


def test_icone_false_oculta_svg():
    html = _render(icone=False)
    assert '<svg' not in html


def test_message_e_autoescapado():
    html = _render(message='<script>alert(1)</script>')
    assert '<script>' not in html
    assert '&lt;script&gt;' in html


@com_fixture_body_template
def test_body_template_inclui_conteudo_e_herda_contexto():
    html = render_to_string(
        'components/alert.html',
        {
            'variant': 'danger',
            'icone': False,
            'body_template': '_fixture_teste_body_template.html',
            'valor_herdado': 'valor-vindo-do-contexto-do-chamador',
        },
    )
    assert '<svg' not in html
    assert 'data-fixture-heranca-contexto' in html
    assert 'valor-vindo-do-contexto-do-chamador' in html


@com_fixture_body_template
def test_body_template_sem_message_nao_exige_message():
    html = render_to_string(
        'components/alert.html',
        {
            'variant': 'warning',
            'body_template': '_fixture_teste_body_template.html',
            'valor_herdado': 'valor-sem-message',
        },
    )
    assert 'data-fixture-heranca-contexto' in html
    assert 'valor-sem-message' in html


@com_fixture_body_template
def test_body_template_tem_precedencia_sobre_message():
    html = render_to_string(
        'components/alert.html',
        {
            'message': 'mensagem que nao deveria aparecer',
            'body_template': '_fixture_teste_body_template.html',
            'valor_herdado': 'valor-do-body-template',
        },
    )
    assert 'mensagem que nao deveria aparecer' not in html
    assert 'valor-do-body-template' in html


def test_class_passthrough_e_mesclado_nao_substitui_invariantes():
    html = _render(**{'class': 'meu-ajuste-customizado'})
    assert 'meu-ajuste-customizado' in html
    assert 'rounded-lg' in html
    assert 'px-4 py-3' in html


def test_aria_live_ausente_por_padrao():
    html = _render()
    assert 'aria-live' not in html


def test_aria_live_explicito_renderiza_atributo():
    html = _render(aria_live='assertive')
    assert 'aria-live="assertive"' in html


def test_id_ausente_por_padrao():
    html = _render()
    assert ' id=' not in html


def test_id_explicito_renderiza_atributo():
    html = _render(id='aviso-duplicidade')
    assert 'id="aviso-duplicidade"' in html


def test_message_vazia_sem_body_template_renderiza_casca_valida():
    html = render_to_string(
        'components/alert.html',
        {
            'variant': 'danger',
            'icone': False,
            'id': 'aviso-duplicidade',
            'aria_live': 'assertive',
            'message': '',
            'class': 'hidden',
        },
    )
    assert 'id="aviso-duplicidade"' in html
    assert 'hidden' in html
    assert 'role="alert"' in html
