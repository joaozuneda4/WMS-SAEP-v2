# Plano — Issue #84: helper `paginar_com_filtros` nas 2 views de histórico

Epic: #68. Bloqueador #74 (`apps/core/http.py`) — `CLOSED`, `htmx_redirect`,
`parse_data_iso`, `querystring_sem_page` e `HtmxHttpRequest` já existem em
`apps/core/http.py`.

## Escopo

**Entra:**
- `apps/core/listagem.py` novo — função `paginar_com_filtros(request, queryset, *, per_page)`
  + dataclass `ResultadoListagem` com as chaves comuns extraídas.
- Refatoração de `historico_requisicoes_view` (`apps/requisicoes/views.py:1135-1222`) e
  `historico_movimentacoes_view` (`apps/estoque/views.py:89-187`) para usar o helper.
- Testes unitários do helper em `apps/core/tests/test_listagem.py`.

**Não entra (conforme a issue):**
- Unificar templates dos 2 históricos.
- Tocar em selectors, services ou policies.
- CBV/mixin genérico — helper é função pura (projeto é FBV por convenção).
- `so_saidas_ativo`, `url_chip_so_saidas`, `url_chip_sem_so_saidas` (chip de saídas do
  ledger de estoque) — específico de domínio, fica na view.

## O que o helper encapsula

Investigação prévia (Serena, ambas as views lidas por completo) confirma que o trecho é
~95% idêntico entre as duas views:

1. `ordem = 'asc' if request.GET.get('ordem') == 'asc' else 'desc'` (fallback seguro p/
   valor inválido, ex. `?ordem=lixo`).
2. `queryset.order_by('criado_em' if ordem == 'asc' else '-criado_em')`.
3. `Paginator(queryset, per_page)` + `paginator.get_page(request.GET.get('page'))`.
4. `url_ordenacao`: querystring atual sem `page`, com `ordem` invertida.
5. `aria_sort`: `'ascending'` / `'descending'`.
6. `querystring_filtros`: via `apps.core.http.querystring_sem_page` (já existe, #74).
7. `is_htmx`: via `request.htmx` (já em uso nas 2 views).

### Verificação de não-regressão na ordenação (ponto de atenção real)

`estoque/views.py` hoje só chama `.order_by('criado_em')` quando `ordem == 'asc'`; no caso
`desc` (default) não há `order_by` explícito na view. `requisicoes/views.py` já aplica
`order_by` explícito nos dois casos. Investigação nos selectors confirma que isso é seguro
de unificar:

- `MovimentacaoEstoque.Meta.ordering = ('criado_em',)` (asc puro) —
  `apps/estoque/models.py:443`.
- Mas `movimentacoes_visiveis_para` (`apps/estoque/selectors.py:311-350`) já aplica
  `.order_by('-criado_em')` explícito em todos os ramos do `base_qs`, sobrescrevendo o
  `Meta.ordering` do model. `filtrar_movimentacoes` não reordena.
- `historico_requisicoes_visiveis_para` (`apps/requisicoes/selectors.py:266-309`) faz o
  mesmo: `order_by('-criado_em')` explícito no `base_qs`.

Ou seja: em ambos os apps o queryset que chega na view **já vem ordenado por
`-criado_em`** antes de qualquer `order_by` da view. O helper aplicando
`order_by('criado_em' if asc else '-criado_em')` incondicionalmente nos dois casos é,
portanto, um no-op no caso `desc` do estoque (reordenar um qs já ordenado por
`-criado_em` com o mesmo critério não muda nada) — **zero mudança de contrato**. Coberto
pelo teste existente `test_ordenacao_asc_inverte_cronologia` (ambos os apps), que já
roda no CI e não deve mudar.

## Assinatura e design

```python
# apps/core/listagem.py
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

from django.core.paginator import Page
from django.core.paginator import Paginator
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
    queryset = queryset.order_by('criado_em' if ordem == 'asc' else '-criado_em')

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
        is_htmx=request.htmx,
    )
```

## Arquivos tocados

| Arquivo | Mudança |
|---|---|
| `apps/core/listagem.py` | **Novo.** `ResultadoListagem` + `paginar_com_filtros`. |
| `apps/core/tests/test_listagem.py` | **Novo.** Testes unitários do helper (`pytest.mark.django_db`, queryset real). |
| `apps/requisicoes/views.py` | `historico_requisicoes_view` encolhe: chama o helper, mantém `exigir_pode_consultar_historico_requisicoes`, parsing de filtros de domínio, `filtrar_historico_requisicoes`, `tem_filtro_ativo`, `setores_disponiveis`. |
| `apps/estoque/views.py` | `historico_movimentacoes_view` encolhe: chama o helper, mantém `exigir_pode_consultar_movimentacoes_estoque`, parsing de filtros, `filtrar_movimentacoes`, `tem_filtro_ativo`, `so_saidas_ativo` + URLs de chip. |

Nenhum arquivo de `selectors`, `policies`, `services`, `models` ou template é tocado —
zero mudança de contrato HTTP (mesmos templates escolhidos, mesmas chaves de contexto,
mesma semântica de `?ordem=`/`?page=`/filtros).

## Estratégia de testes

Conforme ADR-0010 (camadas de teste):

1. **Unitário do helper** (`apps/core/tests/test_listagem.py`, `@pytest.mark.django_db`,
   queryset real — sem mock/fake). Usa fixtures já existentes de
   `apps/core/tests/conftest.py` (`setor_comum`, `solicitante`) para criar registros de
   `apps.accounts.models.VinculoAuxiliar` (tem `criado_em`, é o model mais simples do
   projeto com esse campo, sem depender de domínio de estoque/requisições) e
   `RequestFactory` para montar a `HttpRequest` (padrão já usado em
   `apps/core/tests/test_http.py::_htmx_request`, com `request.htmx` setado manualmente).
   Cenários:
   - ordem default `desc` quando `?ordem=` ausente ou inválido (`?ordem=lixo`) —
     `VinculoAuxiliar.objects.all()` sem `order_by` prévio, criados em sequência,
     paginado pelo helper deve sair em ordem decrescente de `criado_em`;
   - `?ordem=asc` inverte a ordenação e reflete em `ResultadoListagem.ordem`;
   - `url_ordenacao` preserva demais parâmetros da querystring e remove `page`;
   - `aria_sort` corresponde a `ordem`;
   - `is_htmx` reflete `request.htmx` (`True`/`False`);
   - `page_obj` pagina corretamente com `per_page` customizado (`count`/`has_next`).
2. **Views de histórico (regressão)**: suíte existente
   (`TestHistoricoRequisicoesView`, `TestHistoricoRequisicoesFiltros`,
   `TestHistoricoMovimentacoesView`, `TestHistoricoMovimentacoesFiltros`) deve
   permanecer verde **sem alteração** — inclui `test_ordenacao_asc_inverte_cronologia`
   (ambos os apps; asserta `asc == reversed(desc)`, portanto já cobre o caso `desc`
   padrão do estoque implicitamente), `test_paginacao_server_side`,
   `test_querystring_invalida_nao_quebra`, `test_chip_so_saidas_preserva_filtros_atuais`.
   Combinado com o cenário 1 acima (que testa `desc` explicitamente no helper, isolado da
   view), o caso `desc` padrão do estoque fica coberto tanto no nível do helper quanto no
   nível de regressão da view — nenhum teste novo de view é necessário. Se algum teste de
   view precisar mudar, é sinal de regressão (conforme critério de aceite da issue).

## Invariantes relevantes (`docs/matriz-invariantes.md`)

- RBAC de histórico: autorização continua 100% delegada às policies
  (`exigir_pode_consultar_historico_requisicoes` / `exigir_pode_consultar_movimentacoes_estoque`,
  `policies.py`, ADR-0011) — a view só chama a policy, não implementa regra própria; o
  helper não decide autorização, não recebe `request.user`, só recebe o queryset já
  autorizado e devolve página/ordenação.
- Escopo por setor (`setor_beneficiario`): aplicado inteiramente pelos selectors
  (`historico_requisicoes_visiveis_para` / `movimentacoes_visiveis_para`, que já escopam
  por setor do ator) — não tocado, não duplicado na view, não visível ao helper.
- Contrato PRG + HX-Redirect — não tocado (histórico é `@require_GET`, não usa PRG).

## Riscos

- **Baixo.** Sem concorrência, sem mutação de estoque, sem transição de estado, sem
  mudança de contrato OpenAPI (projeto não tem API REST). Único risco real —
  ordenação `desc` do estoque sem `order_by` explícito hoje — investigado e mitigado
  acima (no-op confirmado via leitura dos selectors).
- Import cycle: `apps/core/listagem.py` importa de `apps/core/http.py` (mesma app,
  sem risco de ciclo).

## Guardrails

- ADR-0011: helper é infraestrutura de apresentação — proibido importar
  policies/services/selectors de domínio. Autorização (policies) e escopo/visibilidade
  (selectors) não migram para o helper nem para a view: continuam exatamente onde estão
  hoje, chamadas explicitamente pela view (padrão pré-existente, inalterado por este
  refactor).
- Escopo fechado: 1 módulo novo + 1 arquivo de teste novo + 2 views.
- Zero dependência nova.
- Branch: `refactor/helper-paginar-com-filtros`.
- Suíte + `ruff format`/`ruff check` + `mypy apps` verdes antes do PR final.
- PT-BR em identificadores de domínio, docstrings e comentários.
