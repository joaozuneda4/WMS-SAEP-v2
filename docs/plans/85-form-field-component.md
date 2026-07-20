# Plano — Issue #85: components/form_field.html + widgets padronizados

## Contexto

Bloqueada por #77 (`components/alert.html`), agora mergeada
(joaozuneda4/WMS-SAEP-v2#12). Este plano foi escrito depois de reler o estado
atual do código (pós-#93, que já reescreveu `nova_saida_excepcional` pro
paradigma HTMX FormSet) — parte do escopo original da issue já está satisfeita
e é documentada como tal abaixo, em vez de reimplementada.

## Descobertas que redefinem o escopo

1. **`SaidaExcepcionalForm`/`ItemSaidaExcepcionalFormSet` já existem**
   (`apps/estoque/forms.py`, criados pela issue #93/ADR-0016) com
   `clean_observacao` validando obrigatoriedade com o texto de erro exato que
   a issue pede ("A observação é obrigatória."). O item 4 do objetivo original
   ("criar SaidaExcepcionalForm... ou extrair motivo/observacao") está feito.
   O que falta é só migrar os campos `motivo`/`observacao` (BoundFields reais)
   pro componente novo — já no escopo do item 2 da issue.
2. **Widgets já padronizados em `forms.py` nos 2 apps** para os campos que
   este plano migra: `RegistrarAtendimentoCabecalhoForm.retirante_nome`/
   `observacao` (`apps/requisicoes/forms.py:222-249`) e
   `SaidaExcepcionalForm.motivo`/`observacao` (`apps/estoque/forms.py:19-43`)
   já definem `class`/`autocomplete`/`placeholder` nos widgets — o componente
   não precisa injetar classe via template para esses. Único gap encontrado:
   `RequisicaoForm.observacao_geral` (`apps/requisicoes/forms.py:11-22`) tem o
   placeholder hardcoded no `<textarea>` manual de `rascunho_form.html` em vez
   de no widget — corrigido neste plano (ver "Mudanças em forms.py").
3. **Nenhum dos 6 partials `_modal_form_*.html` usa BoundField real hoje.**
   Inspecionados todos: `_modal_form_devolucao.html`, `_modal_form_recusar.html`,
   `_modal_form_estorno.html`, `_modal_form_cancelar.html`,
   `_modal_form_retornar.html` (requisicoes) e `_modal_form_estorno_saida.html`
   (estoque) constroem `<input>`/`<textarea>` manualmente com `name`/`id`
   fixos ou compostos por item (`modal-devolver-quantidade-{{ item.pk }}`),
   erro vindo de uma variável de contexto solta (`erro`, `motivo_recusa`,
   `justificativa_cancelamento`) em vez de `field.errors`. Só
   `_modal_form_devolucao.html`/`_modal_form_estorno.html` tocam um objeto
   `form`/`estorno_form` e mesmo assim só para ler `.value`, não para
   renderizar via BoundField. `form_field.html` exige um BoundField real
   (`field.id_for_label`, `.errors`, `.html_name`) — nenhum desses 6 partials
   fornece isso hoje sem introduzir um Django `Form` novo por modal, o que é
   mudança de camada de view/domínio, fora do escopo desta issue (template +
   `forms.py` dos 2 apps). **Nenhum modal é migrado** — documentado como bloco
   único de exceção, não caso a caso.
4. **`atender_retirada.html` tem campos de formset por linha
   (`quantidade_entregue`, `justificativa`) que a issue não listou** — usam
   binding reativo Alpine (`x-bind:required`, `x-bind:aria-required` condicional
   a `parcial`) e hint com `x-show`/`aria-live` dinâmico. Não migrados: fora da
   lista explícita da issue (`retirante_nome`, `observacao` do cabeçalho) e o
   contrato reativo Alpine não cabe num componente `{% include %}` estático.

## Escopo

Criar `apps/core/templates/components/form_field.html` conforme
`docs/design-system.md` (§2, linhas 380-396) e migrar os campos abaixo.

### Parâmetros do componente

```text
field           (obrigatório) BoundField do Django
label_override  (opcional) texto customizado da label — senão usa field.label
help_text       (opcional) sobrescreve field.help_text
label_class     (opcional, default abaixo) classes da label — variação real
                entre telas (uppercase/tracking-wide vs sr-only vs sem
                uppercase)
required_marker (opcional, bool) True força mostrar o asterisco mesmo se o
                campo não for obrigatório, False força esconder mesmo se for;
                ausente (default) deriva automaticamente de
                field.field.required — o mesmo idioma de icone!=False já
                usado em alert.html
class           (opcional) passthrough pro `<div>` wrapper
```

Default de `label_class`: `"block text-xs font-medium uppercase tracking-wide
text-slate-500"` (estilo de `atender_retirada.html`, o mais próximo do padrão
já dominante em `<th>`/`<dt>` no restante do projeto). `rascunho_form.html`
sobrescreve com `"sr-only"` (label visualmente oculta, placeholder faz o
trabalho visual); `nova_saida_excepcional.html` sobrescreve com
`"mb-1 block text-xs font-medium text-slate-600"` (sem uppercase — mantém o
estilo atual da tela).

### Sobre `aria-required` (divergência da issue original)

A issue pede "asterisco `aria-hidden` + `aria-required`", descrevendo como
"padrão atual". Verificado contra o código: nenhum dos 5 campos migrados tem
`aria-required` hoje (só os campos Alpine-reativos de `atender_retirada.html`
fora de escopo usam `x-bind:aria-required`, um mecanismo diferente). Decisão:
**não duplicar** — Django já adiciona o atributo HTML nativo `required` a todo
`BoundField` obrigatório por padrão (`Form.use_required_attribute=True`,
não sobrescrito em nenhum dos Forms tocados), e a diretriz WAI-ARIA recomenda
usar semântica nativa em vez de duplicar com ARIA quando o HTML nativo já
cobre. `aria-invalid`/`aria-describedby` (que o HTML nativo não cobre) são os
únicos atributos que o componente injeta.

### Injeção de `aria-invalid`/`aria-describedby`

Django não permite passar `attrs` extras pra `{{ field }}` via linguagem de
template pura (chamada de método sem argumentos sempre renderiza sem attrs
adicionais). O padrão já usado no projeto (`item_form_row.html`) é
reconstruir o `<input>` inteiro à mão — mas isso não escala pra um componente
genérico que precisa suportar qualquer tipo de widget (`Select`, `Textarea`,
`TextInput`). Em vez disso, adiciona-se um `simple_tag` mínimo em
`apps/core/templatetags/core_tags.py`, no mesmo padrão de `icon`:

```python
@register.simple_tag
def renderizar_campo_com_aria(field, tem_ajuda=False, tem_erro=False):
    """Renderiza o BoundField injetando aria-invalid/aria-describedby.

    Único mecanismo do projeto pra passar attrs extras a {{ field }} — Django
    não permite isso via linguagem de template pura. Escopado só aos 2
    atributos ARIA do contrato de components/form_field.html; preserva todos
    os attrs nativos do widget (required, class, placeholder etc. — attrs
    passados a as_widget() são mesclados, não substituem os automáticos).
    """
```

`field.as_widget(attrs=attrs)` mescla (não substitui) os attrs automáticos do
widget — `required`, `class`, `placeholder` definidos em `forms.py`
continuam intactos.

### Migra

- `atender_retirada.html:193-207` — `cabecalho.retirante_nome` (obrigatório,
  asterisco automático), `cabecalho.observacao` (opcional, sem asterisco)
- `rascunho_form.html` (bloco "Observação geral") — `form.observacao_geral`,
  `label_class="sr-only"`
- `nova_saida_excepcional.html` (seção "Dados da saída") — `form.motivo`,
  `form.observacao`, ambos `label_class="mb-1 block text-xs font-medium
  text-slate-600"`, ambos obrigatórios (asterisco automático)

### Não migra (documentado com justificativa no template)

- Todos os 6 partials `_modal_form_*.html` (`_modal_form_devolucao.html`,
  `_modal_form_recusar.html`, `_modal_form_estorno.html`,
  `_modal_form_cancelar.html`, `_modal_form_retornar.html`,
  `_modal_form_estorno_saida.html`) — nenhum usa BoundField real hoje (ver
  "Descobertas" item 3). Migrar exigiria introduzir Forms novos por modal,
  mudança de view/domínio fora do escopo template-only desta issue.
- `atender_retirada.html` campos de linha do formset (`quantidade_entregue`,
  `justificativa`) — Alpine reativo (`x-bind:required`), fora da lista
  explícita da issue (ver "Descobertas" item 4).

## Mudanças em `forms.py`

- `apps/requisicoes/forms.py` — `RequisicaoForm.observacao_geral`: adicionar
  `'placeholder': 'Opcional — contexto adicional sobre esta requisição'` ao
  widget (hoje só existe hardcoded no `<textarea>` manual que este plano
  remove). Único uso editável do campo é `rascunho_form.html` — confirmado
  via grep (`detalhe.html` só lê `requisicao.observacao_geral` do model, modo
  leitura, não afetado).
- `apps/estoque/forms.py` — nenhuma mudança (`SaidaExcepcionalForm` já tem
  classe/placeholder nos widgets).
- Nenhum Form novo criado — `SaidaExcepcionalForm` já existe (#93).

## Arquivos tocados

- `apps/core/templates/components/form_field.html` (novo)
- `apps/core/templatetags/core_tags.py` (adiciona `renderizar_campo_com_aria`)
- `apps/core/tests/test_components_form_field.py` (novo)
- `apps/core/tests/test_core_tags.py` ou arquivo equivalente (novo teste pro
  simple_tag, se não houver arquivo de teste de templatetags já — verificar
  antes de criar)
- `apps/requisicoes/forms.py` (placeholder de `observacao_geral`)
- `apps/requisicoes/templates/requisicoes/atender_retirada.html` (migração)
- `apps/requisicoes/templates/requisicoes/rascunho_form.html` (migração)
- `apps/estoque/templates/estoque/nova_saida_excepcional.html` (migração)
- `static/app.css` / build do Tailwind (`npm run css:build`) — `label_class`
  novos (`sr-only` já deve existir no bundle; `mb-1 block text-xs
  font-medium text-slate-600` são classes já usadas em outro lugar da mesma
  tela, mas confirmar rebuild)

## Estratégia de teste

- Teste de template do componente isolado
  (`test_components_form_field.py`): label vinculada (`for`/`id_for_label`),
  `label_override` sobrescreve `field.label`, `help_text` sobrescreve
  `field.help_text` e some quando ambos ausentes, asterisco aparece quando
  `field.field.required` e some quando `required_marker=False`, aparece
  mesmo em campo opcional quando `required_marker=True`, `aria-invalid`
  ausente sem erro e presente com erro, `aria-describedby` compõe
  `{id}-ajuda`/`{id}-erro` nas 4 combinações (nenhum, só ajuda, só erro,
  ambos), erros renderizam com `role="alert"`, `class` faz passthrough pro
  wrapper, atributo nativo `required` do widget não é removido pela injeção
  de attrs extras.
- Teste do `simple_tag` `renderizar_campo_com_aria` isolado (ou coberto
  indiretamente pelos testes do componente, se não houver padrão de teste de
  templatetag isolado no projeto — verificar `core_tags.py` atual antes de
  decidir).
- Testes de view existentes (`atender_retirada`, `rascunho_form`,
  `nova_saida_excepcional`) continuam cobrindo a exibição de erro por campo
  — texto de erro e presença de `role="alert"` seguem os mesmos após a
  migração; provocar cada erro no browser antes de considerar a issue pronta
  (critério de aceite explícito da issue).

## Invariantes (docs/design-acesso-rapido/matriz-invariantes.md)

- Nenhuma mudança de regra de domínio — `SaidaExcepcionalForm.clean_observacao`
  e a validação de `retirante_nome`/`observacao_geral` continuam idênticas;
  só a camada de renderização muda.
- Contrato ARIA de erros de campo (memória `messages-contract` — por
  extensão, mesmo padrão error→`role="alert"`) preservado.
- `services`/`policies`/`selectors` intocados.

## Riscos

- `label_class` sem valor "certo" único — 3 usos, 3 estilos diferentes; o
  default escolhido (uppercase/tracking-wide) é só o mais comum hoje, não uma
  imposição de padrão novo. Nenhuma tela muda visualmente porque as 3
  chamadas passam `label_class` explícito quando divergem do default.
- `renderizar_campo_com_aria` é a primeira vez que um componente de
  apresentação deste projeto precisa de lógica Python além de `simple_tag`s
  já existentes (`icon`, `validar_contrato_modal`) — mesmo padrão, sem
  dependência nova, mas é superfície de teste adicional (coberta acima).
- `atender_retirada.html` mostrava só o primeiro erro (`field.errors.0`);
  `form_field.html` mostra todos juntos (`field.errors|join:", "`, igual ao
  padrão já usado em `rascunho_form.html`/`nova_saida_excepcional.html`).
  Diferença só visível se um campo acumular 2+ erros simultâneos — raro pra
  `CharField` com `required`+`max_length` (Django geralmente para no primeiro).
  Normalização intencional pro padrão mais comum do projeto.
- Nenhuma dependência nova; sem mudança em services/policies/selectors.

## Verificação manual (executada nesta implementação)

- `nova_saida_excepcional`: submit vazio → `motivo`/`observação` com
  asterisco, erro "Este campo é obrigatório." (mensagem padrão do Django pro
  `CharField` vazio — `clean_observacao` customizado só dispara pra
  whitespace-only, comportamento pré-existente de #93, não alterado aqui),
  `aria-invalid="true"`, `aria-describedby="id_observacao-erro"`,
  `role="alert"` no erro — confirmado via DOM (`getAttribute`), não só
  visualmente.
- `rascunho_form`: `observacao_geral` com `label_class="sr-only"` e
  placeholder preservado (`Opcional — contexto adicional sobre esta
  requisição`) — confirmado via DOM.
- `atender_retirada`: não verificado no browser (exige fixture de requisição
  em estado "pronta para retirada"); confirmado via suíte automatizada — 15
  testes de view (`test_views.py -k atender`) verdes, cobrindo os mesmos
  caminhos de erro.
