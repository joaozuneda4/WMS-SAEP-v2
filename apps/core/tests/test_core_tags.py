"""Testes diretos de {% renderizar_campo_com_aria %} (sem DB, sem view)."""

from decimal import Decimal

import pytest
from django import forms
from django.template import Context, Template

from apps.core.templatetags.core_tags import formatar_quantidade


class _FormDeTeste(forms.Form):
    nome = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'class': 'minha-classe', 'placeholder': 'Nome'}),
    )
    apelido = forms.CharField(required=False)


def _render(tag_call: str, **ctx) -> str:
    template = Template('{% load core_tags %}' + tag_call)
    return template.render(Context(ctx))


def test_sem_ajuda_sem_erro_nao_adiciona_aria():
    form = _FormDeTeste()
    html = _render('{% renderizar_campo_com_aria field %}', field=form['nome'])
    assert 'aria-invalid' not in html
    assert 'aria-describedby' not in html


def test_com_ajuda_adiciona_describedby_ajuda():
    form = _FormDeTeste()
    html = _render(
        '{% renderizar_campo_com_aria field tem_ajuda=True %}', field=form['nome']
    )
    assert f'aria-describedby="{form["nome"].id_for_label}-ajuda"' in html
    assert 'aria-invalid' not in html


def test_com_erro_adiciona_aria_invalid_e_describedby_erro():
    form = _FormDeTeste(data={})
    form.is_valid()
    html = _render(
        '{% renderizar_campo_com_aria field tem_erro=field.errors %}',
        field=form['nome'],
    )
    assert 'aria-invalid="true"' in html
    assert f'aria-describedby="{form["nome"].id_for_label}-erro"' in html


def test_com_ajuda_e_erro_compoe_os_dois_ids_em_ordem():
    form = _FormDeTeste(data={})
    form.is_valid()
    html = _render(
        '{% renderizar_campo_com_aria field tem_ajuda=True tem_erro=field.errors %}',
        field=form['nome'],
    )
    id_campo = form['nome'].id_for_label
    assert f'aria-describedby="{id_campo}-ajuda {id_campo}-erro"' in html


def test_preserva_attrs_nativos_do_widget():
    form = _FormDeTeste()
    html = _render('{% renderizar_campo_com_aria field %}', field=form['nome'])
    assert 'minha-classe' in html
    assert 'placeholder="Nome"' in html
    assert 'required' in html


def test_campo_opcional_nao_tem_required_nativo():
    form = _FormDeTeste()
    html = _render('{% renderizar_campo_com_aria field %}', field=form['apelido'])
    assert 'required' not in html


class _FormComDescribedbyNoWidget(forms.Form):
    campo = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'aria-describedby': 'hint-externo'}),
    )


def test_preserva_aria_describedby_ja_definido_no_widget():
    form = _FormComDescribedbyNoWidget()
    html = _render('{% renderizar_campo_com_aria field %}', field=form['campo'])
    assert 'aria-describedby="hint-externo"' in html


def test_compoe_aria_describedby_do_widget_com_ajuda_e_erro():
    form = _FormComDescribedbyNoWidget(data={})
    form.is_valid()
    html = _render(
        '{% renderizar_campo_com_aria field tem_ajuda=True tem_erro=field.errors %}',
        field=form['campo'],
    )
    id_campo = form['campo'].id_for_label
    assert f'aria-describedby="hint-externo {id_campo}-ajuda {id_campo}-erro"' in html


@pytest.mark.parametrize(
    'qtd, unidade, esperado',
    [
        # Unidade → inteiro
        (Decimal('5.000'), 'un', '5'),
        (Decimal('1.000'), 'un', '1'),
        (Decimal('100.000'), 'un', '100'),
        # kg → 1 decimal
        (Decimal('2.500'), 'kg', '2.5'),
        (Decimal('10.000'), 'kg', '10.0'),
        (Decimal('0.100'), 'kg', '0.1'),
        # l → 1 decimal
        (Decimal('3.000'), 'l', '3.0'),
        (Decimal('1.500'), 'l', '1.5'),
        # m → 1 decimal
        (Decimal('4.200'), 'm', '4.2'),
        (Decimal('10.000'), 'm', '10.0'),
        # m2 → strip trailing zeros (casas significativas)
        (Decimal('2.000'), 'm2', '2'),
        (Decimal('1.500'), 'm2', '1.5'),
        (Decimal('1.230'), 'm2', '1.23'),
        # cx, pct, par, rolo → strip trailing zeros
        (Decimal('3.000'), 'cx', '3'),
        (Decimal('2.500'), 'pct', '2.5'),
        (Decimal('1.000'), 'par', '1'),
        (Decimal('6.000'), 'rolo', '6'),
        # None → fallback
        (None, 'un', '—'),
        (None, 'kg', '—'),
    ],
)
def test_formatar_quantidade(qtd, unidade, esperado):
    assert formatar_quantidade(qtd, unidade) == esperado
