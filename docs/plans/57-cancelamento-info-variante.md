# Plano — Issue #57: `CancelamentoInfo`/`CancelamentoVariant` de domínio; copy do modal migra p/ template

Ref: ADR-0011 (Emenda 2026-06-26, seção "Transições keyed por operação", trecho sobre
metadados de execução de capability), CONTEXT.md ("Variante de cancelamento").
Blocked by #53 (fechada) e #56 (fechada, mergeada em `1fe41be`).

## Scope

**O que muda:**

- `apps/requisicoes/models.py` — novo `CancelamentoVariant(models.TextChoices)` com dois
  membros, `DESCARTE` e `CANCELAMENTO`, espelhando exatamente o vocabulário de CONTEXT.md
  ("Variante de cancelamento": descarte é uma variante do cancelamento, não uma operação à
  parte). Vocabulário puro, não é field de nenhum model (mesmo padrão de `Operacao`).
- `apps/requisicoes/transitions.py` — novo `CancelamentoInfo` (dataclass frozen: `variante:
  CancelamentoVariant`, `requer_justificativa: bool`, `libera_reserva: bool`) e nova função
  `cancelamento_info(requisicao: Requisicao) -> CancelamentoInfo`. A função deriva a
  classificação a partir de `TRANSICOES[Operacao.CANCELAR].estados_origem` (guarda contra
  estado fora do conjunto, espelhando `verificar_transicao_valida`) mais a regra de domínio
  já existente hoje em `_cancelar_requisicao_impl`/`_detalhe_context` (`numero_publico is
  None` em `RASCUNHO` → `DESCARTE`; `AUTORIZADA`/`PRONTA_PARA_RETIRADA` → flags `True`; caso
  contrário `False`). Zero strings de apresentação — só enum + bool, conforme ADR.
  `cancelamento_info` assume que o chamador já checou `Operacao.CANCELAR in
  acoes_disponiveis(...)` (mesmo contrato de uso de `verificar_transicao_valida`); levanta
  `EstadoInvalido` se chamada fora desse conjunto.
- `apps/requisicoes/views.py` (`_detalhe_context`) — os 4 ramos `if/elif/else` que hoje
  montam `cancelamento_titulo`/`cancelamento_descricao`/`cancelamento_trigger`/
  `cancelamento_confirmar`/`cancelamento_variacao` (~50 linhas) são substituídos por uma
  chamada a `cancelamento_info(requisicao)` quando `cancelavel` é `True`. O contexto passa a
  expor `cancelamento_info` (objeto `CancelamentoInfo | None`) no lugar dessas 5 chaves de
  string. `cancelamento_requer_justificativa` continua existindo no contexto (agora como
  projeção de `cancelamento_info.requer_justificativa`) porque `_modal_form_cancelar.html`
  já a consome como bool — nenhuma mudança nesse partial.
- `apps/requisicoes/templatetags/requisicoes_tags.py` — novo `simple_tag` `cancelamento_copy`
  que recebe `CancelamentoInfo` + `requisicao.estado` e devolve um dict de copy (`titulo`,
  `descricao`, `trigger`, `confirmar`) via lookup. É aqui — na camada de apresentação, não no
  view/domínio — que o texto (idêntico ao atual, byte a byte, ver "Preservação de copy"
  abaixo) passa a viver.
- `apps/requisicoes/templates/requisicoes/detalhe.html` — os dois blocos que hoje interpolam
  `cancelamento_titulo`/`cancelamento_descricao`/`cancelamento_trigger`/`cancelamento_confirmar`
  passam a chamar `{% cancelamento_copy cancelamento_info requisicao.estado as
  cancelamento_copy_texto %}` e ler os mesmos 4 campos de `cancelamento_copy_texto`.

**Preservação de copy (correção pós-review do CodeRabbit na PR do plano):**
A primeira versão deste plano propunha colapsar `RASCUNHO`-numerado e
`AGUARDANDO_AUTORIZACAO` na mesma copy porque os dois têm os mesmos atributos de domínio
(`requer_justificativa=False`, `libera_reserva=False`). O CodeRabbit sinalizou que isso é uma
mudança de UX não pedida pela issue (#57 é refactor, não redesign) — `CancelamentoInfo`
carrega só os atributos que **efeitos** de domínio precisam; a granularidade de
**apresentação** pode ser mais fina que a granularidade de domínio, e a issue não pede
reduzi-la. Correção: os 4 textos atuais são preservados byte a byte. O `simple_tag` recebe
`requisicao.estado` como segunda dimensão de lookup (além de `variante`) exatamente para
preservar essa granularidade sem reintroduzir a árvore `if/elif/else` na view — o dado
adicional só amplia a chave de um dicionário estático na camada de template, não recria
lógica de domínio ali. Chave efetiva: `variante` sempre decide `DESCARTE` vs. `CANCELAMENTO`;
dentro de `CANCELAMENTO`, o dicionário distingue `RASCUNHO` / `AGUARDANDO_AUTORIZACAO` /
`{AUTORIZADA, PRONTA_PARA_RETIRADA}` (as duas últimas already compartilham texto hoje).
Resultado: 4 entradas de copy, igual ao comportamento atual — nenhuma mudança de UX.

**O que NÃO muda (fora de escopo):**

- `_render_modal_erro` em `cancelar_requisicao_view` (fragmento de erro HTMX para
  `justificativa_cancelamento_obrigatoria`) mantém seu texto inline hoje duplicado
  ("Cancelar requisição" / "A requisição será encerrada..."). A issue cita explicitamente
  `_detalhe_context`; esse outro call site não foi mencionado e alterá-lo expandiria escopo.
- `_modal_form_cancelar.html` não muda — já é boolean-driven (`cancelamento_requer_justificativa`),
  já satisfaz "zero strings" para a decisão textarea-vs-parágrafo.
- Nenhuma mudança em `services/cancelamento.py` (regras de negócio de cancelar/descartar já
  corretas, só a *apresentação* estava espalhada).
- Nenhuma mudança de schema/migration.
- `pode_cancelar` continua calculado do mesmo jeito (`Operacao.CANCELAR in acoes`).

## Files touched

- `apps/requisicoes/models.py` — `CancelamentoVariant`.
- `apps/requisicoes/transitions.py` — `CancelamentoInfo` + `cancelamento_info()`.
- `apps/requisicoes/views.py` — `_detalhe_context` simplificado.
- `apps/requisicoes/templatetags/requisicoes_tags.py` — `cancelamento_copy` simple_tag +
  tabela de copy privada.
- `apps/requisicoes/templates/requisicoes/detalhe.html` — troca de fonte de copy (2 blocos).
- `apps/requisicoes/tests/test_transitions.py` — testes de `cancelamento_info` (sem HTTP).
- `apps/requisicoes/tests/test_templatetags.py` — testes de `cancelamento_copy` (lookup de
  copy, sem HTTP/render).
- `apps/requisicoes/tests/test_views.py` — 2 asserts que liam `cancelamento_titulo` passam a
  ler `cancelamento_info.variante`; demais testes de cancelamento continuam válidos porque
  `cancelamento_requer_justificativa` e o HTML renderizado (`'Descartar rascunho' in html`)
  não mudam de nome/conteúdo.
- `docs/plans/57-cancelamento-info-variante.md` — este plano.

## Test strategy

`cancelamento_info()` testado sem HTTP em `test_transitions.py`, seguindo o padrão de
`Requisicao(estado=..., numero_publico=...)` não persistida já usado ali:

1. `RASCUNHO` + `numero_publico=None` → `CancelamentoVariant.DESCARTE`,
   `requer_justificativa=False`, `libera_reserva=False`.
2. `RASCUNHO` + `numero_publico` setado → `CancelamentoVariant.CANCELAMENTO`, ambas flags
   `False`.
3. `AGUARDANDO_AUTORIZACAO` → `CANCELAMENTO`, ambas flags `False`.
4. `AUTORIZADA` e `PRONTA_PARA_RETIRADA` (parametrizado) → `CANCELAMENTO`, ambas flags
   `True`.
5. Estado fora de `TRANSICOES[Operacao.CANCELAR].estados_origem` (ex.: `ATENDIDA`) → levanta
   `EstadoInvalido` com `code='estado_origem_invalido'`.
6. Retorno é sempre instância `CancelamentoInfo` frozen (`dataclasses.FrozenInstanceError`
   ao tentar mutar um campo).

View: os 2 testes que hoje leem `response.context['cancelamento_titulo']` passam a checar
`response.context['cancelamento_info'].variante`. Suíte completa roda ao final para confirmar
que HTML renderizado (`'Descartar rascunho' in html`, `'Justificativa do cancelamento' in
html`) permanece idêntico — nenhuma asserção de texto muda de valor esperado, só de origem.

`cancelamento_copy` (o dicionário de lookup em si) ganha teste direto e novo em
`test_templatetags.py` (módulo existente, mesmo padrão de `test_get_item`/
`test_formatar_quantidade`), sem passar por HTTP/template rendering — chama a função
Python do simple_tag diretamente com `CancelamentoInfo` + `estado` construídos à mão e
compara o dict retornado com o texto esperado, cobrindo as 4 combinações (`DESCARTE`+
`RASCUNHO`; `CANCELAMENTO`+`RASCUNHO`; `CANCELAMENTO`+`AGUARDANDO_AUTORIZACAO`;
`CANCELAMENTO`+`AUTORIZADA`/`PRONTA_PARA_RETIRADA`). Isso cobre o gap apontado pelo
CodeRabbit: a tabela de copy passa a ter cobertura própria, independente do teste de view
que só confirma um fragmento de HTML por cenário.

## Invariants

- Regra de domínio preservada: `requer_justificativa`/`libera_reserva` só `True` a partir de
  `AUTORIZADA`/`PRONTA_PARA_RETIRADA` (mesma condição de hoje em `_cancelar_requisicao_impl`).
- `cancelamento_info` não faz IO nem policy — puramente derivada de `requisicao.estado` +
  `requisicao.numero_publico` + `TRANSICOES[Operacao.CANCELAR]`, mesmo contrato de
  `verificar_transicao_valida` (ADR-0011: "a tabela nunca codifica autorização").
- Variante classifica, não decide efeito — os efeitos (justificativa obrigatória, liberação
  de reserva) continuam vindo das flags, nunca de `if variante == X` em `services/`.

## Risks

- Sem mudança de schema/migration — não aplica reset de ambiente.
- Nenhuma dependência de contrato OpenAPI (app é server-rendered, sem DRF).
