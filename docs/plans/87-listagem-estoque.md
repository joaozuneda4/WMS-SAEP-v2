# Plano — Issue #87 (PR 2/3): históricos de `apps/estoque` → padrão de listagem

Epic: #68. PR 1/3 (`refactor/listagem-requisicoes`, `apps/requisicoes`) já entregue
em [joaozuneda4/WMS-SAEP-v2#6](https://github.com/joaozuneda4/WMS-SAEP-v2/pull/6),
CodeRabbit `SUCCESS`. Este plano cobre o PR 2/3, escopo `apps/estoque`.

## Roadmap da issue #87

- ~~PR 1 — `apps/requisicoes`: `lista_minhas.html` + fusão de
  `historico_requisicoes.html`.~~ Entregue.
- **PR 2 (este)** — `apps/estoque`: `historico_movimentacoes.html` (+ fusão do
  partial, chip OOB "só saídas"), `lista_saidas_excepcionais.html`,
  `lista_materiais.html`.
- PR 3 — `estoque/historico_importacoes_scpi.html` (hoje só desktop; adotar
  chrome de tabela; cards mobile fora de escopo, registrado como melhoria
  futura).

## Escopo (PR 2)

**Entra:**
- `apps/estoque/templates/estoque/historico_movimentacoes.html` — funde com
  `partials/_tabela_movimentacoes.html` (apagado) em
  `{% partialdef resultados %}` / `{% partial resultados %}`, migrado para
  `components/table.html`. O reemite do chip OOB "só saídas"
  (`{% if is_htmx %}{% include 'estoque/partials/_chip_so_saidas.html' with oob_chip=True %}{% endif %}`,
  hoje na última linha do partial) **entra dentro do fragmento fundido**, na
  mesma posição relativa (depois do `{% endif %}` do bloco resultado, antes do
  `{% endpartialdef %}`) — é o único jeito de preservar o contrato: hoje esse
  trecho já roda toda vez que o partial é incluído (página completa ou HTMX),
  e o `{% if is_htmx %}` interno é que decide se o chip OOB aparece. Mover
  esse bloco pra fora do `{% partialdef %}` quebraria o swap HTMX (o chip
  precisa vir na mesma resposta que o `#resultados`, não em request separado).
- `apps/estoque/templates/estoque/partials/_tabela_movimentacoes.html` —
  **apagado** após a fusão.
- `apps/estoque/views.py:175-179` (`historico_movimentacoes_view`) — troca o
  `template` escolhido em `is_htmx` de
  `'estoque/partials/_tabela_movimentacoes.html'` para
  `'estoque/historico_movimentacoes.html#resultados'`.
- `apps/estoque/templates/estoque/lista_saidas_excepcionais.html` — migra
  chrome inline para `components/table.html` (já tem `<caption>`, sem HTMX —
  migração direta, mesmo padrão de `lista_minhas.html` no PR 1).
- `apps/estoque/templates/estoque/lista_materiais.html` — migra chrome (sem
  HTMX). Ver "Decisões de design" abaixo — não é migração direta: o chrome
  atual diverge do canônico em cor de `<th>`, background do wrapper desktop e
  tamanho de fonte herdado, além de ter alinhamento central não suportado
  pelo fragmento `#th` numa coluna.
- `apps/estoque/tests/test_views.py` — atualiza os 2 asserts de
  `template.name` do histórico (mesma nuance do PR 1); adiciona teste de
  regressão para o realce de linha divergente em `lista_materiais` (hoje
  **não testado** no nível de markup, só no nível de contexto —
  `test_flag_divergente_visivel_no_contexto`, linha 873).

**Não entra:**
- Colunas, copy, ordem de campos.
- `selectors.py`, `policies.py`, `services.py`.
- `apps/requisicoes` (PR 1, já entregue).
- `historico_importacoes_scpi.html` (PR 3).
- Barra de filtros HTMX do histórico de movimentações — só o bloco de
  resultado migra.

## Decisões de design dentro do escopo

1. **Coluna "Data/hora" do histórico de movimentações fica literal**, mesmo
   raciocínio do PR 1 (`historico_requisicoes.html`): `aria-sort` + link de
   ordenação são conteúdo de célula, não estrutura visual. As demais colunas
   (Tipo, Material, Δ Físico, Δ Reservado, Origem, Ator) usam `#th`. Aqui as
   classes já batem com o canônico hoje (`text-slate-500`) — não há drift
   nesta tela, diferente de `lista_materiais` (decisão 4).
2. **Chip OOB "só saídas" fica dentro do fragmento `resultados` fundido**
   (ver Escopo acima) — não é uma migração de chrome, é preservação de
   contrato HTMX existente. Testado por
   `test_chip_so_saidas_reemitido_via_oob_no_swap_htmx` e
   `test_chip_so_saidas_sem_oob_na_pagina_completa` (ambos por conteúdo
   HTML, não por `template.name` — não afetados pela nuance de fragmento).
3. **`lista_materiais.html`: `<article>` mobile e `<tr>` desktop ficam
   literais, não usam `#card_abertura`.** O card/linha tem estilo condicional
   ao estado de domínio (`saldo.divergente_calculado`: borda/fundo
   vermelhos + `aria-label` no `<article>`; `bg-red-50 hover:bg-red-100` no
   `<tr>`). `#card_abertura` é uma string de classe fixa, sem parâmetros
   (guardrail do próprio `components/table.html`: não parametrizar sem
   registrar decisão). O `<tr>` desktop já é sempre literal em **todas** as
   telas migradas até aqui (nunca fez parte do chrome) — tratar o `<article>`
   mobile pela mesma lógica é consistente, não uma exceção nova: ambos são o
   "item de linha", e o realce de divergência é conteúdo de célula/linha, não
   estrutura de chrome. Isso também é exigido explicitamente pela issue:
   "inclui os realces de linha divergente `bg-red-50` — permanecem
   explícitos nas células/rows". `cards_abertura` (container mobile) e
   `tabela_abertura` (wrapper desktop) — que não carregam nenhum estado
   condicional — usam os fragmentos normalmente.
4. **`lista_materiais.html`: coluna "Status" (`<th>`) fica literal.** É a
   única `<th>` com `text-center` nas 6 telas já migradas ou a migrar; o
   fragmento `#th` só suporta `esquerda` (default) ou `direita`
   (`alinhamento="direita"`). Mesma lógica da decisão 1 do PR 1: forçar um
   terceiro valor no componente compartilhado por causa de 1 coluna em 1
   tela violaria o guardrail de não generalizar por conteúdo específico.
5. **`lista_materiais.html` não tem `<caption>` hoje** — mesmo gap do PR 1
   (`lista_minhas.html`). O contrato do `tabela_abertura`
   (`docs/design-system.md` §8) exige que a tela chamadora forneça a sua.
   Texto proposto: `"Saldo físico, reservado e disponível de cada material
   no estoque."` — variação curta do `<p>` de introdução já existente
   (evita repetir "materiais com divergência crítica..." na caption, que é
   detalhe de célula, não descrição da tabela). Exige teste explícito
   (mesmo padrão do PR 1, cardinalidade+adjacência via `.count(...) == 1`,
   sem parser HTML novo) — sem ele, uma regressão futura remove o
   `<caption>` sem quebrar a suíte.
6. **`lista_materiais.html`: chrome adota as classes canônicas, corrigindo
   drift pré-existente — não é migração byte-idêntica** (diferente de
   `lista_minhas`/`lista_saidas_excepcionais`/`historico_movimentacoes`, onde
   o chrome atual já batia com o canônico). Divergências encontradas hoje:
   - `<th>`: `text-slate-600` → canônico `text-slate-500`.
   - Wrapper desktop: `hidden sm:block overflow-x-auto rounded-xl border
     border-slate-200 shadow-sm` (sem `bg-white`) → canônico adiciona
     `bg-white`.
   - `<table>`: `min-w-full divide-y divide-slate-200 text-sm` → canônico
     `min-w-full divide-y divide-slate-200` (sem `text-sm` a nível de
     tabela). 5 `<td>` hoje dependem desse `text-sm` implícito por não
     declarar tamanho próprio (Material, Físico, Reservado, Disponível,
     Un.) — cada um recebe `text-sm` explícito na migração, preservando o
     tamanho de fonte renderizado (zero mudança visual nessas 5 células,
     mesmo removendo o `text-sm` do `<table>`).
   - **Por que corrigir em vez de preservar**: epic #68 lista exatamente
     esse tipo de divergência ("Tokens semânticos... ~50 usos de cor crua")
     como o problema que a extração de componentes resolve; o guardrail de
     #87 diz "Padrão de #83 é lei". A cor de `<th>` (slate-600→500) e o
     `bg-white` do wrapper são as únicas mudanças visuais reais desta
     decisão — sutis (tom de cinza mais claro no cabeçalho; fundo branco
     explícito atrás da tabela, hoje implícito por herança). Precisam de
     verificação visual manual (mobile+desktop) antes do PR final —
     registrado aqui para não ser lido como omissão caso o `git diff`
     pareça maior que "só chrome".

## Nuance técnica — `template.name` (mesma do PR 1)

`historico_movimentacoes_view` usa o mesmo padrão de
`historico_requisicoes_view` (ambos migrados pelo helper `paginar_com_filtros`
na issue #84). Fragmentos `partialdef` reportam `template.name` como o nome
do fragmento (`"resultados"`), não o path do template —
`.origin.template_name` mantém o path. Assert atual em
`test_requisicao_htmx_devolve_so_partial` (linha ~1029-1038):

```python
nomes = {t.name for t in response.templates}
assert 'estoque/partials/_tabela_movimentacoes.html' in nomes
assert 'estoque/historico_movimentacoes.html' not in nomes
```

Novo assert (mesmo padrão do PR 1, já validado pelo CodeRabbit lá):

```python
def test_requisicao_htmx_devolve_so_partial(
    self, client, superuser, requisicao_autorizada
):
    client.force_login(superuser)
    response = client.get(URL_MOVIMENTACOES, HTTP_HX_REQUEST='true')
    assert response.status_code == 200
    assert any(
        t.name == 'resultados'
        and t.origin.template_name == 'estoque/historico_movimentacoes.html'
        for t in response.templates
    )
    nomes = {t.name for t in response.templates}
    assert 'estoque/historico_movimentacoes.html' not in nomes
```

`test_requisicao_normal_devolve_template_completo` não muda.

## Arquivos tocados

| Arquivo | Mudança |
|---|---|
| `apps/estoque/templates/estoque/historico_movimentacoes.html` | Absorve `_tabela_movimentacoes.html` em `{% partialdef resultados %}` (incl. reemite do chip OOB); migra chrome. |
| `apps/estoque/templates/estoque/partials/_tabela_movimentacoes.html` | **Apagado.** |
| `apps/estoque/templates/estoque/lista_saidas_excepcionais.html` | Migra chrome (byte-idêntico ao atual — já bate com canônico). |
| `apps/estoque/templates/estoque/lista_materiais.html` | Migra chrome com correção de drift (decisão 6); adiciona `<caption sr-only>` (decisão 5); `<article>`/`<tr>`/`<th>` Status ficam literais (decisões 3-4). |
| `apps/estoque/views.py` | 2 linhas: template HTMX do histórico passa a ser `'estoque/historico_movimentacoes.html#resultados'`. |
| `apps/estoque/tests/test_views.py` | Assert de `template.name`; teste novo de caption em `lista_materiais`; teste novo de regressão para realce divergente em `lista_materiais`. |

## Estratégia de testes (ADR-0010)

1. **Regressão de conteúdo** — suítes existentes de `historico_movimentacoes`
   (`TestHistoricoMovimentacoesView`, `TestHistoricoMovimentacoesFiltros`,
   incl. os 4 testes de chip OOB) e `lista_saidas_excepcionais`
   (`TestListarSaidasExcepcionaisView`) permanecem verdes sem alteração de
   asserção — chrome byte-idêntico nessas 2 telas.
2. **Template escolhido (comportamento novo)** — atualizar
   `test_requisicao_htmx_devolve_so_partial` do histórico de movimentações
   conforme nuance acima.
3. **`lista_materiais` — 2 testes novos obrigatórios**:
   - `test_lista_materiais_tabela_tem_caption_sr_only` (gap: sem `<caption>`
     hoje) — cardinalidade+adjacência via `conteudo.count(marcador) == 1`
     (mesmo padrão do PR 1), texto exato ajustado ao rodar (copiar do output
     real do `tabela_abertura`, não assumir espaçamento).
   - `test_material_divergente_realca_linha_e_card` (gap de cobertura
     pré-existente: hoje só `test_flag_divergente_visivel_no_contexto`
     verifica o contexto, não o markup renderizado) — usa fixture
     `material_scpi_critico` (já usada em
     `test_flag_divergente_visivel_no_contexto`, linha 873) e verifica:
     - desktop: `<tr>` contém `bg-red-50` e `hover:bg-red-100`;
     - mobile: `<article>` contém `border-red-300 bg-red-50` e
       `aria-label="Material com divergência crítica"`;
     - badge "Divergente" (`components/badge.html` variant `red-strong`)
       aparece nas 2 apresentações.
4. **Paridade visual** — mobile 375px + desktop, `lista_materiais` com e sem
   material divergente (para validar decisão 6 — cor de `<th>`, `bg-white`
   do wrapper, tamanho de fonte das 5 colunas afetadas), demais telas
   comparação direta com o comportamento pré-refactor.

## Invariantes relevantes (`docs/matriz-invariantes.md`)

- RBAC/escopo por setor: `exigir_pode_consultar_movimentacoes_estoque`,
  `exigir_pode_consultar_saidas_excepcionais`,
  `exigir_pode_consultar_catalogo_estoque` — intocados, só template/markup
  muda.
- Contrato PRG + HX-Redirect: não tocado — as 3 views são `@require_GET`
  (movimentações) ou sem HTMX (saídas excepcionais, materiais).
- Chip "só saídas": contrato de swap OOB preservado (decisão 2) — sem chip
  duplicado na página completa, sem chip ausente no swap HTMX.

## Riscos

- **Baixo-médio.** `historico_movimentacoes` e `lista_saidas_excepcionais`:
  mesmo risco baixo do PR 1 (chrome byte-idêntico + nuance de
  `template.name` já mapeada e validada). `lista_materiais`: risco um degrau
  acima por causa da correção de drift (decisão 6) — mitigado por testes novos
  de regressão do realce divergente + verificação visual manual antes do PR
  final. Sem mutação de estoque, sem transição de estado, sem mudança de
  schema em nenhuma das 3 telas.
- Risco de regressão no chip OOB: mitigado por preservar a posição relativa
  exata do `{% if is_htmx %}...{% endif %}` dentro do fragmento fundido
  (decisão 2) — testes de chip já existentes cobrem isso.

## Guardrails

- Padrão de #83 é lei — variações documentadas nas decisões 1, 3 e 4 (não
  são chrome novo, são exceções já com precedente do PR 1 ou do próprio
  `<tr>`/`<td>` que é sempre literal).
- ARIA inegociável: `caption sr-only` (preservado nas 2 telas que já têm —
  `historico_movimentacoes`, `lista_saidas_excepcionais` — e adicionado em
  `lista_materiais`, decisão 5), `aria-live`/`hx-push-url` do wrapper de
  histórico, `aria-sort`, `aria-label` do `<article>` divergente.
- Tailwind v4 JIT + `npm run css:build` obrigatório — decisão 6 introduz
  `bg-white` que já deve estar compilado (classe usada em outras telas), mas
  rodar de qualquer forma para confirmar zero diff inesperado.
- Escopo fechado: 3 templates + 1 partial apagado + 2 linhas de view + 1
  arquivo de teste.
- Zero dependência nova.
- Branch: `refactor/listagem-estoque-historicos`.
- Verde antes do PR final:
  `uv run pytest -q -ra --tb=short --strict-markers --disable-warnings -n logical`,
  `uv run ruff format .`, `uv run ruff format --check .`,
  `uv run ruff check .`, `uv run mypy apps`.
- PT-BR em identificadores, comentários e copy.
