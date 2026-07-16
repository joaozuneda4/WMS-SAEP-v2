# Plano — Issue #87 (PR 1/3): `lista_minhas` + `historico_requisicoes` → padrão de listagem

Epic: #68. Bloqueador #83 (padrão de listagem responsiva via `partialdef` —
`components/table.html`, `fila_atendimento.html`/`fila_autorizacao.html`) —
`CLOSED`, mergeado.

## Roadmap da issue #87 (3 PRs, todos referenciando #87)

- **PR 1 (este)** — `apps/requisicoes`: `lista_minhas.html` + fusão de
  `historico_requisicoes.html` com `partials/_tabela_historico_requisicoes.html`.
- **PR 2** — `apps/estoque` históricos: `historico_movimentacoes.html` (+ fusão do
  partial, atenção ao chip OOB "só saídas"), `lista_saidas_excepcionais.html`,
  `lista_materiais.html` (realces de linha divergente `bg-red-50` continuam
  explícitos).
- **PR 3** — `estoque/historico_importacoes_scpi.html` (hoje só desktop; adotar
  chrome de tabela; cards mobile ficam registrados como melhoria futura, fora de
  escopo, conforme a issue).

## Escopo (PR 1)

**Entra:**
- `apps/requisicoes/templates/requisicoes/lista_minhas.html` — migrar
  `<table>`/cards inline para `components/table.html#tabela_abertura` /
  `#cards_abertura` / `#card_abertura` / `#th`.
- `apps/requisicoes/templates/requisicoes/historico_requisicoes.html` — fundir
  com `partials/_tabela_historico_requisicoes.html` num único arquivo,
  envolvendo o bloco resultado (cards + tabela + paginação + empty state) em
  `{% partialdef resultados %}` / `{% partial resultados %}`, migrado para o
  chrome `components/table.html`.
- `apps/requisicoes/templates/requisicoes/partials/_tabela_historico_requisicoes.html`
  — apagado após a fusão.
- `apps/requisicoes/views.py:1211-1215` (`historico_requisicoes_view`) — troca
  o `template` escolhido em `is_htmx` de
  `'requisicoes/partials/_tabela_historico_requisicoes.html'` para
  `'requisicoes/historico_requisicoes.html#resultados'`.
- `apps/requisicoes/tests/test_views.py` — atualiza as 2 asserções que checam
  `template.name` (ver nuance técnica abaixo).

**Não entra:**
- Colunas, copy, ordem de campos (fora de escopo pela issue).
- `selectors.py`, `policies.py`, `services.py` — nenhuma regra de domínio
  tocada.
- `estoque/*` (PR 2/3).
- Barra de filtros do histórico (form HTMX) — só o bloco de resultado migra
  para o chrome; a `<details>`/`<form>` fora do `{% partialdef resultados %}`
  não muda.

## Decisões de design dentro do escopo

1. **Coluna "Data/hora" do histórico fica literal, fora do `th` partial.** O
   fragmento `components/table.html#th` só aceita `rotulo` /
   `rotulo_somente_leitura` / `alinhamento` — não tem parâmetro para
   `aria-sort` nem para o `<a hx-get>` de ordenação. Forçar isso no componente
   violaria o guardrail do próprio `table.html` ("se o chrome precisar de
   parâmetro que descreve conteúdo de célula, a abstração está errada — parar
   e registrar"): um link de ordenação é conteúdo de célula, não estrutura
   visual. Essa `<th>` continua escrita explícita na tela, como já é hoje;
   as demais colunas (Número, Solicitante, Beneficiário, Setor, Material,
   Status, Ações) usam `#th`.
2. **`lista_minhas.html` ganha `<caption class="sr-only">`.** A tabela atual
   não tem `<caption>`; o contrato do `tabela_abertura` (`docs/design-system.md`
   § 8) exige que a tela chamadora forneça a sua. Texto proposto:
   `"Requisições onde você é criador ou beneficiário."` — mesma frase do `<p>`
   de introdução já existente na tela, sem inventar copy nova. Contrato novo
   exige teste explícito (ver Estratégia de testes, item 1) — sem isso, uma
   regressão futura pode remover o `<caption>` sem quebrar a suíte.
3. **Sem swap HTMX em `lista_minhas.html`.** Diferente do histórico, essa tela
   não tem filtro/paginação hoje; o `{% partialdef resultados %}` não é
   necessário ali — só a migração de chrome. Registrado aqui para não ser
   lido como omissão.

## Nuance técnica — `template.name` de fragmento `partialdef` nos testes

Investigação em `django/template/defaulttags.py` (`partialdef_func`) e
`django/template/base.py` (`class PartialTemplate`): ao renderizar
`render(request, "app/tpl.html#resultados", ctx)`, o objeto capturado pelo
signal `template_rendered` (e portanto em `response.templates`) é o
`PartialTemplate`, cujo `.name` é **o nome do fragmento** (`"resultados"`),
não o path do template nem do partial antigo. `.origin.template_name` é que
mantém o path do arquivo-fonte (`"requisicoes/historico_requisicoes.html"`).

Isso quebra as 2 asserções atuais em `test_views.py`:

```python
# test_requisicao_htmx_devolve_so_partial
assert 'requisicoes/partials/_tabela_historico_requisicoes.html' in nomes
assert 'requisicoes/historico_requisicoes.html' not in nomes

# test_requisicao_normal_devolve_template_completo
assert 'requisicoes/historico_requisicoes.html' in nomes
```

Novo comportamento após a fusão:
- Requisição HTMX: `response.templates` contém um `PartialTemplate` com
  `.name == 'resultados'` (não mais o path do partial antigo).
- Requisição normal: `response.templates` contém o `Template` completo com
  `.name == 'requisicoes/historico_requisicoes.html'` (inalterado — página
  cheia continua sendo um `Template` normal, não um `PartialTemplate`).

Novo assert proposto (RED nesta fase de plano, GREEN na implementação). Checar
só `t.name == 'resultados'` não garante que o fragmento veio do template certo
— outro template poderia coincidentemente ter um `partialdef resultados` —
então a asserção também verifica `t.origin.template_name`:

```python
def test_requisicao_htmx_devolve_so_partial(self, client, superuser):
    _login(client, superuser)
    response = client.get(URL_HISTORICO_REQUISICOES, HTTP_HX_REQUEST='true')
    assert response.status_code == 200
    assert any(
        t.name == 'resultados'
        and t.origin.template_name == 'requisicoes/historico_requisicoes.html'
        for t in response.templates
    )
    nomes = {t.name for t in response.templates}
    assert 'requisicoes/historico_requisicoes.html' not in nomes
```

`test_requisicao_normal_devolve_template_completo` não muda (página cheia
segue reportando o path completo).

## Arquivos tocados

| Arquivo | Mudança |
|---|---|
| `apps/requisicoes/templates/requisicoes/lista_minhas.html` | Migra chrome para `components/table.html`; adiciona `<caption sr-only>`. |
| `apps/requisicoes/templates/requisicoes/historico_requisicoes.html` | Absorve o conteúdo de `_tabela_historico_requisicoes.html` em `{% partialdef resultados %}`; migra chrome. |
| `apps/requisicoes/templates/requisicoes/partials/_tabela_historico_requisicoes.html` | **Apagado.** |
| `apps/requisicoes/views.py` | 2 linhas: template HTMX passa a ser `'requisicoes/historico_requisicoes.html#resultados'`. |
| `apps/requisicoes/tests/test_views.py` | Atualiza assert de `template.name` em `test_requisicao_htmx_devolve_so_partial`. |

## Estratégia de testes (ADR-0010)

1. **Regressão de conteúdo** — suíte existente de `lista_minhas` (7 testes:
   200, autorizações chefe ativo/inativo, exclusão de rascunho de terceiro,
   número público/fallback, `aria-label` dos botões) deve permanecer verde
   **sem alteração de asserção** — o chrome migrado é byte-idêntico ao HTML
   inline atual (`components/table.html` foi extraído textualmente das mesmas
   classes em #83); só a nova `<caption>` é conteúdo adicional, não corta
   nada existente. **Teste novo** (obrigatório, não opcional — sem ele o
   contrato de acessibilidade fica sem cobertura e uma regressão futura
   passaria despercebida): `test_minhas_tabela_tem_caption_sr_only` verifica
   cardinalidade e adjacência, não só presença — projeto não tem parser HTML
   como dependência (`grep` confirma zero uso de `bs4`/`html.parser` em
   `apps/`; guardrail "zero dependência nova" proíbe introduzir um). Segue a
   convenção já usada em `apps/estoque/tests/test_views.py:546,1151`
   (`conteudo.count(marcador) == 1`):

   ```python
   conteudo = response.content.decode()
   marcador = (
       '<table class="min-w-full divide-y divide-slate-200">'
       '\n        <caption class="sr-only">Requisições onde você é '
       'criador ou beneficiário.</caption>'
   )
   assert conteudo.count(marcador) == 1
   ```

   O marcador inclui a abertura literal de `<table>` (vinda de
   `components/table.html#tabela_abertura`) imediatamente seguida da
   `<caption>`, garantindo adjacência (caption é filho direto da tabela
   certa) sem precisar de parser HTML. Ajustar espaçamento exato ao rodar —
   copiar do output real do `tabela_abertura`, não assumir indentação.
2. **Regressão de conteúdo do histórico** — suíte existente
   (`TestHistoricoRequisicoesView` e filtros) permanece verde, mesmo raciocínio
   de byte-paridade do chrome.
3. **Template escolhido (comportamento novo)** — atualizar
   `test_requisicao_htmx_devolve_so_partial` conforme nuance acima; rodar
   isolado primeiro (`-k test_requisicao_htmx_devolve_so_partial`) para
   confirmar o nome do fragmento antes de generalizar.
4. **Paridade visual** — mobile 375px + desktop, comparação manual (screenshot)
   das 2 telas antes/depois via preview, conforme critério de aceite da #87.

## Invariantes relevantes (`docs/matriz-invariantes.md`)

- RBAC do histórico: `exigir_pode_consultar_historico_requisicoes` continua
  intocado na view — só o template escolhido e o markup mudam.
- Contrato PRG + HX-Redirect: não tocado — `historico_requisicoes_view` é
  `@require_GET`, não usa PRG; o fragmento `#resultados` nunca é alvo de
  transição de estado (guardrail do design-system, já respeitado hoje).
- `aria-live`/`hx-push-url` do wrapper `#resultados-historico-requisicoes`:
  permanecem na página completa, fora do `{% partialdef resultados %}` — o
  partial entrega só o conteúdo interno (mesmo contrato de hoje).

## Riscos

- **Baixo.** Refactor puro de template + 2 linhas de view; zero mudança de
  schema, zero mutação de estoque, zero transição de estado. Único ponto real
  de atenção é a nuance de `template.name` acima (comportamento do Django 6,
  não do código do projeto) — mapeado e com teste already-known-red.
- Risco de drift visual: mitigado por chrome byte-idêntico (extraído do texto
  já existente) + verificação manual mobile/desktop antes do PR final.

## Guardrails

- Padrão de #83 é lei — nenhuma variação nova de chrome (decisão 1 acima
  documenta o único desvio: manter uma `<th>` literal, não uma variante do
  componente).
- ARIA inegociável: `caption sr-only`, `aria-live` do wrapper, `aria-sort`,
  aria-labels de ação — todos preservados ou adicionados (caption).
- Tailwind v4 JIT + `npm run css:build` obrigatório antes do PR final.
- Escopo fechado: 2 templates + 1 partial apagado + 2 linhas de view + 1
  arquivo de teste.
- Zero dependência nova.
- Branch: `refactor/listagem-requisicoes`.
- Suíte + `ruff format`/`ruff check` + `mypy apps` verdes antes do PR final.
- PT-BR em identificadores, comentários e copy.
