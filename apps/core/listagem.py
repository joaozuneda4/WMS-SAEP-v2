"""Helper de paginação/ordenação/metadados para telas de histórico.

Infraestrutura de apresentação pura (ADR-0011): não importa policies,
services nem selectors de domínio. A view continua chamando `exigir_pode_*`
(policies.py) e os selectors de filtro (`filtrar_*`) exatamente como hoje —
este módulo não decide autorização nem filtra domínio, só recebe o queryset
já autorizado/filtrado pela view e cuida de ordenar, paginar e montar os
metadados de apresentação (URL de ordenação, aria-sort, querystring,
flag HTMX).
"""

from __future__ import annotations

from dataclasses import dataclass

from django.core.paginator import Page, Paginator
from django.db.models import QuerySet

from apps.core.http import HtmxHttpRequest, querystring_sem_page


@dataclass(frozen=True)
class ResultadoListagem:
    """Chaves de contexto comuns às telas de histórico paginadas/ordenáveis."""

    page_obj: Page
    ordem: str
    aria_sort: str
    url_ordenacao: str
    querystring_filtros: str
    is_htmx: bool


def paginar_com_filtros(
    request: HtmxHttpRequest, queryset: QuerySet, *, per_page: int
) -> ResultadoListagem:
    """Ordena por `criado_em` (via `?ordem=`), pagina e monta os metadados
    comuns de listagem (URL de ordenação, aria-sort, querystring de filtros,
    flag HTMX). Fora daqui: permissão, parsing de filtros de domínio, chamada
    de selectors — responsabilidade da view (ADR-0011).
    """
    ordem = 'asc' if request.GET.get('ordem') == 'asc' else 'desc'
    campos_ordenacao = ('criado_em', 'pk') if ordem == 'asc' else ('-criado_em', '-pk')
    queryset = queryset.order_by(*campos_ordenacao)

    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(request.GET.get('page'))

    ordem_inversa = 'asc' if ordem == 'desc' else 'desc'
    params_ordenacao = request.GET.copy()
    params_ordenacao.pop('page', None)
    params_ordenacao['ordem'] = ordem_inversa
    url_ordenacao = '?' + params_ordenacao.urlencode()

    return ResultadoListagem(
        page_obj=page_obj,
        ordem=ordem,
        aria_sort='ascending' if ordem == 'asc' else 'descending',
        url_ordenacao=url_ordenacao,
        querystring_filtros=querystring_sem_page(request.GET),
        is_htmx=bool(request.htmx),
    )
