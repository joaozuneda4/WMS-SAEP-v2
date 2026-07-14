# Plano — Issue #78: modal com corpo em fonte única + migrar 2 modais hand-rolled

**Épico:** #68 — extração de componentes do design system (fase 2)
**Branch:** `refactor/modal-fonte-unica`

## Escopo

### Dentro do escopo

1. **Fonte única do corpo do modal.** `apps/core/templates/components/modal.html:72-123` (header + erro +
   corpo + footer) e `apps/requisicoes/templates/requisicoes/partials/_modal_body_fragment.html`
   duplicam a mesma marcação (~50 linhas). Promover o miolo compartilhado para
   `apps/core/templates/components/_modal_body.html` (recebe `id`, `titulo`, `descricao`, `erro`,
   `form_body_template`, `icon_variant`, `cancel_label`, `confirm_label`, `confirm_variant`).
   `modal.html` passa a `{% include %}` esse parcial dentro do `<form>`; `_modal_body_fragment.html`
   passa a ser um wrapper fino que inclui o mesmo parcial (mantém o contrato HTMX de troca via
   `hx-swap="outerHTML"` em `[data-modal-body="{{ id }}"]`).
   `apps/requisicoes/views.py:175-213` (`_render_modal_erro`) não muda de assinatura — o contexto
   já casa com os params do parcial promovido.

2. **Migrar `atender_retirada.html:196-280`** (dialog inline já usa padrão próprio de x-data local
   com `confirmar()` chamando `document.getElementById('form-atender-retirada').requestSubmit()`)
   para `components/modal.html`. Esse fluxo não tem form próprio — precisa de um modo "confirmação
   de form externo": novo param `submit_form_id` em `modal.html`. Quando presente, o componente:
   - não renderiza `<form method="post" action="...">` envolvente (sem `action_url` nesse modo);
   - o botão de confirmar vira `type="button"` com
     `@click="fechar(); document.getElementById('{{ submit_form_id }}')?.requestSubmit()"`
     (optional chaining — contrato único em todo o plano, ver validação abaixo) em vez de
     `type="submit"` dentro do form do próprio modal;
   - mantém `data-modal-confirm` no botão como metadado do modal (identifica o botão de
     confirmação para estilo/acessibilidade) — **não** é o que aciona a proteção de
     double-submit nesse modo; a proteção real acontece no evento `submit` do form alvo
     (ver seção abaixo), disparado depois do `requestSubmit()`, não pela detecção de clique
     no botão.
   `action_url` e `submit_form_id` são mutuamente exclusivos e **o componente valida isso
   explicitamente** (não é só docstring): renderiza vazio/erro de configuração se ambos ou
   nenhum forem passados. **Correção de review:** a existência do elemento DOM referenciado
   por `submit_form_id` não pode ser validada durante o render Django (server-side) — o
   `<form>` alvo é HTML que existe no browser, não algo que o Django enxerga no momento do
   render do componente. Essa validação fica para: (a) testes que verificam o HTML
   renderizado do template chamador (confirmam que o `id` referenciado em `submit_form_id`
   de fato aparece em algum `<form>` da página, via assertion de string/BeautifulSoup no
   teste de view), e (b) a mesma guarda client-side `?.requestSubmit()` do `@click` acima.
   **Correção de review (contrato único):** o `?.` não deve mascarar erro de configuração em
   silêncio — se `getElementById` retornar `null`, o clique não deve falhar silenciosamente:
   o `modalController` loga `console.error` identificando o `id` de `submit_form_id` que não
   foi encontrado (sinal auditável em dev/CI de template quebrado, sem expor nada ao usuário
   final, já que esse erro só pode vir de engano de configuração do template chamador, nunca
   de input de usuário). Testes cobrem: `action_url` sozinho (caminho já existente, não
   regride), `submit_form_id` sozinho, os dois juntos (deve falhar na validação de
   exclusividade) e nenhum dos dois (deve falhar na validação de exclusividade).
   `form_body_template` fica vazio (só header/footer, sem `erro`, sem HTMX).
   Trigger e modal continuam no mesmo `x-data="modalController({ id: 'confirmar-atender-retirada' })"`
   já existente no wrapper (`atender_retirada.html:196-219` vira o `x-data` do `modalController`,
   substituindo o objeto Alpine manual).

   **Anti-double-submit no modo `submit_form_id` (achado de review):** o botão de confirmar fica
   fora de `form[data-prevent-double-submit]` (o form alvo é externo e o botão nem está dentro de
   nenhum form nesse modo). `apps/core/static/core/js/form-submit.js:38-50` só registra o
   `submitter` via clique quando `btn.closest('form[data-prevent-double-submit]')` resolve — o que
   não acontece aqui. Efeito real, verificado lendo o script (`form-submit.js:52-92`): o bloqueio
   central de double-submit (`form.dataset.submitting === '1'`, setado no evento `submit` do form
   alvo) **continua funcionando**, porque é disparado pelo `requestSubmit()` independentemente de
   quem clicou; o que se perde é só a aplicação de `aria-busy`/spinner num botão — que já não está
   mais visível, pois o modal fecha (`fechar()`) antes do `requestSubmit()`. Decisão: não alterar
   `form-submit.js` (o form alvo, `#form-atender-retirada`, já tem `data-prevent-double-submit` e
   nenhum botão de submit próprio visível — `alvosDoForm` retorna vazio hoje também, sem
   regressão). Documentar essa análise no PR e adicionar teste de view garantindo que dois POSTs
   consecutivos ao endpoint de atendimento não causam dupla baixa de estoque (idempotência via
   validação de estado, não via JS) — cobre o risco real (dado inconsistente), não o comportamento
   cosmético do botão.

3. **Migrar `detalhe_saida_excepcional.html:193-268`** (overlay `div` + `x-show`, sem `<dialog>`)
   para `components/modal.html` com `form_body_template="estoque/partials/_modal_form_estorno_saida.html"`
   (novo parcial só com o `<textarea name="justificativa" required>`). Diferença estrutural: hoje o
   trigger (linha 25-33, dentro do cabeçalho) e o modal (linha 193+, bloco separado) não compartilham
   elemento pai e se comunicam via evento de window (`$dispatch('open-modal-estorno')` /
   `@open-modal-estorno.window`). `modalController` exige que trigger e `<dialog x-ref>` estejam sob
   o mesmo escopo `x-data` (mesmo já acontece em `requisicoes/detalhe.html:344` para um caso análogo
   de trigger distante do modal). Decisão: envolver o `<div class="max-w-screen-xl ...">` de
   `{% block content %}` (linha 10) inteiro em `x-data="modalController({ id: 'estornar-saida' })"`,
   remover o `x-data`/`@click="$dispatch(...)"` isolado do botão trigger e trocar por
   `data-modal-trigger="estornar-saida" @click="abrir($event)"`. O comportamento bottom-sheet mobile
   atual (overlay full-screen customizado) **não é preservado** — vira o dialog centrado padrão do
   componente; registrar essa mudança visual no corpo do PR.

   **Invariantes de domínio do estorno (achado de review):** a migração é só de apresentação —
   o `<form method="post" action="{% url 'estoque:estornar_saida_excepcional' saida.pk %}">`
   continua apontando pra mesma view/URL, sem tocar `apps/estoque/services.py`,
   `apps/estoque/policies.py` ou `apps/estoque/views.py`. Antes de considerar a migração 2
   concluída, confirmar (via suíte existente, sem teste novo de domínio — só de não-regressão):
   `saida.estado` permanece `'registrada'` até um POST de estorno bem-sucedido (não pode ser
   estornada implicitamente pela troca de markup); a `Movimentação` de estoque gerada pelo
   estorno continua append-only e referenciando a `SaidaExcepcional` de origem correta (mesmo
   contrato de `apps/estoque/tests/test_services.py`/`test_views.py` já cobre isso — rodar essa
   suíte é a evidência, não escrever nova asserção de domínio). Se a suíte desses testes
   (`test_chefe_estorna_e_redireciona_para_detalhe`, `test_saida_ja_estornada_redireciona_com_mensagem_warning`)
   passar inalterada após a migração de template, a invariante está preservada — nenhuma mudança
   nesses arquivos de teste é esperada, só nos testes de markup do modal.

### Fora do escopo

- Copy dos modais (títulos, descrições, labels de botão) — só reestrutura markup.
- Os outros 8 usos existentes de `components/modal.html` (já corretos, não tocar).
- `apps/core/static/core/js/modal.js` além do necessário para o modo `submit_form_id` — nenhuma
  mudança de JS é esperada, pois o modo é resolvido inteiramente no template (o botão de confirmar
  já dispara `requestSubmit()` via Alpine inline, sem precisar de método novo no controller).
- Dependências novas — zero.
- Mudança de comportamento de domínio (services/policies/selectors intocados).

## Arquivos tocados

| Arquivo | Mudança |
|---|---|
| `apps/core/templates/components/_modal_body.html` | **novo** — parcial promovido (header/erro/corpo/footer) |
| `apps/core/templates/components/modal.html` | inclui `_modal_body.html`; suporta `submit_form_id` |
| `apps/requisicoes/templates/requisicoes/partials/_modal_body_fragment.html` | vira wrapper fino sobre `_modal_body.html` |
| `apps/requisicoes/views.py` | `_render_modal_erro` — sem mudança de assinatura, só confirmar que contrato do fragment se mantém |
| `apps/requisicoes/templates/requisicoes/atender_retirada.html` | dialog inline → `{% include "components/modal.html" %}` com `submit_form_id` |
| `apps/estoque/templates/estoque/detalhe_saida_excepcional.html` | overlay Alpine hand-rolled → `{% include "components/modal.html" %}` |
| `apps/estoque/templates/estoque/partials/_modal_form_estorno_saida.html` | **novo** — form body só com textarea de justificativa |
| `apps/requisicoes/tests/test_views.py` | ajustar asserções de markup dos testes que tocam o dialog de `atender_retirada` |
| `apps/estoque/tests/test_views.py` | ajustar asserções de markup dos testes que tocam o modal de estorno |
| `input.css` / `app.css` | rebuild via `npm run css:build` se novas classes aparecerem (não esperado — classes já existem em `modal.html`) |

## Estratégia de testes

- **Happy path fonte única:** teste de view (`requisicoes`) que dispara 422 via HTMX
  (`_render_modal_erro`) continua validando que a resposta contém `data-modal-body`,
  `aria-live="polite"` e o erro — contrato já coberto por
  `test_recusar_requisicao_sem_motivo_via_htmx_retorna_422_fragment` e
  `test_cancelar_requisicao_sem_justificativa_via_htmx_retorna_422_fragment`
  (`apps/requisicoes/tests/test_views.py:1231,1550`); confirmar que continuam verdes após a
  promoção do parcial. **Nota (correção de review):** `test_atender_post_form_invalido_renderiza_400`
  é um contrato diferente — validação do formset de quantidades entregues, sem HTMX, sem modal,
  resposta 400 — não é evidência do fluxo de modal/422 e não deve ser citado como tal.
- **Caso extremo — duplicação:** verificação manual antes de finalizar, restrita a arquivos de
  template/markup (`apps/**/templates/**/*.html`) — não a todo o repositório. Objetivo: nenhum
  `data-modal-body="..."` **renderizado** (atributo real de markup, não string em docs, testes ou
  comentários) fora de `apps/core/templates/components/`. Um grep literal por `data-modal-body`
  vai naturalmente encontrar ocorrências legítimas em `apps/core/templates/components/modal.html`
  e `_modal_body.html` (fonte) e em `apps/requisicoes/tests/test_views.py` (asserções de HTML
  renderizado) — essas não contam como duplicação; o critério é sobre onde o *atributo é definido
  em markup*, não onde a string aparece.
- **`atender_retirada`:** teste de view que renderiza a tela e verifica presença de
  `data-modal-trigger="confirmar-atender-retirada"`, `data-modal-confirm` e ausência de
  `hx-post` no dialog (modo form externo não usa HTMX). Teste funcional de submit já coberto por
  `test_atender_post_total_redireciona_e_muda_estado` etc. — não muda, pois o form
  `#form-atender-retirada` continua sendo o alvo do POST.
- **`detalhe_saida_excepcional`:** teste de view que verifica `required` no textarea de justificativa
  permanece (`test_estornar_view_sem_justificativa_exibe_warning` cobre o caso de erro server-side;
  adicionar/ajustar teste de markup que confirma `<textarea ... required>` está presente dentro do
  modal migrado, e que `data-modal-trigger="estornar-saida"` existe no botão).
- **Cenário de erro/contrato:** o fluxo 422 de recusar/cancelar requisição (que já usa
  `_modal_body_fragment.html`) precisa continuar devolvendo o modal aberto com erro — teste de
  regressão explícito rodando `test_recusar_requisicao_sem_motivo_via_htmx_retorna_422_fragment`,
  `test_cancelar_requisicao_sem_justificativa_via_htmx_retorna_422_fragment` e equivalentes de
  retornar/devolver (mesmo padrão 422+fragment).

## Invariantes relevantes (matriz de invariantes / a11y)

- `<dialog>` nativo com `aria-modal="true"`, `aria-labelledby`/`aria-describedby`, `x-trap.inert.noscroll`,
  retorno de foco ao trigger ao fechar — comparar atributo a atributo contra `modal.html` atual nos
  dois modais migrados.
- Contrato 422: `_render_modal_erro` continua devolvendo fragment que substitui `[data-modal-body]`
  via `hx-swap="outerHTML"` — não pode regressão nesse ponto (é o mecanismo central do componente).
- Tab preso no dialog (`x-trap`) e Esc fecha com foco de volta — cobrir manualmente nos dois fluxos
  migrados (critério de aceite explícito da issue).
- Anti-double-submit (`data-prevent-double-submit`, `data-modal-confirm`) — no modo `submit_form_id`,
  o form que recebe `requestSubmit()` é o externo (`#form-atender-retirada`), que já carrega sua
  própria proteção; o modal em si não precisa de `data-prevent-double-submit` pois não faz POST
  próprio nesse modo.

## Riscos

- **Integridade de dados/idempotência (achado de review):** o modo `submit_form_id` remove o
  form próprio do modal, então a proteção padrão de double-submit (`data-prevent-double-submit`
  aplicado ao form do modal) não se aplica diretamente — dois cliques rápidos podem, em teoria,
  disparar dois `requestSubmit()` no form alvo antes do primeiro POST completar. Mitigação: o
  bloqueio central de `form-submit.js` (`form.dataset.submitting`) já está no form alvo
  (`#form-atender-retirada` tem `data-prevent-double-submit`) e continua funcionando
  independente de quem chamou `requestSubmit()`; teste de view garante que dois POSTs
  consecutivos ao endpoint de atendimento não causam dupla baixa de estoque (idempotência via
  validação de estado do domínio, não apenas via JS). Sem mudança em services/policies/selectors.
- **Contrato HTMX/422:** maior risco — se `_modal_body_fragment.html` virar wrapper incorretamente,
  quebra o único mecanismo de exibição de erro inline em modal do projeto. Mitigar testando os 4
  fluxos que usam esse fragment (recusar, cancelar, retornar, devolver) antes de considerar a fase 1
  concluída.
- **Modo `submit_form_id` novo no componente:** é a única extensão de contrato do componente
  compartilhado — risco de regressão nos outros 8 usos existentes se a lógica condicional
  (`action_url` vs `submit_form_id`) for malfeita. Mitigar: `action_url` continua obrigatório no modo
  padrão (nenhum uso existente passa `submit_form_id`), então o `if` deve ser aditivo e não alterar o
  caminho padrão.
- **Regressão visual:** `detalhe_saida_excepcional` perde o comportamento bottom-sheet mobile — é uma
  mudança de UX aceita explicitamente pela issue (não precisa ser preservada), mas deve ser destacada
  no corpo do PR para não ser lida como bug.

## Comandos de verificação (ao final da Fase 2)

- `uv run ruff format .`
- `uv run ruff check .`
- `uv run mypy apps`
- `uv run pytest -q -ra --tb=short --strict-markers --disable-warnings -n logical`
- `npm run css:build` (confirmar `app.css` no diff só se houver classe nova — não esperado)
- Verificação manual no browser dos dois fluxos migrados (critérios de aceite da issue).
