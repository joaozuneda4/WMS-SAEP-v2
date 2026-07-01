# Plano: Formset entrega VOs tipados (LinhaAtendimento) (#55)

## Scope

**Inclui:**
- Novo módulo `apps/requisicoes/types.py`, seam entre `forms.py` e `services/atendimento.py` (mesmo papel de `apps/estoque/types.py`), com o VO `LinhaAtendimento` (`@dataclass(frozen=True)`, campos `item_id: int`, `quantidade_entregue: Decimal`, `justificativa: str`).
- `BaseItemAtendimentoFormSet.linhas_atendimento()` — novo método, estilo `linhas_validas()`, que percorre `self.forms` e devolve `list[LinhaAtendimento]` a partir de `form.cleaned_data`. Form/formset não importam nem chamam service.
- `registrar_atendimento_view` para de montar `itens_payload` (dict) na mão; passa a chamar `formset.linhas_atendimento()` e repassar o resultado direto ao service.
- `apps/requisicoes/services/atendimento.py`: `registrar_atendimento(*, itens: list[LinhaAtendimento], ...)` passa a receber o VO em vez do `TypedDict` `ItemAtendimentoEntrada` (removido). Corpo do service ajusta acesso `entrada['x']` → `entrada.x`; mantém a validação defensiva (`int()`/`Decimal()`/duplicidade/pertencimento) porque o service é um limite público e não pode confiar cegamente no chamador.
- `services/__init__.py`: remove reexport de `ItemAtendimentoEntrada`; nada mais muda na API pública (mesmos nomes de função).
- Testes: `test_forms.py` cobre `linhas_atendimento()` (linhas válidas, formset vazio); `test_services.py`/`test_views.py` atualizados para construir `LinhaAtendimento(...)` em vez de dict literal onde chamam `registrar_atendimento` diretamente. Helper `_payload_total` em `test_services.py` passa a devolver `list[LinhaAtendimento]`.

**Não inclui:**
- `ItemRequisicaoForm`/`BaseItemRequisicaoFormSet.linhas_validas()` (usado por `criar_requisicao`/`editar_rascunho`) — a issue cita esse método apenas como precedente de estilo (é o próprio texto da emenda do ADR-0004); não está nos critérios de aceite mudar seu retorno de dict para VO. Fora de escopo por instrução explícita de não expandir além do pedido.
- `registrar_devolucao` — recebe escalares (`item_id`, `quantidade`), não uma lista de itens; não há shaping manual de payload a mover.
- Qualquer mudança de regra de negócio, transição de estado ou UI/template. Puro reshaping de payload.
- Mudança de schema/model — não se aplica.

## Files Touched

| Arquivo | Operação |
|---|---|
| `apps/requisicoes/types.py` | **Novo.** VO `LinhaAtendimento` |
| `apps/requisicoes/forms.py` | `BaseItemAtendimentoFormSet.linhas_atendimento()` |
| `apps/requisicoes/views.py` | `registrar_atendimento_view` chama `formset.linhas_atendimento()` |
| `apps/requisicoes/services/atendimento.py` | `registrar_atendimento` recebe `list[LinhaAtendimento]`; remove `ItemAtendimentoEntrada` |
| `apps/requisicoes/services/__init__.py` | Remove reexport de `ItemAtendimentoEntrada` |
| `apps/requisicoes/tests/test_forms.py` | Testes de `linhas_atendimento()` |
| `apps/requisicoes/tests/test_services.py` | Chamadas a `registrar_atendimento` passam `LinhaAtendimento` |
| `apps/requisicoes/tests/test_views.py` | Ajusta apenas se algum teste inspecionar o payload interno |

## Implementation Order

1. RED/GREEN `apps/requisicoes/types.py` + `test_forms.py`: `LinhaAtendimento` e `BaseItemAtendimentoFormSet.linhas_atendimento()`.
2. GREEN `views.py`: troca shaping manual pela chamada ao método do formset.
3. RED/GREEN `services/atendimento.py`: `registrar_atendimento` recebe VO; ajusta acesso por atributo; `services/__init__.py` atualizado.
4. Ajusta `test_services.py`/`test_views.py` para construir `LinhaAtendimento` nas chamadas diretas ao service.
5. `ruff format .` + `ruff check .` + suíte completa.

## Test Strategy

### Form/formset (`test_forms.py`)
- `linhas_atendimento()` devolve `list[LinhaAtendimento]` com os valores certos para formset válido com N linhas.
- Linha sem `cleaned_data` (formset inválido/vazio) é ignorada, não quebra.
- Tipo de retorno é `LinhaAtendimento`, não dict — assinatura tipada, `isinstance` checável.

### Service (`test_services.py`)
- Caminho feliz (total e parcial) usando `LinhaAtendimento` no lugar do dict — suíte existente adaptada, sem mudança de comportamento esperado.
- `item_id` fora do conjunto autorizado, duplicado, quantidade negativa/acima da autorizada, justificativa ausente — mesmas exceções de domínio (`DadosInvalidos`, `EstadoInvalido`) continuam sendo lançadas pelo service, não pelo form.
- `DadosInvalidos` nunca é levantada a partir do form (form só usa `django.forms.ValidationError`).

### View (`test_views.py`)
- POST válido do formulário de atendimento continua funcionando fim a fim (formset → VO → service → redirect/mensagem).
- Suíte já existente cobre isso; roda sem alteração de expectativa.

## Invariants

- ADR-0004 (emenda 2026-06-26): aplicado nesta slice ao novo `BaseItemAtendimentoFormSet`/`LinhaAtendimento` — forms/formsets entregam VOs tipados, nunca dicts anônimos nem comandos; form não conhece o service. `BaseItemRequisicaoFormSet.linhas_validas()` permanece fora de escopo (continua retornando dict), conforme já declarado em "Não inclui".
- ADR-0011: validação de qualidade de input no form (`ValidationError`); invariantes de domínio no service (`apps.core.exceptions`); service mantém assinatura keyword-only e IDs na borda.
- TR-016/017/018 (atendimento total/parcial, bloqueio sem entrega) — comportamento do service não muda, só o tipo do parâmetro `itens`.

## Risks

- **Import direction:** `types.py` deve ser importado tanto por `forms.py` quanto por `services/atendimento.py` sem criar dependência cruzada form→service ou service→form; `types.py` não importa nenhum dos dois.
- **TypedDict → dataclass:** o service faz `entrada['x']` hoje; trocar para `entrada.x` em todos os pontos (payload_por_item, payload_estoque, atualização dos itens) — risco de esquecer algum acesso por chave e quebrar em runtime (não em type-check, já que é dentro do próprio módulo).
- **Testes diretos ao service:** vários testes em `test_services.py` constroem `itens=[{...}]` chamando `registrar_atendimento` diretamente (não via view/formset) — todos precisam trocar para `LinhaAtendimento(...)`, senão quebram com `AttributeError` no service.
