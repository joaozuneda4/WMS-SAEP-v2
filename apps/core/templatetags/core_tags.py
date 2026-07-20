from typing import Any

from django.core.exceptions import ImproperlyConfigured
from django import template
from django.forms import BoundField
from django.template.loader import render_to_string
from django.utils.safestring import SafeString, mark_safe

register = template.Library()

ICONES_CATALOGO = frozenset(
    {
        'voltar',
        'lixeira',
        'remover',
        'spinner',
        'adicionar',
        'enviar',
        'copiar',
    }
)


@register.simple_tag
def icon(name: str, size: int = 20, **kwargs: str) -> str:
    """Renderiza um ícone do catálogo vendorizado (aria-hidden sempre)."""
    if not isinstance(name, str) or name not in ICONES_CATALOGO:
        raise ImproperlyConfigured(
            f'Ícone "{name}" não está no catálogo (components/icons/). '
            f'Nomes válidos: {sorted(ICONES_CATALOGO)}.'
        )
    css_class = kwargs.get('class', '')
    return mark_safe(
        render_to_string(
            f'components/icons/{name}.svg',
            {'size': size, 'class': css_class},
        )
    )


@register.simple_tag
def validar_contrato_modal(action_url, submit_form_id):
    """Exige exatamente um entre action_url e submit_form_id em components/modal.html."""
    if bool(action_url) == bool(submit_form_id):
        raise ImproperlyConfigured(
            'components/modal.html exige exatamente um entre action_url e '
            'submit_form_id (recebido: '
            f'action_url={action_url!r}, submit_form_id={submit_form_id!r}).'
        )
    return ''


@register.simple_tag
def renderizar_campo_com_aria(
    field: BoundField, tem_ajuda: object = False, tem_erro: object = False
) -> SafeString:
    """Renderiza o BoundField injetando aria-invalid/aria-describedby.

    Único mecanismo do projeto pra passar attrs extras a `{{ field }}` —
    Django não permite isso via linguagem de template pura (chamada de
    método sem argumentos). Usado por components/form_field.html, escopado
    só aos 2 atributos ARIA do contrato do componente. `field.as_widget`
    mescla os attrs recebidos com os automáticos do widget (`required`,
    `class`, `placeholder` etc. definidos em forms.py não são removidos) —
    mas *substitui* attrs com a mesma chave, então um `aria-describedby` já
    definido no widget é preservado explicitamente aqui (concatenado antes
    dos ids de ajuda/erro) em vez de ser sobrescrito.
    """
    attrs: dict[str, str | bool] = {}
    describedby_ids: list[str] = []
    describedby_existente = field.field.widget.attrs.get('aria-describedby')
    if describedby_existente:
        describedby_ids.append(str(describedby_existente))
    if tem_ajuda:
        describedby_ids.append(f'{field.id_for_label}-ajuda')
    if tem_erro:
        describedby_ids.append(f'{field.id_for_label}-erro')
        attrs['aria-invalid'] = 'true'
    if describedby_ids:
        attrs['aria-describedby'] = ' '.join(describedby_ids)
    return field.as_widget(attrs=attrs)


NAVEGACAO: list[dict[str, Any]] = [
    {
        'titulo': 'Requisições',
        'aria_label': 'Requisições',
        'itens': [
            {
                'url_name': 'requisicoes:nova_requisicao',
                'rotulo': 'Nova requisição',
                'icone': 'criar',
                'flag': None,
            },
            {
                'url_name': 'requisicoes:minhas',
                'rotulo': 'Minhas requisições',
                'icone': 'lista',
                'flag': None,
            },
            {
                'url_name': 'requisicoes:autorizacoes',
                'rotulo': 'Fila de autorizações',
                'icone': 'autorizacao',
                'flag': 'pode_ver_fila_autorizacao',
            },
            {
                'url_name': 'requisicoes:historico',
                'rotulo': 'Histórico de requisições',
                'icone': 'historico',
                'flag': 'pode_consultar_historico_requisicoes',
            },
        ],
    },
    {
        'titulo': 'Almoxarifado',
        'aria_label': 'Almoxarifado',
        'itens': [
            {
                'url_name': 'requisicoes:atendimentos',
                'rotulo': 'Atendimento',
                'icone': 'atendimento',
                'flag': 'pode_ver_fila_atendimento',
            },
            {
                'url_name': 'estoque:listar_saidas_excepcionais',
                'rotulo': 'Saídas excepcionais',
                'icone': 'saida',
                'flag': 'pode_consultar_saidas_excepcionais',
            },
            {
                'url_name': 'estoque:lista_materiais',
                'rotulo': 'Catálogo de materiais',
                'icone': 'catalogo',
                'flag': 'pode_consultar_catalogo_estoque',
            },
            {
                'url_name': 'estoque:historico_movimentacoes',
                'rotulo': 'Movimentações',
                'icone': 'movimentacao',
                'flag': 'pode_consultar_movimentacoes_estoque',
            },
            {
                'url_name': 'estoque:preview_importacao_scpi',
                'rotulo': 'Importar SCPI',
                'icone': 'importar',
                'flag': 'pode_visualizar_preview_scpi',
                'url_names_ativos': [
                    'estoque:preview_importacao_scpi',
                    'requisicoes:confirmar_importacao_scpi',
                    'estoque:sucesso_importacao_scpi',
                ],
            },
            {
                'url_name': 'estoque:historico_importacoes_scpi',
                'rotulo': 'Histórico de importações SCPI',
                'icone': 'historico',
                'flag': 'pode_consultar_historico_scpi',
            },
        ],
    },
]

ICONES: dict[str, str] = {
    'criar': 'M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z',
    'lista': 'M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z',
    'autorizacao': (
        'M12 2 4 5v6c0 5.55 3.84 10.74 8 12 4.16-1.26 8-6.45 8-12V5l-8-3zm-1 14'
        '-4-4 1.41-1.41L11 13.17l5.59-5.59L18 9l-7 7z'
    ),
    'historico': 'M13 3a9 9 0 1 0 9 9h-2a7 7 0 1 1-7-7v4l5-5-5-5v4z',
    'atendimento': (
        'M20 8h-3V6c0-1.1-.9-2-2-2H9c-1.1 0-2 .9-2 2v2H4c-1.1 0-2 .9-2 2v9c0 1.1'
        '.9 2 2 2h16c1.1 0 2-.9 2-2v-9c0-1.1-.9-2-2-2zM9 6h6v2H9V6zm11 13H4v-2h16'
        'v2zm0-4H4v-5h3v2h2v-2h6v2h2v-2h3v5z'
    ),
    'saida': (
        'M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2'
        '-2-2zm-7 14l-5-5 1.41-1.41L12 14.17l7.59-7.59L21 8l-9 9z'
    ),
    'catalogo': (
        'M20 3H4v2h16V3zm1 5H3l1 13h16l1-13zm-5 7h-3v3h-2v-3H8v-2h3V10h2v3h3v2z'
    ),
    'movimentacao': (
        'M3 13h2v-2H3v2zm0 4h2v-2H3v2zm0-8h2V7H3v2zm4 4h14v-2H7v2zm0 4h14v-2H7'
        'v2zM7 7v2h14V7H7z'
    ),
    'importar': 'M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z',
}


@register.simple_tag(takes_context=True)
def secoes_navegacao(context: Any) -> list[dict[str, Any]]:
    """Devolve as seções de nav visíveis, lidas de NAVEGACAO/ICONES.

    Filtra itens pela flag de permissão já presente no contexto (sem
    reimplementar policy) e descarta seções sem nenhum item visível.
    Constrói dicts/listas novos a cada chamada — nunca muta NAVEGACAO/ICONES.
    """
    secoes: list[dict[str, Any]] = []
    for secao in NAVEGACAO:
        itens: list[dict[str, Any]] = []
        for item in secao['itens']:
            flag = item.get('flag')
            if flag is not None and not context.get(flag):
                continue
            itens.append(
                {
                    'url_name': item['url_name'],
                    'rotulo': item['rotulo'],
                    'icone_path': ICONES[item['icone']],
                    'url_names_ativos': list(
                        item.get('url_names_ativos', [item['url_name']])
                    ),
                }
            )
        if itens:
            secoes.append(
                {
                    'titulo': secao['titulo'],
                    'aria_label': secao['aria_label'],
                    'itens': itens,
                }
            )
    return secoes
