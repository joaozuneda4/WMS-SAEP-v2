# DESIGN_BRIEF — Top App Bar (MD2)

> Componente reutilizável de Top App Bar seguindo Material Design 2, integrado ao layout autenticado do WMS-SAEP. Substitui o `.site-header` legado.

## Objetivo

Prover uma barra superior consistente para todas as telas autenticadas, oferecendo branding, título contextual, navegação principal e slots para ações específicas de tela — pinned, acessível e responsiva.

## Escopo desta entrega

| Decisão | Valor |
|---|---|
| Stack | Django template + Tailwind v4 (`@layer components`) + Alpine 3 inline (mínimo) |
| Local | `apps/core/templates/base_auth.html` (não é include separado) |
| API | Slots via `{% block %}` no `base_auth.html` |
| Variant | **regular** apenas |
| Scroll behavior | **pinned** (`position: sticky`) |
| Elevação | Borda inferior + sombra sutil **estática** (sem listener de scroll) |
| Acessibilidade | `role="banner"` no header, `<nav aria-label="Navegação principal">`, focus visível, labels PT-BR em ícones |
| Cor | Mantém `slate-900` (continuidade de marca); texto `slate-50` |
| Altura | `--app-bar-height` (CSS var) — 3.5rem mobile, 4rem ≥ sm |
| Menu hamburger | Abre um **drawer** lateral (popover) com seções Navegação e Conta |

## API (slots)

Blocks expostos no `base_auth.html`:

| Block | Default | Quando sobrescrever |
|---|---|---|
| `topbar_leading` | Brand (logo + nome) | Subtelas: trocar por nav icon (back/close) + título contextual |
| `topbar_title` | _(vazio; título vai no leading no pattern atual)_ | Reservado para futuro uso isolado |
| `topbar_actions` | _(vazio)_ | Botões/links de ação principal da tela |
| `topbar_overflow` | _(vazio; não renderiza UI)_ | Reservado para futura impl de menu more_vert |

Pattern de uso em subtela:

```django
{% block topbar_leading %}
  <a href="{{ voltar_url }}" class="app-bar__nav-icon" aria-label="Voltar">
    <svg ...>...</svg>
  </a>
  <h1 class="app-bar__title">{{ titulo }}</h1>
{% endblock %}

{% block topbar_actions %}
  <button class="app-bar__action" type="submit" form="form-x">Salvar</button>
{% endblock %}
```

## Classes CSS (em `@layer components`)

- `.app-bar` — header sticky, surface, borda+sombra estática
- `.app-bar__inner` — container max-width + flex layout
- `.app-bar__leading` — grupo esquerdo (brand OU nav-icon + título)
- `.app-bar__brand` — logo + nome (default leading)
- `.app-bar__nav-icon` — botão ícone de navegação (back/close/menu), 48dp touch target, focus visível
- `.app-bar__title` — título da tela, ellipsis, 16/18px medium
- `.app-bar__nav` — navegação principal (lista de links)
- `.app-bar__nav-link` — link de navegação, estado `aria-current="page"`
- `.app-bar__nav-toggle` — botão hamburguer mobile (Alpine `x-data`)
- `.app-bar__actions` — grupo de ações da tela à direita
- `.app-bar__action` — botão/link de ação individual
- `.app-bar__user` — bloco de identidade (avatar + nome + logout)

CSS custom property `--app-bar-height` permite que `<main>` calcule offset e que futuros variants (`dense`, `prominent`) ajustem altura sem reescrita.

## Acessibilidade

- `<header role="banner">` com `<nav aria-label="Navegação principal">` interna.
- Todo ícone interativo tem `aria-label` PT-BR (“Voltar”, “Abrir menu de navegação”, “Sair”).
- Focus visível via `outline: 2px solid` + `outline-offset: 2px`.
- Contraste WCAG AA: `slate-50` sobre `slate-900` ≈ 16:1.
- Navegação por teclado nativa (Tab/Shift+Tab); botões `<button>` e links `<a>`.
- Conteúdo principal recebe `padding-top` ou margin equivalente a `--app-bar-height` para evitar sobreposição.

## Responsividade

| Breakpoint | Comportamento |
|---|---|
| `< 640px` | `.app-bar__nav` colapsa em menu toggleável (Alpine `open` state); ações inline limitadas |
| `≥ 640px` | Nav inline; toggle escondido; user block completo (avatar + nome + matrícula) |

`flex-wrap` permite que o nav vá para baixo quando aberto no mobile sem quebrar o leading/user.

## Fora do escopo (documentado, não implementado)

| Item | Por quê | Quando reabrir |
|---|---|---|
| `variant: dense` | App mobile-first; sem caso de uso | Quando tela densa (admin/relatório) surgir |
| `variant: prominent` | Requer collapseOnScroll p/ valor real | Quando branding/hero de tela exigir |
| `behavior: hideOnScroll` | Quebra UX com swaps htmx | Se telas longas de leitura forem adicionadas |
| `behavior: collapseOnScroll` | Acoplado a `prominent` | Junto com `prominent` |
| Modo contextual (`selectedCount`, `onCancelContextualMode`) | Nenhuma tela tem multi-select hoje | Quando primeiro multi-select for projetado |
| Overflow menu interativo (`more_vert` + dropdown) | Sem ação secundária na fila | Quando alguma tela tiver ≥ 3 ações |
| Elevação dinâmica ao rolar | Listener de scroll + Alpine sem ganho real (já há borda) | Se design pedir distinção forte |

## Critérios de aceitação

- [ ] Header aparece no topo, sticky, em todas as telas autenticadas.
- [ ] Brand (logo + WMS-SAEP) é o leading default.
- [ ] Subtelas (`detalhe.html`, `rascunho_form.html`) renderizam back + título via `{% block topbar_leading %}` sem usar classes legadas.
- [ ] Nav principal (Minhas requisições / Nova requisição) acessível por teclado, com `aria-current="page"` na rota ativa.
- [ ] Toggle mobile funciona via Alpine; nav colapsa <640px.
- [ ] `<main>` não fica sobreposto pelo header.
- [ ] Borda inferior + sombra sutil estática visíveis.
- [ ] Classes `.site-header*` / `.site-nav*` removidas completamente do `input.css` e `app.css`.
- [ ] `npm run css:build` recompila sem erro.
- [ ] `uv run ruff format --check .` e `uv run ruff check .` passam.

## Call-sites a migrar

- `apps/requisicoes/templates/requisicoes/detalhe.html` (linhas 7-16): `.site-header-back`, `.site-header-title` → `.app-bar__nav-icon`, `.app-bar__title`.
- `apps/requisicoes/templates/requisicoes/rascunho_form.html` (linhas 12-28): mesmo padrão.

## Referências

- [Material Design 2 — App bars: top](https://m2.material.io/components/app-bars-top)
- ADR-0008 — Server-rendered frontend e design system
- `docs/design-system.md` — Filosofia Pragmatic Minimal
