"""Testes diretos de {% renderizar_campo_com_aria %} (sem DB, sem view)."""

from django import forms
from django.template import Context, Template


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
