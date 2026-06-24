# Plano de implementação — Issue #6

**Movimentações de estoque: ledger navegável por papel, paginado**

> Origem: US-17 + `.design/movimentacoes-estoque/DESIGN_BRIEF.md` e `TASKS.md`.
> RBAC espelha `apps/requisicoes/selectors.py::requisicoes_visiveis_para`.

## Scope

Tela de listagem do ledger `MovimentacaoEstoque` em `/estoque/movimentacoes/`,
navegável pelo menu de estoque. Atravessa todas as camadas: selector de
visibilidade por papel (fronteira de segurança), view fina, rota, template
(tabela desktop + cards mobile), item de menu e testes.

### Entra nesta entrega

- Selector `movimentacoes_visiveis_para(ator_id)` com RBAC por papel.
- Policy `pode_consultar_movimentacoes_estoque` + flag no context processor (menu).
- View fina `historico_movimentacoes_view` + rota `name='estoque:historico_movimentacoes'`.
- Template `historico_movimentacoes.html`: tabela desktop, cards mobile, badge de
  tipo (rótulo + cor AA), célula de delta assinado, célula de origem, empty state.
- Paginação server-side (partial `partials/_paginacao.html`, `?page=`).
- Item de menu "Movimentações" em `estoque/_topbar_nav.html`, visível conforme RBAC.
- Registro da rota em `.design/INFORMATION_ARCHITECTURE.md`.

### NÃO entra (deferido — issue diz "Sem filtros ainda")

Barra de filtros (material/tipo/período/setor), chip "só saídas", ordenação
clicável asc↔desc, swap parcial via HTMX. A `TASKS.md` lista esses itens, mas a
issue #6 entrega apenas **histórico escopado e paginado**, ordenado `-criado_em`
fixo. Esses itens são tasks futuras. Ledger permanece somente-leitura.

## Files touched

| Arquivo | Ação | O quê |
| --- | --- | --- |
| `apps/estoque/selectors.py` | Modify | + `movimentacoes_visiveis_para(ator_id)` e helpers `_eh_almoxarifado`, `_setores_visiveis_nao_almox`. |
| `apps/estoque/policies.py` | Modify | + `pode_consultar_movimentacoes_estoque` / `exigir_*`. |
| `apps/requisicoes/context_processors.py` | Modify | + flag `pode_consultar_movimentacoes_estoque`. |
| `apps/estoque/views.py` | Modify | + `historico_movimentacoes_view` (fina). |
| `apps/estoque/urls.py` | Modify | + `path('movimentacoes/', ...)`. |
| `apps/estoque/templates/estoque/historico_movimentacoes.html` | New | tela. |
| `apps/estoque/templates/estoque/partials/_badge_tipo_movimentacao.html` | New | badge reutilizável (tabela + cards). |
| `apps/estoque/templates/estoque/partials/_paginacao.html` | New | controle de paginação reutilizável. |
| `apps/estoque/templates/estoque/_topbar_nav.html` | Modify | + item "Movimentações". |
| `.design/INFORMATION_ARCHITECTURE.md` | Modify | registrar rota/navegação. |
| `apps/estoque/tests/test_selectors.py` | Modify | testes do selector por papel. |
| `apps/estoque/tests/test_policies.py` | Modify | testes da policy. |
| `apps/estoque/tests/test_views.py` | Modify | testes de view + paginação + menu. |
| `apps/estoque/tests/conftest.py` | Modify | fixtures: aux de setor não-almox, movimentações de seed. |

## RBAC (regra no selector — fronteira de segurança)

`movimentacoes_visiveis_para(ator_id) -> QuerySet[MovimentacaoEstoque]`:

- **superuser** → tudo.
- **almoxarifado** (chefe **ou** auxiliar via `VinculoAuxiliar` de setor
  `ALMOXARIFADO` ativo) → tudo, **incluindo** saídas excepcionais.
- **chefe/aux de setor não-almox** → só `requisicao__setor_beneficiario_id ∈`
  setores onde é chefe ou aux ativo; **sem** saídas excepcionais (essas têm
  `requisicao IS NULL`, logo o filtro por setor já as exclui — não-vazamento por
  construção).
- **usuário inativo / inexistente** → `none()`.

Helpers locais (espelham requisicoes; mantêm RBAC self-contained):
- `_eh_almoxarifado(ator)` — chefe **ou** aux ativo de setor ALMOXARIFADO ativo.
- `_setores_visiveis_nao_almox(ator)` — IDs de setores não-almox ativos onde o
  ator é chefe **ou** aux ativo (issue exige cobrir auxiliar de setor, que o
  helper chefe-only de requisicoes não cobre).

`select_related('material', 'estoque', 'ator', 'requisicao',
'requisicao__setor_beneficiario', 'saida_excepcional')`. Ordenação `-criado_em`.

## Test strategy (ADR-0010, sem factory_boy)

Selector (`test_selectors.py`):
- superuser vê tudo (req + saída excepcional).
- chefe almox vê tudo incl. saída excepcional.
- aux almox (VinculoAuxiliar) vê tudo incl. saída excepcional.
- chefe de setor não-almox vê só do próprio setor.
- aux de setor não-almox vê só do próprio setor.
- **não-vazamento**: chefe de setor NÃO vê saída excepcional NEM movimentação de
  outro setor.
- usuário inativo → vazio.
- usuário inexistente (pk fantasma) → vazio.
- ordenação default `-criado_em` (mais recente primeiro).

Policy (`test_policies.py`): superuser/almox/chefe-setor/aux-setor → True;
inativo → False; solicitante puro sem setor chefiado/aux → False.

View (`test_views.py`):
- 200 para ator com visibilidade; queryset escopado no contexto.
- 403 (`PermissionDenied`) para quem não pode consultar (ex.: solicitante puro).
- paginação: com N > page_size, 1ª página tem page_size itens, `?page=2` avança.
- empty state quando ledger visível vazio.
- menu: item "Movimentações" presente para almox/superuser, ausente p/ solicitante.

## Invariants

- **Origem exclusiva** (`movimentacao_exatamente_uma_origem`): cada linha tem
  requisição XOR saída excepcional → célula de origem renderiza exatamente uma.
- **Ledger imutável / append-only**: tela é estritamente leitura; nenhum
  `save`/`update`/`delete`. Paginação server-side por o ledger ser ilimitado.
- **RBAC no selector, nunca na view/template**: forçar querystring não vaza dado.
- **Coerência tipo↔origem** (`movimentacao_tipo_origem_coerente`): tipos de
  origem-requisição nunca aparecem com saída excepcional e vice-versa.

## Risks

- **Vazamento entre setores / saída excepcional a setor**: mitigado por filtro de
  setor via `requisicao__setor_beneficiario` (saídas têm `requisicao` nulo) +
  teste de não-vazamento explícito.
- **N+1 na tabela**: mitigado por `select_related` em todas as FKs exibidas.
- **Auxiliar de setor não coberto pelo helper de requisicoes**: helper próprio
  `_setores_visiveis_nao_almox` cobre chefe + aux.
- **Contraste AA dos badges**: par fundo-100/texto-900 por tipo; rótulo textual
  sempre presente (cor nunca é único portador).
- **Sem migração**: nenhuma mudança de schema (`MovimentacaoEstoque` já existe,
  PR #1). Sem risco de migração.
