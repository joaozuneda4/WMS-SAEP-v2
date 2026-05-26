# Plano: Cancelar requisição antes da retirada (#12)

## Scope

**Inclui:**
- Policy `pode_cancelar_requisicao(ator, requisicao)` + `exigir_pode_cancelar_requisicao` em `apps/requisicoes/policies.py`, cobrindo:
  - rascunho nunca enviado: criador pode descartar;
  - rascunho numerado: criador pode cancelar logicamente;
  - `aguardando_autorizacao`: criador ou beneficiário podem cancelar sem justificativa obrigatória;
  - `autorizada` e `pronta_para_retirada`: criador, beneficiário, almoxarifado (aux/chefe) e superusuário podem cancelar com justificativa obrigatória.
- Transições declarativas em `apps/requisicoes/transitions.py` para os cancelamentos lógicos que preservam requisição:
  - `rascunho -> cancelada` (rascunho numerado);
  - `aguardando_autorizacao -> cancelada`;
  - `autorizada -> cancelada`;
  - `pronta_para_retirada -> cancelada`.
- Service `cancelar_requisicao(*, ator_id, requisicao_id, justificativa='')` em `apps/requisicoes/services.py`:
  - trava `Requisicao` sob `select_for_update`;
  - revalida estado e permissão sob lock;
  - libera reserva automaticamente quando houver autorização;
  - registra timeline `cancelamento` e `liberacao_reserva` quando aplicável;
  - preserva `numero_publico` nos cancelamentos lógicos.
- Service `descartar_rascunho(*, ator_id, requisicao_id)` para rascunho nunca enviado:
  - exclui a requisição sem consumir número público;
  - não cria reserva, baixa física nem timeline operacional.
- Helper de estoque em `apps/estoque/services.py` para liberar reserva sem tocar físico, com lock determinístico e falha sem efeitos parciais quando houver saldo inconsistente.
- View POST `cancelar_requisicao_view` em `apps/requisicoes/views.py`, com PRG/HX-Redirect e tradução de `PermissaoNegada`, `EstadoInvalido`, `DadosInvalidos` e `ConflitoDominio`.
- URL nova `requisicoes/<int:pk>/cancelar/`.
- UI do detalhe:
  - botão destrutivo contextual no bloco de ações;
  - modal acessível com `dialog`, backdrop, Escape e restauração de foco;
  - título/CTA variam entre `Descartar rascunho`, `Cancelar rascunho` e `Cancelar requisição`;
  - justificativa aparece só quando obrigatória.
- Testes por camada:
  - `test_policies.py` para permissão de cancelamento;
  - `test_services.py` para descarte, cancelamento, liberação de reserva, timeline e estados bloqueados;
  - `test_views.py` para contrato HTTP, modal/botão no detalhe, redirect e erro de validação.

**Não inclui:**
- Autorizar, separar para retirada, atender, devolver ou estornar.
- Nova transição de domínio para atendimento parcial/total.
- Mudanças de schema/model.
- Filtros, paginação ou polling nas listas.

## Files Touched

| Arquivo | Operação |
|---|---|
| `apps/estoque/services.py` | Novo helper para liberar reserva |
| `apps/requisicoes/transitions.py` | Declarar transições de cancelamento lógico |
| `apps/requisicoes/policies.py` | Policy de cancelamento contextual |
| `apps/requisicoes/services.py` | `descartar_rascunho` e `cancelar_requisicao` |
| `apps/requisicoes/views.py` | `cancelar_requisicao_view` e flags de contexto no detalhe |
| `apps/requisicoes/urls.py` | Rota `<pk>/cancelar/` |
| `apps/requisicoes/templates/requisicoes/detalhe.html` | Botão contextual e modal de cancelamento |
| `apps/requisicoes/templates/requisicoes/partials/_cancelar_modal.html` | Modal reutilizável do cancelamento |
| `apps/requisicoes/tests/test_policies.py` | Cobertura de permissão |
| `apps/requisicoes/tests/test_services.py` | Cobertura de descarte/cancelamento, timeline e reserva |
| `apps/requisicoes/tests/test_views.py` | Cobertura do POST, modal e renderização do botão |

## UX Direction

Direção: **Pragmatic Minimal / Accessible & Ethical**. O detalhe continua denso e operacional, mas o cancelamento ganha hierarquia clara de risco:
- rascunho nunca enviado: ação destrutiva simples;
- rascunho numerado: cancelamento lógico sem justificativa;
- autorizada/pronta: cancelamento destrutivo com justificativa obrigatória e indicação explícita de liberação de reserva.

Regras aplicadas:
- Modal real, não `window.confirm`.
- Um único CTA destrutivo por contexto.
- Texto curto, consequência clara e contraste forte no estado destrutivo.
- Foco visível, `Escape` fecha, foco volta ao botão de origem.

## Implementation Order

1. RED policies + transitions: permissão, estados permitidos e bloqueios de finalizados.
2. RED estoque/services: helper de liberação de reserva e descarte/cancelamento feliz.
3. GREEN services: descarte de rascunho nunca enviado, cancelamento lógico, reserva liberada, timeline.
4. RED views/urls/templates: botão contextual, modal acessível, POST e mensagens.
5. GREEN views/templates.
6. Revisão a11y/UX com modal e CTA destrutivo.
7. `rtk make test`.

## Test Strategy

### Policies
- Criador pode descartar rascunho nunca enviado.
- Criador pode cancelar rascunho numerado.
- Criador ou beneficiário podem cancelar `aguardando_autorizacao`.
- Criador, beneficiário, almoxarifado (aux/chefe) e superusuário podem cancelar `autorizada` ou `pronta_para_retirada`.
- Usuário fora do papel ou estado final recebe `False`.

### Services
- Descarte de rascunho nunca enviado exclui a requisição e não deixa timeline nem alteração de estoque.
- Cancelamento lógico de rascunho numerado preserva `numero_publico` e registra `cancelamento`.
- Cancelamento de `aguardando_autorizacao` muda para `cancelada` sem exigir justificativa.
- Cancelamento de `autorizada` / `pronta_para_retirada` exige justificativa e libera toda reserva sem mudar saldo físico.
- Cancelamento de estados finais levanta `EstadoInvalido`.
- Permissão negada levanta `PermissaoNegada`.
- Justificativa vazia quando obrigatória levanta `DadosInvalidos`.
- Nenhuma operação deixa escrita parcial em caso de falha.

### Views
- GET do detalhe sem login redireciona.
- POST de cancelamento sem login redireciona.
- POST por ator sem permissão retorna 403.
- POST válido redireciona para detalhe ou lista de origem no descarte.
- HTMX devolve `204` com `HX-Redirect`.
- O detalhe renderiza `Descartar rascunho`, `Cancelar rascunho` ou `Cancelar requisição` conforme estado/numero.
- O modal mostra textarea apenas quando a justificativa é obrigatória.
- Cancelamento sem justificativa obrigatória reabre o detalhe com erro inline no modal.

## Invariants

- REQ-02: rascunho nunca enviado não consome número público.
- REQ-04: cancelamento lógico preserva número público.
- REQ-08: timeline registra eventos principais e é visível a autorizados.
- PER-03: chefia vê/cancela dentro do próprio setor quando aplicável.
- PER-05: superusuário tem permissões totais.
- PER-08: view e service chamam a mesma policy.
- EST-02: autorização reserva integralmente, sem baixar físico.
- EST-04: cancelamento antes da retirada libera reserva.
- EST-06: transições críticas rodam em transação com lock.
- TR-003/TR-004/TR-012/TR-013/TR-014: descarte e cancelamento seguem o fluxo descrito nos docs.

## Risks

- **Rascunho sem número:** o descarte precisa ser delete hard, não um estado novo, para respeitar o contrato de “não consumiu número público”.
- **Reserva só no helper de estoque:** liberar saldo sem tocar físico precisa seguir o mesmo lock determinístico das outras mutações.
- **Modal acessível:** precisa trap de foco, `Escape` e retorno ao botão de origem; `dialog` nativo ajuda, mas a revisão visual vai confirmar.
- **UX de erro no modal:** validação de justificativa deve voltar o modal aberto sem quebrar PRG.
