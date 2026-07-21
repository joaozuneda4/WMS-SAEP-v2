"""Testes diretos da tag {% icon %} e do catálogo vendorizado (sem DB, sem view)."""

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.template import Context, Template

from apps.core.templatetags.core_tags import ICONES_CATALOGO


def _render(tag_call: str, **ctx) -> str:
    template = Template('{% load core_tags %}' + tag_call)
    return template.render(Context(ctx))


@pytest.mark.parametrize('name', sorted(ICONES_CATALOGO))
def test_icon_todo_catalogo_mantem_aria_hidden(name):
    html = _render(f'{{% icon "{name}" %}}')
    assert 'aria-hidden="true"' in html


def test_icon_adicionar_renderiza_path_e_viewbox_originais():
    html = _render('{% icon "adicionar" %}')
    assert (
        'd="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"'
        in html
    )
    assert 'viewBox="0 0 20 20"' in html
    assert 'aria-hidden="true"' in html


def test_icon_repassa_class_verbatim():
    html = _render('{% icon "adicionar" class="h-4 w-4 text-blue-600" %}')
    assert 'class="h-4 w-4 text-blue-600"' in html


def test_icon_nome_fora_do_catalogo_levanta_improperly_configured():
    with pytest.raises(ImproperlyConfigured, match='nao-existe'):
        _render('{% icon "nao-existe" %}')


def test_icon_nome_com_separador_de_caminho_levanta_improperly_configured():
    with pytest.raises(ImproperlyConfigured):
        _render('{% icon "../../etc/passwd" %}')


def test_icon_nome_nao_string_levanta_improperly_configured_em_vez_de_typeerror():
    with pytest.raises(ImproperlyConfigured):
        _render('{% icon nome %}', nome=['adicionar'])


def test_icon_voltar_usa_size_para_width_height_mas_viewbox_fixo_em_24():
    html_default = _render('{% icon "voltar" %}')
    assert 'width="20"' in html_default
    assert 'height="20"' in html_default
    assert 'viewBox="0 0 24 24"' in html_default
    assert (
        'd="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"'
        in html_default
    )

    html_24 = _render('{% icon "voltar" size=24 %}')
    assert 'width="24"' in html_24
    assert 'height="24"' in html_24
    assert 'viewBox="0 0 24 24"' in html_24


def test_icon_voltar_ignora_class_pois_arquivo_nao_referencia_a_variavel():
    html = _render('{% icon "voltar" class="qualquer-coisa" %}')
    assert 'qualquer-coisa' not in html


def test_icon_lixeira_renderiza_path_original_variante_modal_danger():
    html = _render('{% icon "lixeira" class="h-5 w-5" %}')
    assert (
        'd="M8.5 3.5a1.5 1.5 0 0 1 3 0V4H15a1 1 0 1 1 0 2h-1.1l-.5 8.1A2.5 2.5 0 0 1 '
        '10.9 16H9.1a2.5 2.5 0 0 1-2.49-1.9L6.1 6H5a1 1 0 1 1 0-2h3.5v-.5Zm-1.35 8.7.25 '
        '4.05a.5.5 0 0 0 .5.48h2.7a.5.5 0 0 0 .5-.48l.25-4.05H7.15Z"' in html
    )
    assert 'viewBox="0 0 20 20"' in html
    assert 'class="h-5 w-5"' in html
    assert 'aria-hidden="true"' in html


def test_icon_remover_renderiza_path_original_variante_linha_de_item():
    html = _render('{% icon "remover" class="h-4 w-4 shrink-0" %}')
    assert (
        'd="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 '
        '1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 '
        '1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z"' in html
    )
    assert 'viewBox="0 0 20 20"' in html
    assert 'class="h-4 w-4 shrink-0"' in html


def test_icon_enviar_renderiza_path_original():
    html = _render('{% icon "enviar" class="h-4 w-4" %}')
    assert (
        'd="M3.105 3.105a1.5 1.5 0 0 1 1.65-.34l11.5 4.6a1.5 1.5 0 0 1 0 2.78l-11.5 4.6a1.5 '
        '1.5 0 0 1-2.05-1.74l1.21-4.34a.5.5 0 0 1 .39-.36l5.07-.97a.25.25 0 0 0 0-.49L4.41 '
        '6.21a.5.5 0 0 1-.39-.36l-1.21-4.35a1.5 1.5 0 0 1 .3-1.4z"' in html
    )
    assert 'viewBox="0 0 20 20"' in html
    assert 'class="h-4 w-4"' in html


def test_icon_spinner_renderiza_circle_e_path_com_class_repassada():
    html = _render(
        '{% icon "spinner" class="h-4 w-4 animate-spin motion-reduce:animate-none" %}'
    )
    assert (
        '<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"'
        in html
    )
    assert 'd="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"' in html
    assert 'viewBox="0 0 24 24"' in html
    assert 'fill="none"' in html
    assert 'class="h-4 w-4 animate-spin motion-reduce:animate-none"' in html


def test_icon_copiar_renderiza_os_dois_paths_originais():
    html = _render('{% icon "copiar" class="h-4 w-4" %}')
    assert (
        'd="M7 9a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2V9Z"'
        in html
    )
    assert 'd="M5 3a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2V5h8a2 2 0 0 0-2-2H5Z"' in html
    assert 'viewBox="0 0 20 20"' in html
    assert 'class="h-4 w-4"' in html


def test_icon_confirmar_renderiza_path_original():
    html = _render('{% icon "confirmar" class="h-4 w-4 shrink-0" %}')
    assert (
        'd="M16.707 5.293a1 1 010 1.414l-8 8a1 1 01-1.414 0l-4-4a1 1 011.414-1.414L8 '
        '12.586l7.293-7.293a1 1 011.414 0z"' in html
    )
    assert 'viewBox="0 0 20 20"' in html
    assert 'class="h-4 w-4 shrink-0"' in html
    assert 'aria-hidden="true"' in html


def test_icon_confirmar_check_renderiza_path_original():
    html = _render('{% icon "confirmar_check" %}')
    assert (
        'd="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a'
        '.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z"' in html
    )
    assert 'viewBox="0 0 20 20"' in html
    assert 'aria-hidden="true"' in html


def test_icon_estornar_renderiza_path_original():
    html = _render('{% icon "estornar" class="h-4 w-4" %}')
    assert (
        'd="M8.75 1A2.75 2.75 0 0 0 6 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 1 '
        '0 .23 1.482l.149-.022.841 10.518A2.75 2.75 0 0 0 7.596 19h4.807a2.75 2.75 0 0 0 '
        '2.742-2.53l.841-10.519.149.023a.75.75 0 0 0 .23-1.482A41.03 41.03 0 0 0 14 '
        '3.193V3.75A2.75 2.75 0 0 0 11.25 1h-2.5ZM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69'
        '-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4Z'
        'M8.58 7.72a.75.75 0 0 0-1.5.06l.3 7.5a.75.75 0 1 0 1.5-.06l-.3-7.5Zm4.34.06a.75'
        '.75 0 1 0-1.5-.06l-.3 7.5a.75.75 0 1 0 1.5.06l.3-7.5Z"' in html
    )
    assert 'viewBox="0 0 20 20"' in html
    assert 'class="h-4 w-4"' in html
