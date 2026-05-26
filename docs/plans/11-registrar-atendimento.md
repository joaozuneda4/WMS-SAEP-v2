# Plano #11 — Registrar atendimento total ou parcial

Issue: https://github.com/JMZR-SAEP/SAEP/issues/11
Transições cobertas: **TR-016** (atendimento total), **TR-017** (atendimento parcial), **TR-018** (bloqueio sem entrega).
Estado: `PRONTA_PARA_RETIRADA -> ATENDIDA`.

## 1. Escopo

### Inclui
- Service `registrar_atendimento` em `apps/requisicoes/services.py`.
- Policy `pode_atender_retirada` / `exigir_pode_atender_retirada` em `apps/requisicoes/policies.py`.
- Form `RegistrarAtendimentoForm` (formset por item) em `apps/requisicoes/forms.py`.
- View `registrar_atendimento_view` (GET formulário + POST) em `apps/requisicoes/views.py`.
- URL `<int:pk>/atender/` em `apps/requisicoes/urls.py`.
- Transição `PRONTA_PARA_RETIRADA -> ATENDIDA` em `transitions.py`.
- Helper de service `consumir_e_liberar_reservas_para_atendimento` em `apps/estoque/services.py` (mutação física + reserva sob lock). Selectors são read-only por convenção; este helper muta saldo e reserva.
- Template `atender_retirada.html` + ajuste em `detalhe.html` (botão "Registrar atendimento" quando `pode_atender_retirada`).
- Atualização do `_detalhe_context`: nova flag `pode_atender_retirada`.
- Testes: services, policies, views, forms — cobertura TR-016, TR-017, TR-018, permissão, estado inválido, saldo insuficiente.

### Não inclui
- Notificações pós-commit (fora de escopo da issue).
- Cancelamento de pronta para retirada (TR-014 — outra issue).
- Devoluções (TR-020) / estornos (TR-021).
- Edição de itens da requisição depois da retirada.

## 2. Arquivos tocados

| Arquivo | Mudança |
|---|---|
| `apps/requisicoes/services.py` | Adicionar `registrar_atendimento` |
| `apps/requisicoes/policies.py` | Adicionar `pode_atender_retirada` / `exigir_pode_atender_retirada` |
| `apps/requisicoes/forms.py` | Adicionar `RegistrarAtendimentoForm` (formset) |
| `apps/requisicoes/views.py` | Adicionar `registrar_atendimento_view`; estender `_detalhe_context` |
| `apps/requisicoes/urls.py` | Adicionar rota `atender` |
| `apps/requisicoes/transitions.py` | Adicionar `PRONTA_PARA_RETIRADA -> {ATENDIDA}` |
| `apps/estoque/services.py` | Adicionar `consumir_e_liberar_reservas_para_atendimento` |
| `apps/requisicoes/templates/requisicoes/atender_retirada.html` | Novo formulário (UI) |
| `apps/requisicoes/templates/requisicoes/detalhe.html` | Botão para abrir formulário de atendimento |
| `apps/requisicoes/tests/test_services.py` | Bateria TR-016/017/018 |
| `apps/requisicoes/tests/test_policies.py` | `pode_atender_retirada` matriz |
| `apps/requisicoes/tests/test_views.py` | view: GET/POST/permissão/estado |
| `apps/requisicoes/tests/test_forms.py` | validação por item |

## 3. Contrato do service

```python
@transaction.atomic
def registrar_atendimento(
    *,
    ator_id: int,
    requisicao_id: int,
    itens: list[ItemAtendimentoEntrada],
    retirante_nome: str,
    observacao: str = '',
) -> Requisicao: ...
```

```python
class ItemAtendimentoEntrada(TypedDict):
    item_id: int
    quantidade_entregue: Decimal  # >= 0, <= quantidade_autorizada
    justificativa: str            # obrigatória quando entregue < autorizada (incl. 0)
```

### Ordem do service
1. Carregar `ator` por id; `DadosInvalidos('ator_nao_encontrado')` se ausente.
2. `Requisicao.objects.select_for_update().get(pk=...)` (lock primeiro); `DadosInvalidos('requisicao_nao_encontrada')` se ausente.
3. `exigir_pode_atender_retirada(ator, requisicao)`.
4. Validar `estado == PRONTA_PARA_RETIRADA` — senão `EstadoInvalido('estado_origem_invalido')`.
5. Validar `verificar_transicao_valida(PRONTA_PARA_RETIRADA, ATENDIDA)`.
6. Validar `retirante_nome` não vazio — `DadosInvalidos('retirante_obrigatorio')`.
7. Carregar itens autorizados (`quantidade_autorizada__gt=0`) ordenados por id.
8. Validar payload: cada item do payload mapeia 1:1 com item autorizado da requisição (`DadosInvalidos('item_invalido')` se faltar/sobrar/duplicar/estranho).
9. Para cada item:
   - `0 <= entregue <= autorizada` — `DadosInvalidos('quantidade_entregue_invalida')`.
   - se `entregue < autorizada`, exigir `justificativa.strip()` — `DadosInvalidos('justificativa_obrigatoria')`.
10. Bloqueio TR-018: se `sum(entregue) == 0`, `EstadoInvalido('atendimento_sem_entrega')`.
11. `consumir_e_liberar_reservas_para_atendimento` (lock de saldos em ordem determinística):
    - baixa física: `saldo_fisico -= entregue`.
    - reserva consumida = `entregue`; reserva liberada = `autorizada - entregue`.
    - reserva resultante: `saldo_reservado -= autorizada` (consome o reservado pela autorização integral).
    - valida físico suficiente: `saldo_fisico >= entregue` — `ConflitoDominio('saldo_fisico_insuficiente')`.
    - valida reserva suficiente: `saldo_reservado >= autorizada` — `ConflitoDominio('reserva_insuficiente')`.
12. Persistir `quantidade_entregue` e `justificativa_entrega` em cada item.
13. `requisicao.estado = ATENDIDA; save(update_fields=...)`.
14. Timeline:
    - `ATENDIMENTO_TOTAL` se `entregue == autorizada` para todos os itens;
    - senão `ATENDIMENTO_PARCIAL`;
    - se houve liberação (qualquer `entregue < autorizada`), cria evento adicional `LIBERACAO_RESERVA` com metadata `{'origem': 'atendimento_parcial'}`.
    - metadata principal inclui `retirante` e `observacao` quando preenchidos.
15. Retorna `requisicao`.

### Policy
`pode_atender_retirada(ator, requisicao) -> bool`:
- ator ativo;
- superusuário OR auxiliar/chefe do almoxarifado;
- estado da requisição não importa (view aplica filtro adicional na flag UI).

Mesma forma que `pode_separar_para_retirada`. `exigir_pode_atender_retirada` delega.

## 4. Estratégia de testes

### Services (`test_services.py`)
- TR-016 feliz: `entregue == autorizada` em todos os itens → `estado=ATENDIDA`, timeline `ATENDIMENTO_TOTAL`, físico baixado, reserva zerada, sem evento `LIBERACAO_RESERVA`.
- TR-017 feliz parcial: um item entregue < autorizada com justificativa → `estado=ATENDIDA`, `ATENDIMENTO_PARCIAL` + `LIBERACAO_RESERVA`, físico baixado parcial, reserva liberada parcial.
- TR-017 entrega zero por item: ok com justificativa; entregue 0 + outro item entregue > 0.
- TR-018 bloqueio: todos os itens com entregue 0 → `EstadoInvalido('atendimento_sem_entrega')`.
- Justificativa obrigatória ausente → `DadosInvalidos('justificativa_obrigatoria')`.
- Entregue > autorizada → `DadosInvalidos('quantidade_entregue_invalida')`.
- Entregue negativa → `DadosInvalidos('quantidade_entregue_invalida')`.
- Estado origem != PRONTA_PARA_RETIRADA → `EstadoInvalido('estado_origem_invalido')`.
- Permissão negada (solicitante, chefe de obras) → `PermissaoNegada`.
- Aceita aux/chefe almox e superuser.
- Ator inexistente → `DadosInvalidos('ator_nao_encontrado')`.
- Requisição inexistente → `DadosInvalidos('requisicao_nao_encontrada')`.
- Retirante vazio → `DadosInvalidos('retirante_obrigatorio')`.
- Idempotência: segundo POST após sucesso → `EstadoInvalido` (estado origem ATENDIDA).
- Multi-itens: liberação de reserva apenas para os itens parciais.
- Saldo físico insuficiente (físico < entregue) → `ConflitoDominio('saldo_fisico_insuficiente')` e estado não muda.

### Policies (`test_policies.py`)
- `pode_atender_retirada`: ativo+superuser True; aux almox True; chefe almox True; chefe setor False; solicitante False; inativo False.

### Views (`test_views.py`)
- GET sem login → 302 login.
- GET com solicitante → 403.
- GET com aux almox em requisição PRONTA_PARA_RETIRADA → 200 + form.
- POST feliz total → redirect detalhe, mensagem success, estado ATENDIDA.
- POST parcial com justificativa → redirect detalhe + mensagem success.
- POST sem entrega → mensagem warning + estado preservado.
- POST estado origem inválido → mensagem warning.
- POST permissão negada → 403.

### Forms (`test_forms.py`)
- Validação formset: entregue ausente, > autorizada, parcial sem justificativa.

## 5. Invariantes preservados

Da `docs/estado-transicoes-requisicao.md` §5 e §6:
- TR-016: entregue == autorizada para todos os itens autorizados; baixa físico no entregue; consome reserva.
- TR-017: ao menos um entregue > 0; entregue <= autorizada; justificativa quando entregue < autorizada (incl. zero); libera reserva não entregue; finaliza como `atendida`.
- TR-018: todos zero ⇒ bloqueio.
- Atomicidade: `transaction.atomic` + lock determinístico (Requisição -> saldos por `(estoque_id, material_id, id)`).
- Quantidade líquida: `entregue` é persistido apenas neste fluxo; constraint `item_entregue_ate_autorizada` mantida.
- Timeline append-only; `ATENDIMENTO_TOTAL` e `ATENDIMENTO_PARCIAL` mutuamente exclusivos; `LIBERACAO_RESERVA` opcional.

## 6. Riscos

| Risco | Mitigação |
|---|---|
| Concorrência: dois auxiliares atendem a mesma requisição | `select_for_update` na Requisicao antes de qualquer leitura/escrita |
| Saldo físico negativo | Validar `saldo_fisico >= entregue` sob lock antes de mutar |
| Reserva fica negativa | Validar `saldo_reservado >= autorizada` antes de subtrair |
| Múltiplos saldos do mesmo material | `consumir_e_liberar_reservas_para_atendimento` falha com `ConflitoDominio('saldo_ambiguo')` antes de mutar |
| Form vazia ou items extras | Validação 1:1 itens autorizados ↔ payload no service |
| Timeline duplicada em refetch | Estado origem != PRONTA_PARA_RETIRADA bloqueia segunda execução |
| OpenAPI/contracts | UI server-rendered; sem alteração de serializer |

## 7. Frontend

Tela própria `atender_retirada.html` (não pop-up no detalhe). Acesso pelo botão "Registrar atendimento" no detalhe quando `pode_atender_retirada`.

Componentes:
- Cabeçalho com número público + setor beneficiário + retirante (input obrigatório).
- Tabela de itens: material, autorizada, input `quantidade_entregue` (decimal), input `justificativa` (revelado quando `entregue < autorizada`).
- Observação geral (textarea opcional).
- Botão "Confirmar retirada" (submit normal POST PRG).

Estilo: design system Tailwind + componentes existentes (cards `rounded-xl border border-slate-200 bg-white shadow-sm`). Acessibilidade conforme `_estado_badge` e padrão atual.

Revisão UI via `/web-design-guidelines` ao final.
