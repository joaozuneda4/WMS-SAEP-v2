# ADR-0016 — Paradigma único para linhas de item dinâmicas em formulários

**Status**: Aceita

**Data**: 2026-07-17

**Decisores**: João

## Contexto

Duas telas do sistema precisam de linhas de item dinâmicas (adicionar/remover
material com quantidade dentro de um formulário) e resolveram o problema com
paradigmas diferentes:

1. **HTMX formset server-side** — `requisicoes/rascunho_form.html` +
   `requisicoes/partials/_item_form_row.html` + view `nova_linha_item`
   (`apps/requisicoes/views.py:417`): linhas renderizadas pelo servidor a
   partir de um `ItemRequisicaoFormSet` real, `TOTAL_FORMS` incrementado por
   JS após cada swap HTMX, validação via Django FormSet.
2. **Alpine client-side** — `estoque/nova_saida_excepcional.html`: linhas num
   array Alpine (`x-for` sobre `itens`), management form falso
   (`itens-INITIAL_FORMS` fixo em `0`, sem `Form` real por linha), validação
   manual na view com dicionário `erros`, guarda de duplicidade de material
   inteiramente em JS (`selecionarMaterial`).

A coexistência gerou markup duplicado com drift (autocomplete, botão remover,
layout de quantidade), a tela de saída excepcional fora do padrão de forms do
projeto (sem `forms.Form`, sem contrato de erro por campo consistente com o
resto do sistema) e a necessidade de decidir de novo a cada tela nova com
itens dinâmicos.

Auditoria arquitetural de 2026-07 (épico #68) recomendou o paradigma
server-side, mas registrou a decisão como HITL (issue #82) por afetar o
contrato de formulário de uma tela já em produção (`nova_saida_excepcional`).

## Decisão

Adotar o **HTMX formset server-side** como paradigma único para linhas de
item dinâmicas em formulários do projeto.

Consequências obrigatórias:

- toda tela nova com itens dinâmicos usa um Django `FormSet` real (ou
  `formset_factory`), com `management_form` renderizado pelo Django, endpoint
  HTMX próprio para nova linha e swap incremental — seguindo o padrão já
  estabelecido em `requisicoes/rascunho_form.html`. O contrato HTMX de
  `docs/CONVENTIONS.md` se aplica sem exceção: POST bem-sucedido responde com
  `HX-Redirect` (nunca com fragmento de escrita); fragments HTMX são
  exclusivos de requisições GET, para leitura ou interação auxiliar (ex.: a
  própria linha nova do formset);
- markup de linha de item deve ser compartilhado via partial reutilizável em
  vez de reimplementado por tela (a extração desse partial fica a cargo da
  issue-filha correspondente do épico #68, quando existir);
- guardas de domínio (ex.: duplicidade de material, quantidade inválida,
  material inelegível) são validadas no `clean()` do form/formset, não em JS
  — JS pode replicar feedback client-side como otimização, nunca como única
  fonte de validação. Para "Saída excepcional" especificamente: cada
  `Material` pode aparecer no máximo uma vez no documento; entradas repetidas
  são rejeitadas no `clean()`, nunca combinadas ou somadas silenciosamente;
- `estoque/nova_saida_excepcional.html` é migrada para esse padrão via
  issue-filha vinculada ao épico #68, herdando os guardrails padrão do épico
  (paridade de comportamento, ARIA, suíte verde, escopo fechado) e exigindo
  testes distribuídos pelas camadas corretas (ADR-0010): duplicidade,
  quantidade inválida e elegibilidade de material cobertas em testes de
  `Form`/`FormSet`; fluxo completo (submissão, redirect, mensagens) coberto
  em testes de integração da view; autorização e mutação de domínio cobertas
  em testes de policy/service, com mutações em `services.py` sob
  `transaction.atomic` conforme `docs/CONVENTIONS.md`;
- o paradigma Alpine client-side puro (array Alpine sem `Form`/`FormSet` por
  trás) não deve ser usado para itens dinâmicos em novas telas.

## Consequências

### Positivas

1. **Testável sem browser** — o formset é exercitável via pytest puro
   (`client.post`), consistente com ADR-0010 (estratégia de testes).
2. **Validação no lugar canônico** — o Django FormSet volta a ser a única
   fonte de verdade para regras de item, eliminando a duplicação de lógica
   entre view e template que o paradigma Alpine introduziu.
3. **Coerência com a filosofia server-rendered** do projeto (ADR-0008):
   estado vive no servidor, HTMX cuida da interação incremental, Alpine fica
   reservado para UI puramente client-side (autocomplete, toggles, `x-show`).
4. **Menos drift** — uma única implementação de linha de item elimina a
   necessidade de sincronizar markup/comportamento entre duas telas a cada
   ajuste.

### Negativas

1. **Custo de migração** — `nova_saida_excepcional` perde seu modelo Alpine
   atual e precisa de um `FormSet` novo, endpoint de nova linha e adaptação
   da guarda de duplicidade para `clean()` de formset.
2. **Menos localidade de estado no cliente** — o formset server-side depende
   de round-trip HTMX para cada linha nova, enquanto o array Alpine adicionava
   linhas sem request.

### Trade-off

Aceitamos o custo de migrar uma tela já funcional em troca de um único
paradigma testável, auditável e sem duplicação de lógica de validação — a
alternativa (manter os dois, ou migrar o sentido contrário) perpetuaria a
ambiguidade que motivou esta decisão ou abriria mão da testabilidade sem
browser que o restante do projeto já garante.

## Referências

- Issue #82 (decisão HITL)
- Épico #68 (auditoria de componentes do design system)
- `docs/adr/0008-design-system-pragmatico-django-tailwind-htmx.md`
- `docs/adr/0010-estrategia-de-testes.md`
- `apps/requisicoes/templates/requisicoes/rascunho_form.html`
- `apps/requisicoes/templates/requisicoes/partials/_item_form_row.html`
- `apps/requisicoes/views.py:417` (`nova_linha_item`)
- `apps/estoque/templates/estoque/nova_saida_excepcional.html`
