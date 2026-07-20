"""Testes diretos de components/badge.html (sem DB, sem view)."""

import pytest
from django.template.loader import render_to_string


def _render(**ctx):
    ctx.setdefault('variant', 'slate')
    ctx.setdefault('label', 'Rótulo')
    return render_to_string('components/badge.html', ctx)


@pytest.mark.parametrize(
    'variant,classes_esperadas',
    [
        ('slate', ['bg-bg-subtle', 'text-text-primary', 'ring-border']),
        (
            'blue',
            ['bg-primary-muted', 'text-primary-text-strong', 'ring-primary-border'],
        ),
        (
            'blue-strong',
            [
                'bg-primary-muted-strong',
                'text-primary-text-strong',
                'ring-primary-border-strong',
            ],
        ),
        (
            'amber',
            ['bg-warning-muted', 'text-warning-text-strong', 'ring-warning-border'],
        ),
        (
            'amber-strong',
            [
                'bg-warning-muted-strong',
                'text-warning-text-strong',
                'ring-warning-border-strong',
            ],
        ),
        (
            'green',
            ['bg-success-muted', 'text-success-text-strong', 'ring-success-border'],
        ),
        ('red', ['bg-danger-muted', 'text-danger-text-strong', 'ring-danger-border']),
        (
            'red-strong',
            [
                'bg-danger-muted-strong',
                'text-danger-text-strong',
                'ring-danger-border-strong',
            ],
        ),
        ('teal', ['bg-return-muted', 'text-return-text-strong', 'ring-return-border']),
        # Fora do mapeamento da issue #86 — permanecem cru de propósito.
        ('orange', ['bg-orange-100', 'text-orange-900', 'ring-orange-200']),
        ('indigo', ['bg-indigo-100', 'text-indigo-900', 'ring-indigo-200']),
        ('violet', ['bg-violet-100', 'text-violet-900', 'ring-violet-200']),
        ('yellow', ['bg-yellow-100', 'text-yellow-900', 'ring-yellow-200']),
    ],
)
def test_variant_produz_classes_de_cor_esperadas(variant, classes_esperadas):
    html = _render(variant=variant)
    for classe in classes_esperadas:
        assert classe in html


def test_label_e_renderizado():
    html = _render(label='Autorizada')
    assert 'Autorizada' in html


def test_variant_desconhecida_cai_no_fallback_indisponivel():
    html = _render(variant='estado-que-nao-existe')
    assert 'bg-danger' in html
    assert 'ring-danger-hover' in html
    assert 'Indisponível' in html


def test_role_e_propagado_literalmente():
    html = _render(variant='blue', role='status')
    assert 'role="status"' in html


def test_role_ausente_por_padrao():
    html = _render()
    assert 'role=' not in html


def test_aria_label_e_propagado_literalmente():
    html = _render(variant='red', aria_label='Estado: Recusada')
    assert 'aria-label="Estado: Recusada"' in html


def test_aria_label_ausente_por_padrao():
    html = _render()
    assert 'aria-label=' not in html


def test_todas_as_variantes_de_marca_mantem_rounded_full_pill():
    for variant in ['slate', 'blue', 'amber', 'green', 'red', 'teal']:
        html = _render(variant=variant)
        assert 'rounded-full' in html
