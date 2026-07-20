# Plano — Issue #77: components/alert.html

## Contexto

Issue fechada em 13/07/2026 referenciando commit `77d78890`, mas esse commit não é
ancestral de `origin/main` nem `upstream/main` — a branch `refactor/alert-component`
ficou órfã (nunca mergeada, provavelmente perdida num reset/force-push). O componente
não existe no working tree atual; `rascunho_form.html`, `nova_saida_excepcional.html`,
`copiar_confirmacao.html` e `preview_importacao_scpi.html` ainda têm caixas de aviso
inline. Reaberta para reimplementar antes de retomar #85 (form_field.html), que
depende deste componente.

O conteúdo da branch órfã (`refactor/alert-component-orphan-backup-2026-07-20`) foi
inspecionado: `components/alert.html`, `test_components_alert.py` e os partials de
corpo rico já haviam passado por uma rodada de revisão CodeRabbit (commit
`b9efa40 fix(alert): address CodeRabbit findings`) e continuam válidos como estão —
nada no contrato do componente em si depende de código que mudou depois. Reaproveitados
verbatim. O que mudou desde então foi o **conteúdo dos templates a migrar**:
`nova_saida_excepcional.html` foi totalmente reescrito pela issue #93 (paradigma HTMX
FormSet, ADR-0016) — os alvos de migração deste plano foram remapeados para o estado
atual do arquivo, e dois novos casos elegíveis surgiram (formset `non_form_errors` e a
caixa de duplicidade, que deixou de ser Alpine `x-show`/`x-text` e virou JS vanilla
simples — portanto migrável, ao contrário do que a issue original presumia).

## Escopo

Criar `apps/core/templates/components/alert.html` conforme `docs/design-system.md`
(§4, linhas 415-431) e migrar as caixas de aviso inline abaixo.

### Parâmetros do componente

```text
variant        (default=info) info, success, warning, danger
message        (obrigatório, exceto se body_template ou casca JS-hidratada) texto
               autoescapado (Django escapa por padrão); conteúdo HTML rico só via
               body_template, nunca via message. String vazia é permitida
               explicitamente quando o componente serve só de casca estática inicial
               para um elemento que o JS do chamador preenche depois via
               `textContent` (caso da caixa de duplicidade — ver "Migra" abaixo);
               fora desse cenário, `message` vazio sem `body_template` é
               responsabilidade do chamador tratar (o componente não valida
               obrigatoriedade em runtime, só documenta a expectativa)
body_template  (opcional) partial incluído no corpo — herda contexto do chamador
               (mesmo mecanismo de form_body_template em modal.html). Precedência
               explícita quando ambos são passados: `body_template` sempre vence,
               `message` é ignorado nesse caso (sem erro, sem renderização
               duplicada) — mesma regra de exclusividade mútua de `icon_variant`
               vs. conteúdo textual em outros componentes do projeto. Não é
               esperado que um chamador passe os dois; quando `body_template` é
               usado, `message` normalmente fica ausente
icone          (opcional, bool, default=True)
role           (opcional) sobrescreve role padrão (default: info/success=status,
               warning/danger=alert)
aria_live      (opcional) valor de aria-live — sem default automático
id             (opcional) — extensão prática além do inventário do design-system,
               necessária para o caso da caixa de duplicidade (JS precisa de um alvo
               estável via getElementById)
class          (opcional) passthrough de layout
```

Nomenclatura `danger` (não `error`): consistente com `button.html` e com o próprio
`docs/design-system.md` §4. Distinto do nível de severidade `error` do contrato de
mensagens Django (`messages-contract`) — `alert.html` é um componente de apresentação
(banner estático), não o contêiner de flash messages; não há mapeamento a documentar
porque operam em camadas diferentes.

**Sobre o botão de dismiss manual de `docs/CONVENTIONS.md` (§Níveis e ARIA,
linhas 172-181):** essa exigência é do contrato de flash messages do Django
(`messages.error`/`messages.warning`/etc.), renderizado por
`apps/core/templates/core/partials/_messages.html` — que tem markup e JS de
dismiss próprios, **não usa `alert.html` hoje** e não é tocado por este plano
(já listado em "Fora de escopo" da issue original: "Reestilizar `_messages.html`
... não nesta issue"). `alert.html` é um componente distinto, para banners de
página/formulário estáticos — nunca o canal de flash messages — então a regra
de dismiss de `CONVENTIONS.md` não se aplica a ele por escopo, não por exceção.
Se `_messages.html` um dia adotar `alert.html` internamente (fora deste plano),
o dismiss seria implementado no template/JS **chamador** de `_messages.html`,
do mesmo jeito que a caixa de duplicidade já hidrata `alert.html` com JS
externo — o componente não precisaria de um parâmetro de dismiss próprio.
`alert.html` é estático, sem JS de dismissal embutido.

Visual: `rounded-lg border px-4 py-3 text-sm` + par cor-200/cor-50/cor-800 (spec).

### Migra

- `rascunho_form.html:134-143` — `tem_item_inelegivel`, warning, corpo rico (via
  `body_template`)
- `rascunho_form.html:150-156` — `formset.non_form_errors`, danger, corpo rico (loop)
- `nova_saida_excepcional.html:20-24` — `erro_geral`, danger, mensagem simples
- `nova_saida_excepcional.html:83-89` — `formset.non_form_errors`, danger, corpo rico
  (loop) — **novo caso, não existia na issue original** (era dict `erros` manual antes
  de #93)
- `nova_saida_excepcional.html:92-97` — caixa de duplicidade (`#aviso-duplicidade`),
  danger, `icone=False`, `id="aviso-duplicidade"`, `aria_live="assertive"`,
  `message=""`, `class="hidden"` (**invariante obrigatória**: a casca renderiza
  oculta por padrão via `class="hidden"` — sem isso, um `role="alert"` vazio poderia
  ser anunciado por leitor de tela antes da hidratação. JS do chamador continua
  fazendo `textContent`/`classList.remove('hidden')` para popular e mostrar,
  `classList.add('hidden')` para esconder de novo — ciclo
  oculto→preenchido→visível→oculto idêntico ao comportamento atual, componente só
  fornece a casca estática inicial) — **novo caso**: na issue original
  isso era Alpine `x-show`/`x-text` reativo (não migrável); pós-#93 é JS vanilla direto
  no DOM, compatível com uma casca server-rendered
- `copiar_confirmacao.html:23-26` — nota amber, `role="note"` preservado via override
- `preview_importacao_scpi.html:111-124` — `erro_arquivo`, danger, corpo rico (título +
  mensagem)

### Não migra (documentado com justificativa no template)

- `apps/core/templates/components/_modal_body.html:32-39` — caixa `data-modal-erro`.
  O `id` do contrato ARIA (`aria-describedby="{{ id }}-erro"`, referenciado por 4+
  partials `_modal_form_*.html`) fica no `<span>` **interno**, não no elemento raiz —
  meu `alert.html` só aceita `id` no elemento raiz. Migrar exigiria um segundo
  parâmetro (`inner_id`) e preservar o atributo custom `data-modal-erro` só para este
  caso, o que expande o componente além do que qualquer outro consumidor precisa.
  Já documentado como exceção na issue original (coordenar com #78 — mergeada
  separadamente sem essa migração). Fica inline.
- `preview_importacao_scpi.html:385-403` — caixas de resumo `novos`/`divergencias`.
  Fora do escopo textual da issue (que cita só "caixas de erro de arquivo"). A caixa
  `novos` usa cor teal — não é uma das 4 variantes do componente (forçar para
  info/success regridiria a semântica de cor já estabelecida via
  `badge.html` variant="teal" na mesma tela). Fica inline.

## Arquivos tocados

- `apps/core/templates/components/alert.html` (novo)
- `apps/core/tests/test_components_alert.py` (novo)
- `apps/requisicoes/templates/requisicoes/partials/_alert_itens_inelegiveis_corpo.html` (novo)
- `apps/requisicoes/templates/requisicoes/partials/_alert_erros_formset.html` (novo)
- `apps/requisicoes/templates/requisicoes/partials/_alert_nota_copia_corpo.html` (novo)
- `apps/estoque/templates/estoque/partials/_alert_erro_arquivo_corpo.html` (novo)
- `apps/estoque/templates/estoque/partials/_alert_erros_formset.html` (novo)
- `apps/requisicoes/templates/requisicoes/rascunho_form.html` (migração)
- `apps/estoque/templates/estoque/nova_saida_excepcional.html` (migração)
- `apps/requisicoes/templates/requisicoes/copiar_confirmacao.html` (migração)
- `apps/estoque/templates/estoque/preview_importacao_scpi.html` (migração)
- `static/app.css` / build do Tailwind (`npm run css:build`)

## Estratégia de teste

- Teste de template do componente isolado (`test_components_alert.py`): variantes
  (info/success/warning/danger), `role` correto por variante, override de `role`,
  `icone=False` oculta ícone, `body_template` inclui corpo herdando contexto sem exigir
  `message` (caso omitido), `body_template` tem precedência quando os dois são
  passados juntos, `id` renderiza atributo, `class` faz passthrough, `message` é
  autoescapado, `message=""` sem `body_template` renderiza casca válida sem erro
  (caso da casca JS-hidratada) — incluindo o cenário `class="hidden"` +
  `message=""` da caixa de duplicidade, com asserção de que a classe `hidden` está
  presente na renderização inicial (o restante do ciclo — popular e reexibir via
  `textContent`/`classList` — é client-side; o projeto não tem suíte de teste de
  JS/browser hoje, então esse trecho permanece verificado manualmente no browser,
  igual ao comportamento inline atual, sem regressão de cobertura introduzida por
  esta migração).
- Testes de view existentes (rascunho_form, nova_saida_excepcional, copiar_confirmacao,
  preview_importacao_scpi) continuam cobrindo a exibição das mensagens — texto e roles
  seguem presentes após a migração; nenhuma asserção de view deve precisar mudar de
  significado (só potencialmente de string de classe CSS, se algum teste existente
  faz assert nisso — verificar antes de migrar cada arquivo).

## Invariantes (docs/design-acesso-rapido/matriz-invariantes.md)

- Nenhuma mudança de camada de domínio — apenas template.
- Contrato ARIA de mensagens (memória `messages-contract`): error/warning→alert,
  success/info→status. `role="note"` do `copiar_confirmacao.html` é caso especial
  documentado (não é mensagem de sistema, é nota informativa fixa) — preservado via
  override explícito.

## Riscos

- Drift visual mínimo: `preview_importacao_scpi.html` usa `rounded-xl`/`py-4` na caixa
  de erro de arquivo; componente usa `rounded-lg`/`py-3` (padrão do spec). Normalização
  intencional — documentar no PR.
- `rascunho_form.html` warning usava `text-amber-900`; componente padroniza
  `text-amber-800` (par cor-800 do spec, igual a `copiar_confirmacao.html`).
  Normalização intencional.
- Extensão do parâmetro `id` além do inventário original do design-system: necessária
  e mínima (só a caixa de duplicidade usa), documentada no docstring do componente.
- Nenhuma dependência nova; sem mudança em services/policies/selectors.
