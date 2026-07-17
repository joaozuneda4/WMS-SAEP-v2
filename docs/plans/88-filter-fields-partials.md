# Plano — Issue #88: campos de filtro como partials

Pai: #68 (épico de extração de componentes do design system)
Bloqueado por: #83 (CLOSED — padrão de listagem/one-template via `{% partialdef %}`)

## Escopo

Extrair os campos da barra de filtros HTMX — hoje ~120 linhas ~90% idênticas em
`historico_requisicoes.html` e `historico_movimentacoes.html` — como partials
reutilizáveis de **campo**, mantendo o `<form>` (composição explícita) em cada
tela. Segue o padrão já estabelecido por `components/table.html` (issue #83):
fragmentos "abertura" via `{% partialdef %}` + `{% include "file.html#nome" %}`
para peças que envolvem conteúdo composto pelo chamador; partials totalmente
autocontidos (estilo `components/badge.html`/`button.html`) para campos cujo
conteúdo é 100% parametrizável.

**NÃO** criar um "FilterBar" genérico. Os campos diferem entre telas (texto vs
material, estados vs tipos, chip "só saídas" só em movimentações) — extrair
campos e o shell (disclosure), não o formulário inteiro.

### O que muda

Novos partials em `apps/core/templates/components/`:

| Arquivo | Padrão | Parâmetros |
|---|---|---|
| `filter_shell.html#abertura` | abertura (estilo `table.html`) | `action_url`, `target_id` |
| `filter_acoes.html` | autocontido | `action_url`, `target_id`, `tem_filtro_ativo` |
| `filter_busca.html` | autocontido | `id`, `name`, `label`, `value`, `placeholder` |
| `filter_data.html` | autocontido, campo único (De/Até = 2 includes) | `id`, `name`, `label`, `value` |
| `filter_select.html` | autocontido (uso único: filtro de setor) | `id`, `name`, `label`, `opcoes` (obj com `.pk`/`.nome`), `selecionado`, `opcao_todos_rotulo` |
| `filter_checkbox_group.html` | autocontido | `legend`, `name`, `opcoes` (tuplas valor/rótulo), `selecionados` |

Templates migrados (só a barra de filtros — resto intocado):
- `apps/requisicoes/templates/requisicoes/historico_requisicoes.html`
- `apps/estoque/templates/estoque/historico_movimentacoes.html`

`lista_materiais.html` fica **fora de escopo** (form distinto, sem encaixe
natural — confirmado na leitura do arquivo).

### O que NÃO muda

- `views.py`, `selectors.py`, `services.py`, `policies.py` — nomes de campo
  GET (`texto`, `material`, `data_ini`, `data_fim`, `setor`, `estados`,
  `tipos`, `ordem`) permanecem idênticos, contrato de querystring intocado.
- `filter_shell.html` NÃO conhece o `hidden ordem=asc` — fica explícito no
  template chamador (decisão da própria issue).
- Chip "só saídas" (`estoque/partials/_chip_so_saidas.html`) fica fora do
  shell, como já é hoje.

### Correção de drift descoberta durante leitura

`historico_movimentacoes.html` (linha 33) tem `<div>` sem `sm:block!` ao
redor do form, enquanto `historico_requisicoes.html` (linha 31) tem
`<div class="sm:block!">`. `filter_shell.html#abertura` unifica com
`sm:block!` nas duas telas — elimina esse drift como efeito colateral
(alinhado ao objetivo do épico).

## Estratégia de testes

Testes existentes (`TestHistoricoRequisicoesFiltros`,
`TestHistoricoMovimentacoesFiltros`, `TestHistoricoMovimentacoesResponsivo`)
não fixam estrutura interna dos campos — verificam comportamento (contexto,
querystring, presença de `<details>`/`<summary>`, empty state contextual).
Não deveriam quebrar com a extração se os `name=`/`id=` dos inputs forem
preservados byte-a-byte.

Cobertura nova a acrescentar (TDD, RED→GREEN por comportamento):
1. **Paridade visual/estrutural**: as 2 telas continuam renderizando
   `<details>`, `<summary class="sm:hidden"...>`, `sm:block!` no wrapper do
   form (regressão do drift corrigido acima). Usar parser HTML
   (`lxml.html.fromstring` ou `assertHTMLEqual`) para validar aninhamento e
   fechamento de tags — não apenas `in response.content` — cobrindo em
   especial o `</div>` do grid aberto por `filter_shell.html#abertura` (ver
   risco abaixo).
2. **Submissão sem JS (requisito de aceite explícito)**: separar o contrato
   de navegação nativa do contrato HTMX — dois testes distintos. (a) Afirmar
   no HTML renderizado que o `<form>` expõe `method="get"` e `action="{{
   url }}"` (o atributo real de fallback sem JS — `hx-get`/`hx-push-url`
   representam comportamento do lado do cliente e não são exercitados por
   `client.get()`).
   (b) Chamar essa mesma `action` via `client.get(url, {..._querystring_})`
   sem `HTTP_HX_REQUEST` e validar o `page_obj` filtrado — isto comprova o
   fallback de navegação nativa (GET com querystring), não que o cliente de
   teste "processou" `hx-push-url`. Testar o `href` de "Limpar filtros"
   separadamente, como link estático de navegação nativa.

3. **Checkbox `min-h-11`**: manter asserção de alvo de toque nos checkboxes
   de estado/tipo.
4. **`filter_select` fieldset a11y**: `<label for=...>` vinculado ao `id` do
   select permanece.
5. **Zero duplicação e conjunto de campos preservado**: em vez de
   `assertNotContains` sobre o HTML renderizado (frágil — testa string, não
   composição), verificar a fonte dos 2 templates migrados (leitura direta
   do `.html` no teste) confirmando que `filter_shell.html#abertura` é
   incluído e que os blocos de campo inline antigos não estão mais
   presentes. Complementar com asserções sobre a resposta renderizada que
   fixem, por tela, todos os campos esperados via seus atributos
   `name`/`id` (`texto`/`material`, `data_ini`, `data_fim`, `setor` quando
   `mostrar_filtro_setor`, `estados`/`tipos`), incluindo o caso condicional
   do filtro de setor, e confirmando que o chip "só saídas" continua
   composto fora de `filter_shell.html#abertura` (não migra para dentro do
   shell).

## Invariantes preservadas

- A11y: labels vinculadas, `fieldset`/`legend` do grupo de checkboxes,
  `focus-visible` rings, alvos de toque `min-h-11`.
- HTMX: `hx-get`, `hx-target`, `hx-push-url="true"` idênticos por tela
  (parametrizados via `action_url`/`target_id`, não codificados no partial).
- Contrato de querystring: nomes de campo GET inalterados.
- `tem_filtro_ativo` continua controlando a exibição do link "Limpar
  filtros".
- Filtro de setor continua condicional a `mostrar_filtro_setor`.

## Riscos

- **Tailwind v4 `sm:block!`**: sufixo `!important` — exige
  `npm run css:build` após a mudança para o CSS compilado refletir a classe
  (já usada em `historico_requisicoes.html`, mas precisa estar presente no
  build atual para `historico_movimentacoes.html` também).
- **Composição por posição**: `filter_shell.html#abertura` deixa `<div
  class="grid ...">` aberto para o chamador fechar — risco de esquecer o
  `</div>` de fechamento ao migrar uma das 2 telas; mitigado pelo teste de
  paridade estrutural com parser HTML (item 1 da estratégia de testes, não
  apenas checagem de substring).
- Nenhum risco de concorrência, migração de schema ou mudança de contrato
  OpenAPI — mudança é puramente de template.
