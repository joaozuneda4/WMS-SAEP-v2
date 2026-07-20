# Plano — #86 refactor(css): tokens semânticos dentro dos componentes

Épico: #68. Blocked by (fechadas): #72 (badge), #76 (button), #77 (alert).

## Decisões tomadas com o usuário antes deste plano

1. **Escopo de arquivos**: `components/` inteiro (não só os 6 itens listados na
   issue). Grep em `apps/core/templates/components/` mostrou cor crua também em
   `filter_shell.html`, `filter_checkbox_group.html`, `filter_busca.html`,
   `filter_acoes.html`, `filter_select.html`, `filter_data.html`,
   `form_field.html`, `autocomplete.html`, `item_form_row.html`, `table.html` —
   nenhum desses migrou cor nas issues que os criaram (#70/#71/#85 só
   extraíram estrutura). Incluídos aqui para o critério de aceite
   ("dentro de `apps/core/templates/components/`") bater literalmente.
2. **Slate**: migrar para os tokens `text-*`/`border-*`/`bg-*` **só onde o
   valor já existe idêntico** (ex. `text-slate-900` → `text-text-primary`).
   Onde não há token com o mesmo valor (`bg-slate-700` do botão secondary do
   modal, `ring-slate-400/500`, `text-slate-600`, `bg-slate-900/50` do
   backdrop), fica cru — não invento token novo pra slate.
3. **Tokens novos**: convenção de sufixo estendendo o vocabulário já usado em
   `input.css` (`-subtle`, `-muted`, `-border`, `-text`, `-hover`, `-active`).
   Tabela completa abaixo.

`white` não entra no escopo — não está na lista de prefixos do critério de
aceite (`blue-`, `red-`, `amber-`, `green-`, `teal-`), fica como está
(`text-white`, `bg-white` sem token equivalente eleito neste PR, exceto os
`bg-white` que colidem 1:1 com `--color-surface`, migrados por serem a mesma
decisão de "bate exato" do item 2).

## Tokens novos em `input.css` `@theme`

| Token | Valor | Consumidores |
|---|---|---|
| `--color-primary-muted-strong` | `blue-200` | badge `blue-strong` (bg) |
| `--color-primary-border-strong` | `blue-300` | badge `blue-strong` (ring) |
| `--color-primary-text-emphasis` | `blue-800` | alert `info` (texto), `_messages.html` info |
| `--color-primary-text-strong` | `blue-900` | badge `blue`/`blue-strong` (texto) |
| `--color-danger-muted-strong` | `red-200` | badge `red-strong` (bg) |
| `--color-danger-border-strong` | `red-300` | badge `red-strong` (ring), button `danger-outline` (border) |
| `--color-danger-border-input` | `red-400` | autocomplete `com_erro` (border) |
| `--color-danger-accent` | `red-500` | button `danger`/`danger-outline` (focus ring), modal `_modal_body` confirm `danger` (focus ring), form_field asterisco obrigatório |
| `--color-danger-hover` | `red-700` | button `danger` (hover), modal `_modal_body` confirm `danger` (hover), badge fallback (ring) |
| `--color-danger-active` | `red-800` | button `danger` (active) |
| `--color-danger-text-emphasis` | `red-800` | alert `danger`, `_messages.html` error |
| `--color-danger-text-strong` | `red-900` | badge `red`/`red-strong`, modal `_modal_body` erro (texto) |
| `--color-warning-muted-strong` | `amber-200` | badge `amber-strong` (bg) |
| `--color-warning-border-strong` | `amber-300` | badge `amber-strong` (ring) |
| `--color-warning-text-subtle` | `amber-700` | `item_form_row` saldo insuficiente (texto) |
| `--color-warning-text-strong` | `amber-900` | badge `amber`/`amber-strong`, `_messages.html` warning (texto) |
| `--color-success-text-emphasis` | `green-800` | alert `success`, `_messages.html` success |
| `--color-success-text-strong` | `green-900` | badge `green` (texto) |
| `--color-return-text-strong` | `teal-900` | badge `teal` (texto) |

`--color-warning-text` (`amber-800`, já existente, hoje sem consumidor) passa a
ser consumido por alert `warning` e `_modal_icon.html` `warning` — mesmo valor,
sem mudança. `--color-primary-text`/`--color-danger-text` (700, já
consumidos pelo `.app-bar`) passam a ser reaproveitados por `_modal_icon.html`
(`info`/`danger`) e pelo hover do botão remover em `item_form_row.html` — sem
mudança de valor.

Nenhum token novo para `orange`, `indigo`, `violet`, `yellow` (variantes de
badge fora do mapeamento da issue — ficam cru).

## Arquivos tocados e mapeamento

- `apps/core/static/core/css/input.css` — 19 tokens novos no `@theme`.
- `apps/core/static/core/css/app.css` — gerado via `npm run css:build`.
- `docs/design-system.md` §Tokens — documentar tokens novos.
- `apps/core/templates/components/badge.html` — variantes `slate` (slate→token
  onde bate), `blue`/`blue-strong`/`amber`/`amber-strong`/`green`/`red`/
  `red-strong`/`teal` (cor de marca→token); `orange`/`indigo`/`violet`/`yellow`
  inalterados; fallback `red-600`/`red-700`→`danger`/`danger-hover`.
- `apps/core/templates/components/button.html` — `primary`(blue→primary+hover+active+border-focus),
  `secondary`(slate→tokens onde bate), `danger`(red→danger+hover+active),
  `danger-outline`(red→danger-text+danger-border-strong+danger-accent),
  `ghost`/`link` (slate/blue→tokens).
- `apps/core/templates/components/alert.html` — 4 variantes, borda/bg/texto/ícone→tokens
  (`info`→`primary-*`, não `info-*`, ver nota abaixo).
- `apps/core/templates/components/pagination.html` — slate→tokens onde bate; `ring-blue-500`→
  `border-focus`; `text-slate-600`/disabled fica cru (sem token exato).
- `apps/core/templates/components/empty_state.html` — slate→tokens; CTA link `text-blue-600`→
  `text-primary`.
- `apps/core/templates/components/modal.html` — `border-slate-200`/`bg-white`/`text-slate-900`→
  tokens; backdrop `slate-900/50` fica cru (não bate com `surface-overlay`,
  alpha/matiz diferentes).
- `apps/core/templates/components/_modal_body.html` — borda/bg/texto slate→tokens onde bate;
  botão cancelar `ring-slate-400` fica cru; erro→`danger-subtle`/
  `danger-border`/`danger-text-strong`; confirm `danger`→`danger`/
  `danger-hover`/`danger-accent` (ring); confirm `secondary` (`bg-slate-700`)
  fica cru (sem token de superfície pra slate-700, ring-slate-500 idem);
  confirm padrão→`primary`/`primary-hover`/`border-focus` (ring).
- `apps/core/templates/components/_modal_icon.html` — 3 variantes→tokens (`danger`→
  `danger-muted`/`danger-text`; `warning`→`warning-muted`/`warning-text`;
  `info`(else)→`primary-muted`/`primary-text`).
- `apps/core/templates/core/partials/_messages.html` — 4 níveis→tokens (`warning`→`warning-muted`
  (bg)/`warning-border`/`warning-text-strong`; `error`→`danger-*`; `success`→
  `success-*`; default→`primary-*`).
- `apps/core/templates/components/filter_shell.html`,
  `apps/core/templates/components/filter_busca.html`,
  `apps/core/templates/components/filter_select.html`,
  `apps/core/templates/components/filter_data.html`,
  `apps/core/templates/components/filter_checkbox_group.html`,
  `apps/core/templates/components/filter_acoes.html` —
  `ring-blue-500`/`focus:ring-blue-500`→`border-focus`; `bg-blue-600`
  (aplicar filtros)→`primary`+`hover`; `text-blue-600` (checkbox accent)→
  `text-primary`; slate→tokens onde bate.
- `apps/core/templates/components/form_field.html` — asterisco `text-red-500`→`text-danger-accent`;
  erro `text-red-600`→`text-danger`; slate→tokens.
- `apps/core/templates/components/autocomplete.html` — `border-red-400`→`border-danger-border-input`;
  `focus:border-blue-500`/`focus:ring-blue-500`→`border-focus`; item
  selecionado `bg-blue-50`→`bg-primary-subtle`; slate→tokens onde bate.
- `apps/core/templates/components/item_form_row.html` — `border-amber-300 bg-amber-50/40`→
  `border-warning-border-strong bg-warning-subtle/40`; `text-amber-700`→
  `text-warning-text-subtle`; erros `text-red-600`→`text-danger`; remover
  hover `text-red-700`→`text-danger`; `ring-red-600`→`ring-danger`; slate→
  tokens onde bate.
- `apps/core/templates/components/table.html` — `border-slate-200`/`bg-white`/`divide-slate-200`/
  `text-slate-500` (th)→tokens; exemplo dentro do `{% comment %}` também
  atualizado (`bg-slate-50`→`bg-bg-subtle`, `text-slate-900`→
  `text-text-primary`; `divide-slate-100` do exemplo fica cru — sem token
  exato, mesmo caso do critério 2) — senão o grep automatizado acusa falso
  positivo em comentário.

### Nota — `alert.html` variante `info`

O token `--color-info*` existe e mapeia pra `slate` (neutro), mas a variante
`info`/default de `alert.html` **já renderiza azul** (`blue-50/200/800/600`).
Migrar essa variante pro token `info` mudaria a cor renderizada (slate ≠
blue) — viola o critério "zero mudança de cor". Por isso a variante `info` do
alert usa os tokens `primary-*`, não `info-*`. Documentar isso em
`docs/design-system.md` pra não confundir o próximo dev.

## Fora de escopo (fica cru, justificado)

- `orange`, `indigo`, `violet`, `yellow` em `badge.html` — não fazem parte do
  mapeamento pedido pela issue.
- `text-white`/`bg-white` sem correspondência 1:1 já mapeada — `white` não
  está na lista de prefixos do critério de aceite.
- Slate sem token de mesmo valor: `text-slate-600`, `bg-slate-700`/`800`
  (botão secondary do modal), `ring-slate-400`/`500`, `bg-slate-900/50`
  (backdrop do modal).
- Telas/partials de domínio — herdam via componentes, não tocadas.
- Dark mode — adiado (decisão já registrada em `input.css`).

## Estratégia de teste

- Teste automatizado novo (`apps/core/tests/test_tokens_semanticos.py`):
  1. grep programático em `apps/core/templates/components/**/*.html` +
     `apps/core/templates/core/partials/_messages.html` garantindo zero
     ocorrência de `(bg|text|border|ring|divide)-(blue|red|amber|green|teal)-[0-9]`
     fora da lista de exceções documentada (badge
     `orange`/`indigo`/`violet`/`yellow`). Este é o "busca automatizável"
     citado no critério de aceite.
  2. roda `npm run css:build` e valida no `app.css` gerado que os 19 tokens
     novos existem como custom properties e que as utilities consumidas
     pelos templates (ex. `bg-warning-subtle/40` → regra com
     `--color-warning-subtle` presente no `app.css`) foram de fato geradas —
     falha se algum token ficar sem utility correspondente (nome errado,
     typo, ou o Tailwind não reconhecer o `@theme`).
  Isso cobre tanto "cor crua não volta" quanto "token novo realmente gera
  CSS", falhando o CI nos dois cenários de regressão.
- Suíte completa
  (`uv run pytest -q -ra --tb=short --strict-markers --disable-warnings -n logical`)
  — nenhuma mudança de comportamento esperada, só verificação de que
  templates ainda renderizam (testes existentes de view que tocam
  badge/button/alert/modal continuam verdes).
- Verificação manual/visual: `npm run css:build`, abrir telas com badge,
  botões, alert, paginação, modal — comparar cor computada via DevTools antes
  e depois (deve ser idêntica). Prova de rebrand: trocar temporariamente
  `--color-primary` no DevTools e confirmar que botão/badge/modal mudam
  juntos — capturar screenshot pro PR, não commitar a troca.

## Invariantes de domínio

N/A — issue de indireção CSS pura (tokens), sem mudança de comportamento,
services, policies ou selectors.

## Riscos

- Tailwind v4 gera utilitários automaticamente a partir de `@theme`, mas
  preciso conferir cada nome gerado (`bg-primary-muted-strong` etc.) existe
  de fato em `app.css` após `npm run css:build` antes de usar em massa.
- Opacidade em token custom (`bg-warning-subtle/40`) — confirmar que o
  modificador `/40` funciona sobre var CSS gerada pelo Tailwind v4 (deveria,
  já que o token é uma cor sólida, não já alfa-blendada).
- Escopo maior (components/ inteiro) aumenta superfície de regressão visual —
  mitigado pela checagem de cor computada via DevTools em cada arquivo
  tocado.
