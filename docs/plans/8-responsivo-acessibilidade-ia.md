# Plano — Issue #8: Movimentações de estoque: responsivo mobile, acessibilidade e IA

## Escopo

### O que muda
- `historico_movimentacoes.html`: barra de filtros ganha disclosure (Alpine `x-show`) no mobile; campos empilhados full-width `min-h-11`; chip "só saídas" sempre visível (já está fora do form).
- `.design/INFORMATION_ARCHITECTURE.md`: registrar rota `/estoque/movimentacoes/` e item de menu "Movimentações" (RBAC: almox/chefe setor com `pode_consultar_movimentacoes_estoque`).

### O que NÃO muda
- Lógica de backend (selectors, view, policies) — já entregue nas issues #6 e #7.
- Templates de partials (`_tabela_movimentacoes.html`, `_badge_tipo_movimentacao.html`, `_chip_so_saidas.html`, `_paginacao.html`, `_delta_movimentacao.html`) — já corretos.
- `_topbar_nav.html` — item "Movimentações" já existe condicionado a `pode_consultar_movimentacoes_estoque`.
- Schema, modelos, migrations.

## Arquivos tocados

| Arquivo | Ação |
|---|---|
| `apps/estoque/templates/estoque/historico_movimentacoes.html` | Modificar: filtros em disclosure Alpine no mobile |
| `.design/INFORMATION_ARCHITECTURE.md` | Modificar: adicionar rota e item de nav estoque |

## Estratégia de implementação

### 1. Barra de filtros responsiva — disclosure no mobile

Objetivo: em `< sm` o form de filtros fica colapsado atrás de um botão "Filtros" (summary/botão Alpine); ao clicar, expande. Chip "só saídas" permanece fora do disclosure e sempre visível.

**Abordagem**: wrapping do `<form>` em um div Alpine com `x-data="{ aberto: false }"`. No mobile (`sm:hidden`) renderiza botão toggle. No desktop (`hidden sm:block`) tudo expandido sem toggle. Para não duplicar o form, usa `sm:block` no wrapper interno e o toggle é `sm:hidden`.

**Pattern concreto** (baseado em Alpine.js `x-show`):

```html
<div x-data="{ aberto: false }">
  {# Botão toggle — apenas mobile #}
  <button
    type="button"
    @click="aberto = !aberto"
    :aria-expanded="aberto.toString()"
    class="sm:hidden mb-4 inline-flex min-h-11 w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
  >
    Filtros
    <span aria-hidden="true" x-text="aberto ? '▲' : '▼'"></span>
  </button>

  {# Form: mobile = visível só se aberto; desktop = sempre visível #}
  <form
    x-show="aberto"
    :class="{ 'sm:block': true }"  {# garante visível no desktop via CSS #}
    class="hidden sm:block ..."
    ...
  >
  ...
  </form>
</div>
```

Simplificação mais limpa: `class="sm:block"` no `<form>` + `x-show="aberto || window.matchMedia('(min-width: 640px)').matches"`. Porém Alpine `x-show` usa `display: none` inline que sobrescreve classes. A solução padrão é separar o comportamento:

- No desktop: form tem `sm:!block` (importante pra sobrescrever o `display:none` do Alpine).
- No mobile: Alpine controla.

Alternativa mais simples e robusta: dois divs separados (mobile-only form + desktop-only form) mas isso duplica HTML.

**Solução escolhida**: usar `x-show` com `sm:!block` (Tailwind `!` prefix para `!important`) no form, e botão toggle com `sm:hidden`. Tailwind gera `sm:!block` = `@media (min-width: 640px) { display: block !important }` que garante override do inline style do Alpine.

### 2. Atualizar IA global

Adicionar seção `/estoque/` no site map e entrada na tabela de navegação do módulo estoque.

## Estratégia de testes

Não há mudança de comportamento de backend — os testes existentes da view e selectors permanecem. A implementação é puramente de template/CSS/Alpine. Não há teste automatizado de Alpine — a verificação é visual (run da app).

A suite pytest deve permanecer verde sem alteração.

## Invariantes relevantes

- Chip "só saídas" **sempre visível** — não pode entrar no disclosure.
- O form de filtros **não pode criar novo alvo de swap** (id `resultados-movimentacoes` é único e fica no template base).
- `aria-live` e `aria-atomic` no wrapper de resultados — já presente, não tocar.

## Riscos

- Alpine `x-show` gera `display: none` inline → pode conflitar com classes Tailwind `sm:block`. Mitigado com `!important` via `sm:!block`.
- Duplicar o form seria solução mais simples mas aumenta manutenção — evitar.
