# Plano — #7 Filtros via HTMX no histórico de movimentações

> Origem: US-17 + `.design/movimentacoes-estoque/DESIGN_BRIEF.md` e `TASKS.md`.
> Bloqueado por #6 (já mergeado — tela base `/estoque/movimentacoes/` existe).

## Scope

### O que muda
- **Novo selector** `estoque/selectors.py::filtrar_movimentacoes(qs, *, material, tipos, data_ini, data_fim, setor)`:
  estreita o queryset **já escopado** por `movimentacoes_visiveis_para`. Filtro nunca
  amplia o universo visível (aplica `AND` sobre o `qs` recebido).
  - `material`: `str | None` → `Q(material__codigo__icontains) | Q(material__nome__icontains)`.
  - `tipos`: `list[str]` → `tipo__in`, somente se a lista não-vazia; valores fora de
    `TipoMovimentacaoEstoque` são descartados (sanitização no selector).
  - `data_ini` / `data_fim`: `date | None` → `criado_em__date__gte` / `criado_em__date__lte`
    (período **inclusivo** sobre o dia).
  - `setor`: `int | None` → `requisicao__setor_beneficiario_id`. Como o `qs` de entrada já
    está escopado, chefe de setor passando `setor` de outro setor resulta em vazio (não vaza).
- **View** `historico_movimentacoes_view`: passa a ler a querystring, sanitizar, chamar
  `filtrar_movimentacoes`, aplicar ordenação, paginar, e detectar requisição HTMX para
  devolver só o partial da tabela. Novas chaves de contexto: `filtros` (valores ativos),
  `mostrar_filtro_setor` (= `_eh_almoxarifado`), `setores_disponiveis`, `tipos_opcoes`,
  `ordem`, `tem_filtro_ativo`, `so_saidas_ativo`.
  - **Contrato de chamada (ADR-0011/CONVENTIONS.md)**: a view chama o selector de
    visibilidade por **ID** — `movimentacoes_visiveis_para(request.user.pk)` — e nunca passa
    o objeto `user` ao selector. `mostrar_filtro_setor` deriva de `_eh_almoxarifado(request.user)`.
    Policies (`exigir_pode_consultar_movimentacoes_estoque`) recebem o objeto `user` conforme
    o padrão vigente do projeto; a view traduz `PermissaoNegada` → `PermissionDenied` (403).
    Se a implementação divergir deste contrato, sinalizar explicitamente conforme CONVENTIONS.md.
- **Ordenação**: tratada na **view** via querystring `?ordem=asc|desc` (default `desc`).
  Decisão: mantém a assinatura do selector exatamente como especificada na issue (sem
  `ordem`); ordenação é responsabilidade da view (`order_by`). Selector permanece filtro puro.
- **Filtro de setor**: campo renderizado SOMENTE quando `mostrar_filtro_setor` (almoxarifado).
- **Templates**:
  - Extrair tabela+paginação para `partials/_tabela_movimentacoes.html` (alvo do swap HTMX),
    com `aria-live="polite" aria-atomic="true"` no contêiner de resultados — contrato completo
    de `docs/design-system.md` (linha 267: updates HTMX críticos usam ambos os atributos).
  - Barra de filtros (form GET) em `historico_movimentacoes.html`: busca de material, multi-
    seleção de tipo, período (data ini/fim), setor (condicional). Submete via HTMX GET com
    `hx-push-url`, troca só o partial, reseta para página 1.
  - Chip "só saídas": seta tipo = `consumo` + `saida_excepcional` num clique; estado ativo visível.
  - Header de data clicável: alterna `?ordem=` asc↔desc, com `aria-sort` e indicador visual.
  - Empty state contextual: distingue "nenhum resultado para este filtro" de "ledger vazio".
- **HTMX**: o projeto **não** usa `django-htmx` (sem `request.htmx`). Detecção via
  `request.headers.get('HX-Request') == 'true'`. Partial preserva querystring na paginação.

### O que NÃO muda
- `movimentacoes_visiveis_para` (RBAC) — fronteira de segurança intacta; filtro só estreita.
- Modelos, migrations, contrato de policies (`exigir_pode_consultar_movimentacoes_estoque`).
- Nada de agregação/métrica/export/deep-links (fora de escopo no brief).
- Partials `_badge_tipo_movimentacao.html`, `_delta_movimentacao.html` (reuso).

## Files touched

| Arquivo | Ação |
| --- | --- |
| `apps/estoque/selectors.py` | + `filtrar_movimentacoes` (após `movimentacoes_visiveis_para`) |
| `apps/estoque/views.py` | reescrever corpo de `historico_movimentacoes_view` (parse/sanitize/filtro/ordem/HTMX) |
| `apps/estoque/templates/estoque/historico_movimentacoes.html` | + barra de filtros, chip, header ordenável, include do partial |
| `apps/estoque/templates/estoque/partials/_tabela_movimentacoes.html` | **novo** — tabela+cards+paginação (swap target) |
| `apps/estoque/templates/estoque/partials/_paginacao.html` | preservar querystring nos links `?page=` |
| `apps/estoque/tests/test_selectors.py` | + `TestFiltrarMovimentacoes` |
| `apps/estoque/tests/test_views.py` | + testes de filtro/HTMX/ordem/setor na view |
| `.design/INFORMATION_ARCHITECTURE.md` | registrar rota/nav (se ainda não) |

## Test strategy

### Selector (`TestFiltrarMovimentacoes`) — sobre qs de `movimentacoes_visiveis_para`
- **Material**: filtra por `codigo` icontains; por `nome` icontains; case-insensitive; `None`/`''` → no-op.
- **Tipos**: lista única; lista múltipla (`tipo__in`); lista vazia → no-op; valor inválido descartado.
- **Período**: `data_ini` inclusivo; `data_fim` inclusivo (mesmo dia entra); intervalo combinado; `None` → no-op.
- **Setor**: filtra por setor; combinação com outros filtros.
- **Não-ampliação (segurança)**: chefe de setor — `filtrar_movimentacoes(visiveis_chefe, setor=<outro_setor>)`
  retorna vazio (não vaza dado de outro setor via querystring).
- **Combinados**: material + tipos + período aplicados juntos.

### View — contrato HTTP/render
- **Happy path**: querystring com filtros reflete na contagem de `page_obj`.
- **Permissão negada**: solicitante → 403 (já coberto; manter).
- **HTMX**: header `HX-Request: true` devolve só o partial `_tabela_movimentacoes.html`
  (não o template completo com app-bar).
- **Reset de página**: aplicar filtro novo volta para página 1.
- **Ordenação**: `?ordem=asc` inverte; default `desc`; mantém demais filtros.
- **Filtro de setor por papel**: contexto `mostrar_filtro_setor` True p/ almox, False p/ chefe de setor.
- **Querystring inválida não quebra**: `?ordem=lixo`, `?tipos=inexistente`, `?data_ini=abc`,
  `?setor=abc` → 200, sem 500.
- **Empty state contextual**: com filtro sem resultado → mensagem de filtro; sem filtro e
  ledger vazio → mensagem de ledger vazio.
- **Chip só saídas**: querystring `tipos=consumo&tipos=saida_excepcional` marca estado ativo no contexto.

## Invariants (matriz)
- **RBAC é fronteira no selector** — filtro nunca amplia universo visível; setor jamais vê
  dado de outro setor por manipular a URL (Experience Principle 2 do brief).
- **Ledger imutável / append-only** — tela estritamente leitura; nenhuma mutação.
- **Exatamente uma origem por linha** (requisição XOR saída excepcional) — preservado no render.

## Risks
- **Sanitização de querystring**: entradas livres (datas, ints, tipos) precisam degradar para
  no-op sem 500. Mitigado por parsing defensivo na view + testes de querystring inválida.
- **HTMX sem django-htmx**: detecção manual por header `HX-Request`. Risco de o partial não
  incluir querystring na paginação → links quebram o recorte. Mitigado preservando querystring
  no `_paginacao.html` e teste de paginação com filtro ativo.
- **Não-ampliação do filtro de setor**: risco de vazamento se o filtro fosse aplicado sobre
  qs não-escopado. Mitigado por contrato (recebe qs já escopado) + teste de vazamento.
- **Sem mudança de schema** — fluxo incremental, sem reset de migrations.

## TDD order (vertical slices)
1. `filtrar_movimentacoes` — material → tipos → período → setor → não-ampliação (RED→GREEN cada).
2. View: parse+filtro+contexto → ordenação → HTMX partial → querystring inválida → empty state contextual.
3. Frontend: partial extraído → barra de filtros HTMX → chip só saídas → header ordenável → empty state → responsivo → a11y.
4. Suíte completa + ruff + mypy verdes.
