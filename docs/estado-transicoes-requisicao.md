# Estados e Transições da Requisição — WMS-SAEP

## 1. Objetivo

Síntese operacional da máquina de estados de requisições. Use este arquivo para implementar enums, tabela declarativa de transições, services, policies, timeline, movimentações de estoque e testes.

Fontes de alinhamento: `docs/processos-almoxarifado.md` e `docs/matriz-invariantes.md`.

## 2. Princípios

- Transições devem ser declarativas e aplicadas por uma função/service única.
- Services validam domínio, estado, permissões contextuais, estoque/reserva e registram timeline.
- Policies validam ator, papel, setor, beneficiário e objeto.
- Views e services chamam a mesma policy quando houver autorização contextual.
- Mudanças de saldo/reserva exigem `transaction.atomic()`, lock pessimista e ordem determinística.
- Timeline registra os eventos principais e é visível a usuários autorizados no escopo da requisição.
- Notificações são side effects pós-commit; nunca decidem sucesso da transação.

## 3. Estados canônicos

| Estado | Técnico | Papel no fluxo | Itens editáveis? | Estoque/reserva | Final? |
|---|---|---|---|---|---|
| Rascunho | `rascunho` | Criação/correção antes da autorização. | Sim, somente pelo criador enquanto permanecer rascunho. | Sem reserva/baixa. | Não |
| Aguardando autorização | `aguardando_autorizacao` | Fila do chefe do setor do beneficiário. | Não; deve retornar para rascunho. | Sem reserva/baixa. | Não |
| Recusada | `recusada` | Recusa da requisição inteira com motivo. | Não; deve ser copiada ou recriada conforme regra futura. | Sem reserva/baixa. | Não |
| Autorizada | `autorizada` | Aprovada integralmente pelo chefe do setor do beneficiário e disponível para separação pelo Almoxarifado. | Não | Reserva integral criada na autorização; sem baixa físico. | Não |
| Pronta para retirada | `pronta_para_retirada` | Quantidades autorizadas foram separadas e aguardam coleta/retirada final. | Não | Reserva mantida; sem baixa físico. | Não |
| Atendida | `atendida` | Retirada final registrada pelo Almoxarifado, total ou parcial sobre o autorizado. | Não | Baixa entregue; consome reserva entregue e libera reserva não entregue. | Sim |
| Cancelada | `cancelada` | Encerrada antes da retirada final. | Não | Se autorizada ou pronta para retirada, libera reserva; não baixa físico. | Sim |
| Estornada | `estornada` | Saída atendida revertida formalmente. | Não | Movimentação inversa de estorno. | Sim |

## 4. Eventos de timeline

| Evento | Técnico | Quando | Responsável | Justificativa |
|---|---|---|---|---|
| Criação | `criacao` | Criação do rascunho com ao menos um item. | Criador | Não |
| Envio | `envio_autorizacao` | Rascunho vai para autorização. | Criador | Não |
| Recusa | `recusa` | Chefe recusa a requisição inteira. | Chefe do setor do beneficiário | Sim |
| Autorização total | `autorizacao_total` | Todos os itens autorizados integralmente. | Chefe do setor do beneficiário | Não |
| Cancelamento | `cancelamento` | Cancelamento em estado permitido. | Conforme estado | Só se autorizada ou pronta para retirada |
| Separação para retirada | `separacao_retirada` | Quantidades autorizadas foram separadas e estão prontas para retirada. | Almoxarifado | Não |
| Atendimento total | `atendimento_total` | Tudo que foi autorizado foi entregue. | Almoxarifado | Não |
| Atendimento parcial | `atendimento_parcial` | Entrega menor que autorizada, com ao menos um item entregue. | Almoxarifado | Sim, por item |
| Liberação de reserva | `liberacao_reserva` | Cancelamento de autorizada ou atendimento parcial. | Ator da transição | Conforme transição |
| Devolução registrada | `devolucao_registrada` | Entrada por devolução vinculada. | Almoxarifado | Sim |
| Estorno | `estorno` | Reversão total/parcial pelo chefe de Almoxarifado. | Chefe de Almoxarifado | Sim |
| Atualização de estoque relevante | `atualizacao_estoque_relevante` | Operação ou importação afeta saldo/divergência de material relacionado. | Ator da operação | Não |

## 5. Matriz compacta de transições

| ID | De -> Para | Ação | Atores | Regras críticas | Efeitos | Ref. |
|---|---|---|---|---|---|---|
| TR-001 | N/A -> Rascunho | Criar requisição | Solicitante para si; auxiliar de setor para si ou usuários do próprio setor; chefe de setor para usuários do próprio setor; Almoxarifado para qualquer usuário | Usuário ativo; beneficiário permitido; setor do beneficiário ativo; ao menos um item; material ativo, sem divergência crítica, com saldo disponível inicial; quantidade solicitada positiva e compatível com saldo disponível inicial | Cria cabeçalho, itens, criador, beneficiário e snapshot do setor do beneficiário; sem número público; registra criação | 1.1, 1.2, 1.5, 11; REQ-01, REQ-02, REQ-05, REQ-07, EST-08, EST-10 |
| TR-002 | Rascunho -> Rascunho | Editar rascunho | Criador | Requisição ainda não enviada; ao menos um item; materiais ativos, sem divergência crítica e com saldo disponível inicial | Atualiza itens e observação geral; não gera número público; não reserva nem baixa estoque | 1.3, 1.4; REQ-02, REQ-05, REQ-06 |
| TR-003 | Rascunho -> descartado | Descartar rascunho nunca enviado | Criador ou beneficiário | Nunca enviado; sem número público | Pode excluir ou descartar sem consumir número público, sem reserva e sem movimentação de estoque | 1.3, 1.4; REQ-02 |
| TR-004 | Rascunho -> Cancelada | Cancelar rascunho já numerado | Criador ou beneficiário | Já possui número público; preserva número público | Encerra logicamente sem justificativa obrigatória; bloqueia edição, envio e atendimento; sem reserva e sem baixa de estoque | 1.3, 1.4; REQ-04, REQ-06 |
| TR-005 | Rascunho -> Aguardando autorização | Enviar | Criador | Ao menos um item; gera `REQ-AAAA-NNNNNN` apenas no primeiro envio; reenvios preservam número público | Registra envio; entra na fila do chefe do setor do beneficiário; não reserva nem baixa estoque | 1.3, 1.4; REQ-03, REQ-04, REQ-05, EST-02 |
| TR-008 | Aguardando autorização -> Autorizada | Autorizar | Chefe do setor do beneficiário | Beneficiário pertence ao setor do chefe; todos os itens solicitados são autorizados integralmente; itens ativos, sem divergência crítica; saldo disponível atual suficiente para reservar tudo; transação e lock de estoque | Persiste `autorizada = solicitada` para todos os itens; cria reserva integral; não baixa físico; notifica envolvidos quando aplicável | 1.3, 1.4; PER-03, ITEM-01, EST-02, EST-05, EST-06, EST-08 |
| TR-010 | Aguardando autorização -> Aguardando autorização | Bloquear autorização inválida | Chefe do setor do beneficiário | Tentativa de autorizar parcialmente; divergência crítica; item inativo; saldo disponível atual insuficiente para reservar todos os itens solicitados | Não transiciona; orientar recusa inteira ou resolução da divergência/indisponibilidade antes da autorização | 1.3, 1.4; ITEM-01, EST-05, EST-08 |
| TR-011 | Aguardando autorização -> Recusada | Recusar inteira | Chefe do setor do beneficiário | Beneficiário pertence ao setor do chefe; motivo obrigatório | Registra motivo, chefe e data; sai da fila; sem reserva e sem baixa de estoque; notifica envolvidos quando aplicável | 1.3, 1.4; PER-03 |
| TR-012 | Aguardando autorização -> Cancelada | Cancelar antes da autorização | Criador ou beneficiário | Estado `aguardando_autorizacao`; sem justificativa obrigatória | Remove da fila; encerra logicamente; preserva número público; sem reserva e sem baixa de estoque | 1.3, 1.4; REQ-04 |
| TR-013 | Autorizada -> Cancelada | Cancelar autorizada | Criador, beneficiário, auxiliar de Almoxarifado ou chefe de Almoxarifado | Justificativa obrigatória; ainda sem retirada final; transação e lock de estoque | Libera reservas automaticamente; não altera físico; registra cancelamento e liberação de reserva; notifica envolvidos quando aplicável | 1.3, 1.4; EST-04, EST-06 |
| TR-014 | Pronta para retirada -> Cancelada | Cancelar pronta para retirada | Criador, beneficiário, auxiliar de Almoxarifado ou chefe de Almoxarifado | Justificativa obrigatória; ainda sem retirada final; transação e lock de estoque | Libera reservas automaticamente; desfaz separação operacional quando aplicável; não altera físico; registra cancelamento e liberação de reserva; notifica envolvidos quando aplicável | 1.3, 1.4; EST-04, EST-06 |
| TR-015 | Autorizada -> Pronta para retirada | Separar para retirada | Auxiliar ou chefe de Almoxarifado | Requisição autorizada integralmente; itens autorizados > 0; físico suficiente para manter a retirada planejada; transação e lock de estoque | Registra separação; mantém reserva; não baixa físico; notifica quando aplicável | 1.3; EST-02, EST-06 |
| TR-016 | Pronta para retirada -> Atendida | Atendimento total | Auxiliar ou chefe de Almoxarifado | Todos os itens autorizados foram entregues; entregue = autorizado nos itens autorizados; físico suficiente; retirada registrada; transação e lock de estoque | Baixa físico na quantidade efetivamente retirada; consome reserva; registra responsável, retirante e observação quando houver; notifica envolvidos quando aplicável | 1.2, 1.3, 1.4; ITEM-02, EST-03, EST-06 |
| TR-017 | Pronta para retirada -> Atendida | Atendimento parcial | Auxiliar ou chefe de Almoxarifado | Ao menos um item entregue > 0; entregue <= autorizado; algum item entregue menor que autorizado ou zerado; justificativa para entrega menor que autorizada ou zero; físico suficiente para entregue; transação e lock de estoque | Baixa físico apenas do entregue; consome reserva entregue; libera reserva não entregue; finaliza como `atendida`, sem estado separado de atendimento parcial e sem pendência | 1.3, 1.4; ITEM-02, ITEM-03, ITEM-05, ITEM-06, EST-03, EST-04, EST-06 |
| TR-018 | Pronta para retirada -> Pronta para retirada | Bloquear atendimento sem entrega | Auxiliar ou chefe de Almoxarifado | Todos os itens seriam entregues com zero | Não finaliza; orientar cancelamento com justificativa | 1.3, 1.4; ITEM-06 |
| TR-019 | Atendida/Estornada -> mesmo estado | Bloquear cancelamento | Qualquer usuário | Estado final operacional | Não transiciona; orientar estorno quando aplicável | 1.3, 1.4 |
| TR-020 | Atendida -> Atendida | Registrar devolução | Auxiliar ou chefe de Almoxarifado | Vinculada a requisição atendida; quantidade <= entregue líquida; justificativa ou observação conforme regra operacional; transação e lock de estoque | Aumenta físico; não altera status nem reserva; registra devolução na timeline e movimentação de estoque | 1.4; EST-01, EST-06 |
| TR-021 | Atendida -> Estornada | Estornar requisição | Chefe de Almoxarifado | Justificativa obrigatória; quantidade válida; preserva histórico original; transação e lock de estoque | Registra movimentação inversa; devolve físico conforme estorno total ou parcial; encerra definitivamente a requisição | 1.3, 1.4; EST-06 |
| TR-022 | Estornada -> Estornada | Bloquear ações pós-estorno | Qualquer usuário | Requisição estornada | Permite somente consulta à timeline e ao histórico por usuários autorizados; bloqueia corrigir, reenviar, separar, atender, cancelar e nova devolução operacional | 1.3, 1.4 |

## 6. Regras rápidas de quantidade e estoque

- Quantidades ficam separadas: `solicitada`, `autorizada`, `entregue`.
- Na autorização, `autorizada = solicitada` para todos os itens; no atendimento, `entregue <= autorizada`.
- Autorização parcial e autorização zero não são permitidas; o chefe autoriza integralmente ou recusa a requisição inteira.
- Entrega parcial e entrega zero exigem justificativa no item correspondente pelo Almoxarifado.
- Requisição atendida precisa de ao menos um item entregue > 0.
- Item autorizado com zero não é permitido; item entregue com zero libera a reserva correspondente no atendimento parcial.
- Atendimento parcial encerra a requisição como `atendida`; não cria estado separado nem pendência automática.
- Se todo o autorizado foi entregue, o status é `atendida`, mesmo que solicitado > autorizado.
- Autorização reserva integralmente o solicitado e não baixa físico.
- Separação para retirada muda o status para `pronta_para_retirada`, mantém reserva e não baixa físico.
- Atendimento baixa físico somente do entregue e consome/libera reserva.
- Cancelamento de autorizada libera reserva e não altera físico.
- Devolução aumenta físico e não altera status.
- Estorno preserva histórico e registra movimentação inversa.
- Saldo disponível = saldo físico - saldo reservado, sempre recalculado no ponto crítico.
- Material divergente bloqueia novas requisições e autorizações até resolução.
- Material inativo não entra em nova requisição, mas permanece em histórico.
- Rascunho nunca enviado não consome número público; número público nasce apenas no primeiro envio e é preservado em reenvios ou cancelamento lógico.

## 7. Ações bloqueadas por estado

| Estado | Bloqueios principais |
|---|---|
| Rascunho | Autorizar, separar, atender, devolver, estornar, baixar estoque. |
| Aguardando autorização | Editar itens diretamente, autorizar parcialmente, separar, atender, devolver, estornar, cancelar como autorizada. |
| Recusada | Autorizar, separar, atender, devolver, estornar, cancelar como autorizada; qualquer correção direta fica fora do escopo deste arquivo. |
| Autorizada | Editar, reenviar, autorizar novamente, devolver antes de atendimento, estornar antes de atendimento. |
| Pronta para retirada | Editar, reenviar, autorizar novamente, devolver antes de atendimento, estornar antes de atendimento. |
| Atendida | Editar, reenviar, autorizar, separar, atender novamente, cancelar. |
| Cancelada | Editar, reenviar, autorizar, separar, atender, devolver, estornar. |
| Estornada | Corrigir, reenviar, autorizar, separar, atender, cancelar, registrar nova devolução operacional. |
