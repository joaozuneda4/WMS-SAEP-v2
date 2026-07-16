# Design System — WMS-SAEP

Design system pragmático baseado em Django templates, Tailwind CSS, HTMX e Alpine.js. Cobre tokens visuais, componentes globais reutilizáveis e padrões de interação operacional.

Não é SPA, não é biblioteca JS pesada, não é identidade de marca. É ferramenta de trabalho.

## Princípios

- **Pragmático**: Decidir baseado em necessidade real, não antecipar
- **Operacional**: Usuário entende rápido o que pode fazer, qual estado está, onde há erro
- **Neutro**: Sistema administrativo interno — visual profissional e acessível
- **Simples**: Componentes com responsabilidade clara; sem excesso de parâmetros
- **Progressivo**: HTMX/Alpine para interação incremental; sem estado de domínio no JavaScript

## Tokens visuais

### Paleta base

**Cores neutras** — slate para fundos, bordas, texto

```
slate-50, slate-100, slate-200, slate-300, slate-700, slate-900
```

**Cor primária** — blue para ações, focos, accents

```
blue-50, blue-100, blue-200, blue-500, blue-600, blue-700, blue-800
```

**Semântica de estado**

```
success:  green     (requisição atendida, saldo disponível)
warning:  amber     (ação requer atenção/decisão)
danger:   red       (negação, erro, divergência, risco)
info:     slate     (neutro, informacional)
return:   teal      (devolução operacional, reversão não-negativa)
```

### Shades — regra de aplicação

```
50–100   = fundos suaves, hover leve, badge/background
200–300  = bordas suaves, separadores, ring
400–500  = foco (ring-blue-500), bordas ativas, ícones
500–600  = ação primária (bg-blue-600)
700–800  = hover/active forte, texto colorido legível
900+     = raro; futura expansão para dark mode
```

### Tipografia

**Fonte do sistema** — sem dependência de CDN

```css
font-family: ui-sans-serif, system-ui, sans-serif;
```

**Hierarquia**

```
h1:      tela title (text-2xl/3xl)
h2:      seção (text-xl)
body:    conteúdo (text-base)
small:   metadados, timestamp, badges (text-xs)
```

### Espaçamento

Usar Tailwind defaults; customização sob demanda. Padrão conservador:

```
container:  max-w-5xl
padding:    p-4, p-6 (cards, seções)
gap:        gap-4, gap-6 (flex/grid)
rounded:    rounded-lg (cards, inputs)
            rounded-full (badges, pills)
```

### Sombras e bordas

```
cards:    shadow-sm border border-slate-200
inputs:   border border-slate-300
focus:    border-blue-500 ring-2 ring-blue-500 ring-offset-2
```

## Estados de UI

### Desabilitado (ação bloqueada por permissão/estado)

**Visual**: slate neutro com motivo textual

```
bg-slate-200 text-slate-500 cursor-not-allowed
```

**Comportamento**:
- Ação de workflow (autorizar, atender, etc) = **visível + disabled + motivo**
- Ação administrativa/irrelevante = **esconder da markup**

**Motivo**:
```
Disponível apenas para o chefe do setor do beneficiário.
```

**ARIA**:
```
aria-disabled="true" (se não usa atributo HTML disabled)
title="motivo" (tooltip)
```

**Exemplo**:
```django
{% if pode_autorizar %}
  {% include "components/button.html" with label="Autorizar" %}
{% else %}
  {% include "components/button.html" with 
    label="Autorizar"
    disabled=True
    title="Apenas chefe de setor pode autorizar"
  %}
{% endif %}
```

### Loading (operação em andamento)

**Visual**: preserva variante + spinner inline + texto de progresso

```
[spinner] Registrando atendimento...
```

**Comportamento**:
- disabled obrigatório
- pointer-events-none
- cursor-wait
- aria-busy="true"

**ARIA**:
```
aria-busy="true"
aria-label ou screen reader vê o label
```

**CSS**:
```
opacity-75 preserve-variant
```

**Exemplo**:
```django
{% if loading %}
  <button disabled aria-busy="true">
    <svg class="spinner inline">...</svg>
    Registrando atendimento...
  </button>
{% else %}
  <button>Atender requisição</button>
{% endif %}
```

### Readonly (campo preenchido, não edita)

**Visual**: bg-slate-50, sem border ativo, cursor padrão

```
bg-slate-50 border border-slate-200 cursor-default
```

**Não usar**:
- `disabled` (impede submission)
- `aria-disabled` (não é semanticamente desabilitado)

**HTML**:
```html
<input type="text" readonly value="...">
```

### Foco (teclado/acessibilidade)

**Ring global** para inputs, buttons, links

```
focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2
```

**Inputs + botões**:
```
focus:border-blue-500
focus:ring-2 focus:ring-blue-500
```

**Perigo**: em ações destrutivas, pode usar ring-red-500 para semântica clara. Preferência: azul global.

## Acessibilidade — requisitos obrigatórios

### Contraste

- Texto: mínimo WCAG AA (4.5:1 contrast ratio)
- Gráficos/bordas: 3:1
- Badges: testar antes de codar

**Exemplos seguros**:
```
text-slate-700 on bg-slate-100 ✓
text-amber-800 on bg-amber-50  ✓ (amber-800 bem escuro)
text-blue-700 on bg-blue-50    ✓
```

### Foco visível

Todos os controles interativos (button, input, link, dropdown) devem ter `focus-visible` claro.

Nunca remover outline com `outline: none` sem substituir.

### ARIA

**Buttons**:
```html
<button aria-busy="true"><!-- loading --></button>
<button aria-disabled="true"><!-- disabled --></button>
```

**Inputs com erro**:
```html
<input aria-invalid="true" aria-describedby="field-error">
<span id="field-error">Matrícula já cadastrada</span>
```

**Alerts**:
```html
<div role="alert"><!-- erro crítico --></div>
<div role="status"><!-- sucesso --></div>
```

**Modais**:
```html
<div role="dialog" aria-modal="true" aria-labelledby="modal-title">
  <h2 id="modal-title">Confirmar atendimento</h2>
</div>
```

### Teclado

- Tab = navega entre controles
- Shift+Tab = retrocede
- Enter/Espaço = ativa button
- Escape = fecha modal/dropdown
- Setas = navega dentro dropdown (nice-to-have)

**Modal deve**:
- Trap foco dentro modal
- Restaurar foco no gatilho ao fechar

**Dropdown deve**:
- Abrir com Enter/Espaço
- Fechar com Escape
- Tab navega itens

### Aria-live para HTMX

Quando HTMX atualiza conteúdo crítico, usar aria-live:

```html
<div aria-live="polite" aria-atomic="true">
  <!-- mensagem de sucesso aparece aqui via HTMX -->
</div>
```

Use `polite` para mensagens normais; `assertive` apenas para erro crítico.

## Granularidade de componentes

### Componente global (core)

Vive em `apps/core/templates/components/`

- Conhece: variantes visuais, estados, ARIA
- Não conhece: semântica de domínio

**Exemplos**:
```
button.html         (variant, size, state)
form_field.html     (label, error, required)
badge.html           (variant color, label)
alert.html          (role, message)
card.html           (header, body, footer)
```

**Decisão**: se precisa de `status="autorizada"` ou `estado="requisicao"`, não é componente global. Cria partial de domínio.

### Partial de domínio (app)

Vive em `apps/<app>/templates/<app>/partials/`

- Conhece: semântica de negócio, estados, enum do app
- Usa: componentes globais internamente

**Exemplos**:
```
_estado_badge.html      (mapeia EstadoRequisicao → variant)
_acoes_requisicao.html  (botões + permissões + HTMX)
_filtros_fila.html      (filtros + busca da fila)
```

### Inline HTML

Permitido para:
- Bloco usado uma única vez
- Fluxo ainda instável
- Muito acoplado à tela

Extrair para componente/partial quando:
- Reutilizado 2+ vezes
- Padrão visual estabiliza
- Mudança central precisa se refletir em vários lugares

## Organização dos componentes

**Estrutura flat** em `apps/core/templates/components/`

```
components/
  button.html
  form_field.html
  form_errors.html
  card.html
  alert.html
  badge.html
  page_header.html
  modal.html
  table.html
  table_empty.html
  dropdown.html
  pagination.html
  ...
```

**Nomes explícitos com prefixos semânticos** quando necessário:
```
form_field.html
form_errors.html
table_empty.html
badge.html
```

**Hierarquia só se ultrapassar 30–40 componentes** ou surgirem famílias grandes (ex: forms/* com 10+ subcomponentes).

## Inventário inicial

### 1. button.html

Render: `<button>`

Parâmetros:
```
variant       default=primary (primary, secondary, danger, ghost, link)
size          default=md (sm, md, lg)
type          default=button (button, submit)
label         (obrigatório)
disabled      (boolean)
loading       (boolean)
loading_label (opcional, se loading)
icon          (opcional)
icon_position default=left (left, right)
class         (passthrough para ajustes layout)
hx_*          (hx_get, hx_post, hx_target, hx_swap, hx_confirm, etc)
```

Comportamento:
- Primary: bg-blue-600 hover:bg-blue-700 active:bg-blue-800
- Secondary: bg-white text-slate-700 border border-slate-300 hover:bg-slate-50
- Danger: bg-red-600 hover:bg-red-700
- Ghost: bg-transparent text-slate-700 hover:bg-slate-100
- Link: text-blue-700 hover:underline
- Loading: disabled + aria-busy + spinner inline + text

### 2. form_field.html

Render: wrapper <label>/<input> com ajudas e erros

Parâmetros:
```
field           Django form field (obrigatório)
help_text       (opcional, sobrescreve field.help_text)
```

Comportamento:
- Label vinculada ao input
- Mostra field.help_text abaixo
- Mostra errors se houver
- required="*" se campo obrigatório
- focus:border-blue-500 focus:ring-blue-500
- aria-invalid/aria-describedby se erro

### 3. card.html

Render: `<div>` com bordas, fundo branco, sombra

Parâmetros:
```
header   (slot opcional)
body     (slot; conteúdo principal)
footer   (slot opcional)
class    (ajustes layout)
```

Comportamento:
- bg-white border border-slate-200 shadow-sm rounded-lg
- Padding interno conservador
- Preservar fluidez de conteúdo

### 4. alert.html

Render: `<div role="alert" ou role="status">`

Parâmetros:
```
variant   default=info (info, success, warning, danger)
message   (obrigatório)
icon      (opcional)
class     (ajustes)
```

Comportamento:
- Info/success: role="status"
- Warning/danger: role="alert"
- Cores baseadas em paleta semântica
- aria-live="polite" se dinâmico

### 5. badge.html

Render: `<span>` compacto com cor e label

Parâmetros:
```
variant     (slate, blue, blue-strong, amber, amber-strong, green, red,
             red-strong, orange, teal, indigo, violet, yellow)
label       (obrigatório)
role        (opcional — propagado literalmente como role="{{ role }}")
aria_label  (opcional — propagado literalmente como aria-label="{{ aria_label }}")
```

Comportamento:
- Não conhece estados de requisição
- Baseado apenas em variante visual
- Partial de domínio mapeia estado → variant, e decide `role`/`aria_label` (ex. `role="status"` para estados de listagem)

### 6. page_header.html

Render: cabeçalho de página com título, ações, breadcrumb

Parâmetros:
```
title     (obrigatório)
subtitle  (opcional)
actions   (opcional, conteúdo HTML ou botões)
breadcrumb (opcional, lista de links)
```

### 7. modal.html (adiar até uso real)

Render: `<dialog>` ou `<div role="dialog">`

Adiado. Implementar quando houver HTMX modal concreto.

### 8. Listagem responsiva (cards mobile + tabela desktop)

Render: `<table>` desktop (`sm:` acima) + cards `<article>` mobile — mesmo dado, duas
apresentações. Chrome vive em `apps/core/templates/components/table.html`, via
`{% partialdef %}` nativo do Django 6 (`{% partialdef nome %}...{% endpartialdef %}`
define; `{% include "components/table.html#nome" with ... %}` renderiza de outro
arquivo). Implementado a partir das filas gêmeas (`fila_atendimento.html`,
`fila_autorizacao.html` — issue #83).

**Decisão de arquitetura**: nada de `DataTable` genérico config-driven (colunas como
lista de dicts) — células reais têm HTML rico e condicional de domínio; uma DSL de
colunas seria pior que HTML explícito e hostil ao ARIA custom. Só as **aberturas**
com string de classe canônica viram `partialdef` — fechamentos (`</table>`, `</div>`,
`</article>`) são triviais e ficam literais na tela. Células `<td>` e conteúdo do
card permanecem 100% explícitos na tela chamadora.

Fragmentos disponíveis:
```text
tabela_abertura   wrapper desktop: div.hidden...sm:block + table.min-w-full
                  (fechamento literal: </tbody></table></div>)
th                <th scope="col"> — rotulo, alinhamento ("direita", default
                  esquerda), rotulo_somente_leitura (renderiza <span class="sr-only">)
cards_abertura    container mobile: div.space-y-3.sm:hidden
                  (fechamento literal: </div>)
card_abertura     card individual: article.rounded-xl...
                  (fechamento literal: </article>)
```

**Contrato do `<caption>`**: `tabela_abertura` não inclui `<caption>` — a tela chamadora
fornece a sua, com descrição específica da listagem, imediatamente após o
`{% include "components/table.html#tabela_abertura" %}` (ver exemplo abaixo). O
componente compartilhado não conhece semântica de negócio o suficiente para descrever
o que a tabela lista; colocar a caption nele generalizaria conteúdo de célula, o que o
guardrail abaixo proíbe. Divergência entre este contrato e o código (ex. tela sem
caption, ou caption dentro do chrome) deve ser sinalizada em vez de silenciosamente
replicada.

**Guardrail**: se o chrome precisar de parâmetro que descreve conteúdo de célula
(não estrutura visual), a abstração está errada — parar e registrar, não generalizar.

**One-template pattern (HTMX)**: a própria tela envolve o bloco de resultado
(cards + tabela + empty state) em `{% partialdef resultados %}` e renderiza com
`{% partial resultados %}` logo abaixo. Isso elimina o par página/partial em
arquivos separados: quando uma tela ganhar swap HTMX (filtro, paginação), a view
passa a renderizar `template.html#resultados` para esse mesmo fragmento — sempre
**GET-only**. Transições de estado de domínio continuam retornando `204` com
`HX-Redirect` (`docs/CONVENTIONS.md`); este fragmento nunca é alvo delas.

Exemplo canônico:
```django
{% partialdef resultados %}
{% if lista %}
  {% include "components/table.html#cards_abertura" %}
    {% for item in lista %}
      {% include "components/table.html#card_abertura" %}
        <div class="flex items-start justify-between gap-3">
          <h2 class="break-words text-sm font-semibold text-slate-900">{{ item.titulo }}</h2>
          <span class="shrink-0">{% include "components/badge.html" with variant="blue" label="Estado" %}</span>
        </div>
        {# dl explícito + botão explícito #}
      </article>
    {% endfor %}
  </div>

  {% include "components/table.html#tabela_abertura" %}
    <caption class="sr-only">Descrição da listagem.</caption>
    <thead class="bg-slate-50">
      <tr>
        {% include "components/table.html#th" with rotulo="Número" %}
        {% include "components/table.html#th" with alinhamento="direita" rotulo_somente_leitura="Ações" %}
      </tr>
    </thead>
    <tbody class="divide-y divide-slate-100 bg-white">
      {# <tr><td>...</td></tr> explícito #}
    </tbody>
  </table>
  </div>
{% else %}
  {% include 'components/empty_state.html' with titulo='Nada por aqui' %}
{% endif %}
{% endpartialdef %}
{% partial resultados %}
```

## Code review — checklist acessibilidade

Ao revisar componente novo ou tela que usa componentes:

```
[ ] Contraste mínimo WCAG AA (testar com ferramenta)
[ ] Todos controles interativos têm focus-visible
[ ] Botões loading usam aria-busy="true"
[ ] Campos com erro usam aria-invalid="true" + aria-describedby
[ ] Campos readonly e disabled visualmente distintos
[ ] Modais/dropdowns funcionam com teclado (Tab, Escape, Enter/Espaço)
[ ] Ações disabled têm motivo textual quando relevante
[ ] HTMX updates críticos usam aria-live ou feedback visível
[ ] Alternativas de texto para ícones (aria-label, title, ou context)
```

## Exemplos de uso

### Botão primário com HTMX

```django
{% include "components/button.html" with
  label="Autorizar requisição"
  variant="primary"
  hx_post="/api/requisicoes/1/autorizar/"
  hx_target="#requisicao"
  hx_swap="outerHTML"
  hx_confirm="Tem certeza que quer autorizar?"
%}
```

### Campo de formulário

```django
{% include "components/form_field.html" with field=form.matricula %}
```

### Card com ações

```django
{% include "components/card.html" %}
  {% block header %}
    <h2>Dados da requisição</h2>
  {% endblock %}
  {% block body %}
    <dl>
      <dt>Matrícula</dt>
      <dd>{{ requisicao.criador.matricula }}</dd>
    </dl>
  {% endblock %}
  {% block footer %}
    {% include "components/button.html" with label="Editar" %}
  {% endblock %}
{% endinclude %}
```

### Badge de estado (via partial de domínio)

```django
{# Em requisicoes/partials/_estado_badge.html #}
{% if requisicao.estado == "rascunho" %}
  {% include "components/badge.html" with variant="slate" label="Rascunho" %}
{% elif requisicao.estado == "autorizada" %}
  {% include "components/badge.html" with variant="blue" label="Autorizada" %}
{% endif %}
```

Uso na tela:
```django
{% include "requisicoes/partials/_estado_badge.html" with requisicao=requisicao %}
```

## Quando aparecer identidade corporativa da SAEP

Se a SAEP trouxer guideline oficial (logo, cores, tipografia):

1. Atualizar `docs/design-system.md` com novos tokens
2. Não alterar templates individuais
3. Tokens levam mudanças; componentes herdam

Isso é possível porque componentes usam `variant="primary"`, não `bg-blue-600` direto.

## Futuro — dark mode, themes

Adiado. Sistema começa em light mode.

Se dark mode virar requisito: usar CSS custom properties (`--color-primary`, etc) e media query `prefers-color-scheme`.

Componentes já estão estruturados pra suportar isso sem reescrever.
