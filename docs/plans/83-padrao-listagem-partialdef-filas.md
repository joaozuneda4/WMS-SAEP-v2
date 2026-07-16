# Plano — Issue #83: padrão de listagem responsiva via `{% partialdef %}` (filas gêmeas)

Epic: #68. Bloqueadores #70, #71, #72, #76 — todos `CLOSED`, componentes já existem em
`apps/core/templates/components/` (`pagination.html`, `empty_state.html`, `badge.html`, `button.html`).

## Decisões confirmadas com o usuário (HITL)

1. **`{% partialdef resultados %}` já entra nas 2 telas reais agora**, mesmo sem swap HTMX hoje — zero
   mudança de output renderizado, mas prova o padrão de fato (não só em prosa no design-system.md) e
   deixa pronto pra `view` futura renderizar `fila_x.html#resultados` num swap parcial.
2. **Só os fragmentos de abertura viram `partialdef`** (`tabela_abertura`, `th`, `cards_abertura`,
   `card_abertura`). Fechamentos (`</table></div>`, `</div>`, `</article>`) são triviais, carregam
   nenhuma string de classe pra deduplicar, e ficam literais nas telas — minimiza abstração e resolve
   o critério de aceite ao pé da letra ("string de classes de `<th>` não aparece mais inline").

## Escopo

**Entra:**
- `apps/core/templates/components/table.html` novo — chrome componentizado via `{% partialdef %}`
  (wrapper desktop, `<th>` genérico com alinhamento, container mobile, card).
- Reescrita de `apps/requisicoes/templates/requisicoes/fila_atendimento.html` e
  `fila_autorizacao.html` sobre o padrão, com bloco de resultado (cards + tabela + empty_state)
  envolvido em `{% partialdef resultados %}` (renderizado inline via `{% partial resultados %}`
  logo abaixo do parágrafo de introdução — sem uso HTMX ainda).
- `docs/design-system.md` — nova seção curta "Listagem responsiva" (substitui o "adiado" da seção
  8 "tables") com exemplo canônico de uso do chrome + explicação do one-template pattern.

**Não entra (fora de escopo, conforme a issue):**
- Views das 2 filas — zero mudança de lógica, contexto ou querysets.
- Ordenação, filtros, paginação (as filas hoje não paginam; não vamos adicionar `page_obj` porque
  isso exigiria mexer na view).
- Qualquer outra tela de listagem (fica pra #87, que só começa depois deste merge).

## Arquivos tocados

| Arquivo | Mudança |
|---|---|
| `apps/core/templates/components/table.html` | **Novo.** 4 `partialdef`: `tabela_abertura`, `th`, `cards_abertura`, `card_abertura`. Comentário de doc + exemplo no topo. |
| `apps/requisicoes/templates/requisicoes/fila_atendimento.html` | Reescrito sobre o chrome; ~129 → ~60-70 linhas. |
| `apps/requisicoes/templates/requisicoes/fila_autorizacao.html` | Reescrito sobre o chrome; ~107 → ~55-65 linhas. |
| `docs/design-system.md` | Seção 8 "tables (adiar)" substituída por "Listagem responsiva" com o padrão + exemplo. Atualizar índice de `## Organização dos componentes` (já lista `table.html` — nenhuma mudança necessária ali). |

Nenhum arquivo de `services`, `policies`, `selectors`, `views` ou `models` é tocado.

## Design do `table.html`

```django
{% partialdef tabela_abertura %}
<div class="hidden overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm sm:block">
  <table class="min-w-full divide-y divide-slate-200">
{% endpartialdef %}

{% partialdef th %}
<th scope="col" class="px-4 py-3 text-{% if alinhamento == 'direita' %}right{% else %}left{% endif %} text-xs font-semibold uppercase tracking-wide text-slate-500">{% if rotulo_somente_leitura %}<span class="sr-only">{{ rotulo_somente_leitura }}</span>{% else %}{{ rotulo }}{% endif %}</th>
{% endpartialdef %}

{% partialdef cards_abertura %}
<div class="space-y-3 sm:hidden">
{% endpartialdef %}

{% partialdef card_abertura %}
<article class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
{% endpartialdef %}
```

Parâmetros do `th`: `rotulo` (obrigatório se não for coluna de ação), `alinhamento` (opcional,
`"direita"`, default esquerda), `rotulo_somente_leitura` (opcional — renderiza `<span class="sr-only">`
em vez do rótulo visível; usado na coluna "Ações").

`tabela_abertura`, `cards_abertura` e `card_abertura` não recebem parâmetro nenhum — são strings de
classe fixas. O comentário de topo do arquivo deixa isso explícito para não virarem alvo de
parametrização futura (ex. tentar passar `class` extra) sem antes registrar a decisão, coerente com o
guardrail da issue ("se o chrome precisar de parâmetro que descreve conteúdo de célula, a abstração está
errada").

Uso nas telas (via `{% include "components/table.html#th" with ... %}` e
`{% include "components/table.html#cards_abertura" %}` / `#tabela_abertura` / `#card_abertura`).
Fechamentos ficam literais: `</div>` após o loop de cards, `</tbody></table></div>` após o corpo
da tabela, `</article>` ao fim de cada card.

## Estratégia de teste

Suíte existente já cobre paridade visual por conteúdo (não por string de classe), serve como rede de
regressão sem alteração:
- `test_fila_atendimento_aux_almox_renderiza_autorizada_e_pronta` — título, botão "Atender".
- `test_fila_atendimento_botao_atender_preserva_aria_label` — `aria-label` composto.
- `test_fila_atendimento_vazia_renderiza_empty_state` — empty state.
- `test_fila_atendimento_coluna_autorizada_em` / `test_fila_autorizacao_coluna_enviada_em` — rótulo de
  coluna de data por tela (garante que o `th`/`dt` explícito de cada tela não vira genérico).
- Equivalentes em `fila_autorizacao` (`test_fila_autorizacao_chefe_renderiza_apenas_setor`,
  `test_fila_autorizacao_superuser_ve_todos_setores`, `test_fila_autorizacao_ator_sem_permissao_retorna_403`).

Não é necessário criar novo teste de comportamento (nenhuma lógica nova) — mas será adicionado 1 teste
de regressão por tela garantindo que o `<caption class="sr-only">` e o `<span class="sr-only">Ações</span>`
continuam presentes após a extração do chrome, já que esses dois elementos passam a ser produzidos por
fragmento compartilhado (`th` com `rotulo_somente_leitura`) e um erro de parâmetro nesse fragmento
quebraria as 2 telas ao mesmo tempo — o tipo de regressão silenciosa que este refactor pode introduzir.

Nomes fixados:
- `test_fila_atendimento_caption_e_acoes_sr_only_apos_refactor_chrome`
- `test_fila_autorizacao_caption_e_acoes_sr_only_apos_refactor_chrome`

Cada um faz `assertContains` em `<caption class="sr-only">` (texto específico da tela) e em
`<span class="sr-only">Ações</span>`.

Rodar suíte completa (`uv run pytest -q -ra --tb=short --strict-markers --disable-warnings -n logical`)
antes e depois — contagem de passes deve ser igual (mais os 2 testes novos).

## Invariantes (matriz)

Nenhum invariante de `docs/matriz-invariantes.md` é tocado — mudança é puramente de apresentação
(templates), sem alteração de `services`/`policies`/`selectors`/`models`. PER-08 (view e service chamam
a mesma policy) permanece válido porque a view não é tocada.

## Riscos

- **Drift visual silencioso**: `th`/`card`/wrapper compartilhados entre 2 telas — um erro de parâmetro
  quebra as 2 ao mesmo tempo. Mitigado pelos 2 testes novos de `sr-only`/`caption` + suíte existente.
- **Tailwind v4 JIT**: nenhuma classe nova é introduzida (só reorganizadas as mesmas strings) — não deve
  exigir mudança em `app.css`, mas `npm run css:build` roda mesmo assim por precaução, conforme critério
  de aceite do épico. Se `css:build` não gerar diff, isso é esperado (zero classe nova) e será dito
  explicitamente na descrição do PR para o revisor humano, em vez de forçar um diff artificial.
- **Gate humano**: PR precisa de screenshots mobile (375px) + desktop das 2 telas antes de merge — vou
  gerar via preview do browser antes de finalizar. #87 (replicação) só começa depois deste merge.
