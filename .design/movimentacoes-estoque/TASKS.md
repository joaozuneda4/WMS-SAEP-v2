# Build Tasks: Histórico de Movimentações de Estoque

Generated from: .design/movimentacoes-estoque/DESIGN_BRIEF.md
Date: 2026-06-24

> Stack: Django + Tailwind + HTMX + Alpine. Arquitetura em camadas (ADR-0004/0011):
> RBAC e leitura no selector, view fina, template apresentacional. TDD obrigatório
> (ADR-0010): cada task de backend nasce com teste vermelho primeiro.
> Filtros vivem na querystring; HTMX faz swap parcial da tabela.

## Foundation

- [ ] **Selector de visibilidade `movimentacoes_visiveis_para(ator_id)`** (RISK-FIRST):
  retorna `QuerySet[MovimentacaoEstoque]` filtrado por papel, espelhando
  `requisicoes/selectors.py::requisicoes_visiveis_para`. Regras: superuser → tudo;
  almoxarifado (chefe **ou** auxiliar via `VinculoAuxiliar`) → tudo (inclui saídas
  excepcionais); chefe/aux de setor não-almox → só movimentações com
  `requisicao__setor_beneficiario ∈ setores do ator`, **sem** saídas excepcionais;
  usuário inativo / inexistente → `none()`. `select_related` em material, estoque,
  ator, requisicao, saida_excepcional. _New. Reusa helpers `_eh_almoxarifado` /
  `_setores_chefiados_nao_almox` (extrair p/ `core` ou replicar)._ **Done**: testes de
  cada papel verdes, incluindo tentativa de vazamento entre setores e órfã (saída
  excepcional invisível a setor).

- [ ] **Selector de filtro `filtrar_movimentacoes(qs, *, material, tipos, data_ini, data_fim, setor)`**:
  aplica filtros sobre o queryset visível. Material por `codigo`/`nome` icontains; tipos
  como lista de `TipoMovimentacaoEstoque`; período sobre `criado_em` (inclusivo);
  setor via `requisicao__setor_beneficiario_id`. Ordenação default `-criado_em`,
  alternável p/ `criado_em`. _New._ **Done**: testes de cada filtro isolado + combinados
  + ordenação verdes; filtro de setor não amplia universo (aplica sobre o já-visível).

## Core UI

- [ ] **View + URL `historico_movimentacoes_view`**: view fina em `estoque/views.py`,
  rota `movimentacoes/` (`name='historico_movimentacoes'`). Lê querystring → chama
  selectors → pagina (Paginator) → renderiza. Detecta `request.htmx` para devolver só o
  partial da tabela. Passa ao contexto: página, filtros ativos, flag `mostrar_filtro_setor`
  (= `_eh_almoxarifado`). _New. Depends on: selectors._ **Contrato (ADR-0011/CONVENTIONS.md)**:
  a view chama os selectors por **ID** (`movimentacoes_visiveis_para(request.user.pk)`), não pelo
  objeto `user`; traduz exceção de domínio `PermissaoNegada` → `PermissionDenied` (403) via
  policy. **Done**: testes de view por papel (status, queryset escopado, contexto), teste de
  request HTMX devolve partial, teste de querystring inválida não quebra, teste de que
  solicitante recebe 403 (tradução de exceção).

- [ ] **Template base `historico_movimentacoes.html` + tabela desktop**: estende
  `estoque/base.html`, `app-bar__title` "Movimentações". Tabela densa (`hidden sm:block`)
  colunas: data/hora · tipo · material · Δfísico · Δreservado · origem · ator. `<caption
  class="sr-only">`, `scope="col"`. Bloco da tabela+paginação isolado em partial
  `partials/_tabela_movimentacoes.html` (alvo do swap HTMX). _Modify (esqueleto de
  `lista_saidas_excepcionais.html`). Depends on: view._ **Done**: render manual com dados
  de seed mostra ledger correto, mais-recente-no-topo.

- [ ] **Badge de tipo de movimentação**: pill semântica por `TipoMovimentacaoEstoque`
  (7 tipos), rótulo textual sempre presente. Mapa de cor comunica identidade do tipo
  (não alarme) seguindo shades do design-system (fundo-100 / texto-900). _New
  component._ **Done**: os 7 tipos renderizam com cor+rótulo distintos; contraste AA.

- [ ] **Célula de delta assinado**: Δfísico e Δreservado com `tabular-nums`, sinal +/−
  explícito, zero atenuado (`text-slate-400`). _New._ **Done**: positivos, negativos e
  zero distinguíveis sem depender só de cor.

- [ ] **Célula de origem**: renderiza nº público da requisição **ou** da saída
  excepcional (exatamente uma por linha — invariante do modelo). Texto, sem link nesta
  entrega. _New._ **Done**: ambas origens exibidas corretamente; nunca as duas.

## Interactions & States

- [ ] **Barra de filtros (form GET + HTMX)**: campos material (busca texto), tipo
  (multi-seleção), período (data ini/fim), setor (renderizado só se
  `mostrar_filtro_setor`). Submete via HTMX GET com `hx-push-url` → swap do partial da
  tabela, URL atualizada, página volta p/ 1. _New. Depends on: view._ **Done**: aplicar
  filtro troca só a tabela; URL reflete o recorte; recarregar mantém estado; chefe não vê
  campo de setor.

- [ ] **Chip "só saídas"**: atalho que seta tipo = `consumo` + `saida_excepcional` e
  reaplica filtro; estado ativo visível. _New. Depends on: barra de filtros._ **Done**:
  um clique filtra as saídas reais; chip reflete estado ativo/inativo.

- [ ] **Ordenação por data**: header de data clicável inverte `criado_em` asc↔desc via
  querystring (`?ordem=`), com `aria-sort` e indicador visual de direção. _Depends on:
  filtro selector + tabela._ **Done**: alterna ordem mantendo demais filtros; `aria-sort`
  correto.

- [ ] **Paginação server-side**: controle de páginas preservando toda a querystring de
  filtros; navega via HTMX (swap do partial). Partial `partials/_paginacao.html`
  reutilizável. _New (não há partial de paginação no projeto)._ **Done**: navegar páginas
  mantém filtros; total/posição visíveis; teclado operável.

- [ ] **Empty state contextual**: distingue "ledger vazio" de "nenhum resultado para
  este filtro". Padrão `border-dashed` + ícone + mensagem. _Reuses: padrão de empty state
  de `lista_saidas_excepcionais`._ **Done**: as duas mensagens corretas conforme há ou
  não filtro aplicado.

## Responsive & Polish

- [ ] **Cards mobile**: `< sm` cada movimentação vira `<article>`; hierarquia tipo(badge)
  +data no topo, material em destaque, deltas em `<dl>`, origem/ator como metadados. Sem
  scroll horizontal. _Modify (padrão de cards de `lista_saidas_excepcionais`).
  Breakpoints: < sm._ **Done**: mobile sem overflow horizontal; paridade de informação
  com a tabela.

- [ ] **Barra de filtros responsiva**: `< sm` campos empilhados full-width `min-h-11`,
  filtros em disclosure; chip "só saídas" sempre visível. _Breakpoints: < sm._

- [ ] **Item de menu "Movimentações"**: link na navegação da área de estoque
  (`_topbar_nav.html`), visível conforme RBAC. _New._ **Done**: chefe e almox veem a
  entrada; aponta p/ `estoque:historico_movimentacoes`.

- [ ] **Atualizar IA global**: registrar a rota `/estoque/movimentacoes/` e o item de
  navegação em `.design/INFORMATION_ARCHITECTURE.md` (IA é global no projeto). _Doc._

- [ ] **Pass de acessibilidade**: contraste AA dos badges; cor nunca único portador
  (rótulo de tipo + sinal de delta); teclado completo em filtros/chip/ordenação/paginação
  com `focus-visible:ring-2 ring-blue-500`; `aria-live="polite"` **e** `aria-atomic="true"`
  no contêiner de resultados para anunciar swap HTMX (contrato de `docs/design-system.md`
  linha 267); `aria-sort` no header de data. _Checks do brief._

## Review

- [ ] **Suíte de testes verde**: `uv run pytest -q -ra --tb=short --strict-markers
  --disable-warnings` + `ruff format --check .` + `ruff check .` + `mypy apps`.
- [ ] **Design review**: rodar `/design-review` contra o brief.
