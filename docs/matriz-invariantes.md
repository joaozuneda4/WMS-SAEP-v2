# Matriz de Invariantes — WMS-SAEP

## 1. Objetivo

Referência rápida dos invariantes que não podem ser violados por `models`, `services`, `policies`, comandos, admin actions, ou interfaces futuras.

## 2. Como usar

Para cada mudança, localizar o invariante aplicável, implementar na camada indicada, reforçar com constraint/policy/service quando couber e cobrir teste de caminho feliz, permissão negada e violação de domínio.

## 3. Matriz compacta

| ID | Tema | Invariante | Camada/reforço esperado | Testes mínimos | Ref. |
|---|---|---|---|---|---|
| USR-01 | Usuários | Usuário inativo não acessa nem opera. | Auth/policy. | Login bloqueado; escrita negada. | Crit. 11.1 |
| USR-02 | Usuários | Todo usuário ativo é solicitante. | Policy derivada de usuário ativo. | Criar para si; negar operação fora do papel. | Crit. 11.1 |
| USR-03 | Setores | Usuário pertence a um único setor. | Model; FK de setor principal. | Criar com setor; sem vínculos auxiliares. | Modelo 2.1 |
| USR-04 | Setores | Todo setor operacional ativo possui um chefe ativo; `Setor.chefe` apontando para usuário inativo viola o invariante. | Model/service; validação em alteração e na desativação de usuário. | Criar com chefe ativo; bloquear setor ativo sem chefe ativo. | Backlog ACE-002 |
| USR-05 | Setores | Um chefe responde por apenas um setor. | Constraint/policy. | Bloquear chefe duplicado. | Modelo 2.1 |
| USR-06 | Setores | Setor inativo permanece em histórico e não recebe nova requisição. | Service/policy; preservar FK histórica. | Negar nova requisição; histórico visível. | Modelo 2.1 |
| USR-07 | Setores | Não desativar usuário que chefia setor ativo sem designar antes outro chefe ativo do próprio setor. | Service de desativação de usuário. | Bloquear desativação sem reassignment; permitir com novo chefe válido. | USR-04 |
| PER-01 | Permissões | Solicitante cria apenas para si. | Policy/service compartilhados. | Próprio permitido; terceiro negado. | Crit. 11.1 |
| PER-02 | Permissões | Auxiliar de setor cria para si e usuários dentro do próprio setor. | Policy por setor principal. | Mesmo setor permitido; outro negado. | Crit. 11.2 |
| PER-03 | Permissões | Chefe autoriza só beneficiários do próprio setor. | Policy por setor responsável. | Próprio setor permitido; outro negado. | Crit. 2.1 |
| PER-04 | Permissões | Almoxarifado cria em nome de qualquer usuário de qualquer setor. | Policy de papel operacional. | Criar para setores distintos. | Crit. 1.1 |
| PER-05 | Permissões | Superusuário tem permissões totais, incluindo administração, consulta ampla e operações de negócio/estoque. | Policy/admin/service. | Permitir ação técnica; permitir ação operacional; permitir consulta ampla. | Crit. 11.6 |
| PER-06 | Permissões | Requisição pertence ao setor do beneficiário, não do criador. | Service/model snapshot. | Almoxarifado cria para Obras e vai ao chefe de Obras. | Crit. 1.2 |
| PER-08 | Permissões | Views e services chamam a mesma policy contextual. | `policies.py` ou equivalente. | View e service negam mesmo escopo. | CodeRabbit |
| REQ-01 | Requisições | Toda requisição começa em rascunho. | Service/model default. | Criação gera `rascunho`. | Crit. 1.1 |
| REQ-02 | Requisições | Rascunho nunca enviado não tem número público. | Service/model; número nulo até envio. | Criar sem número; descartar sem consumir número. | Crit. 1.9 |
| REQ-03 | Requisições | Número público nasce no primeiro envio e segue `REQ-AAAA-NNNNNN`. | Gerador anual atômico. | Formato e sequência anual. | Crit. 1.6 |
| REQ-04 | Requisições | Reenvios preservam número público. | Campo histórico imutável. | Retorno e reenvio mantêm número. | Crit. 1.7 |
| REQ-05 | Requisições | Requisição precisa ter ao menos um item. | Regra crítica no service. | Bloquear criar/salvar/enviar sem item. | Crit. 1.1 |
| REQ-06 | Requisições | Após envio, não há edição direta de itens. | Máquina de estados/service. | Bloquear edição; permitir retorno para rascunho. | Crit. 1.8 |
| REQ-07 | Requisições | Registrar criador, beneficiário e setor do beneficiário. | Campos obrigatórios/snapshots. | Criar em nome de terceiro preservando papéis. | Crit. 1.1 |
| REQ-08 | Requisições | Timeline registra eventos principais e é visível a autorizados. | Service/policy. | Eventos do ciclo; autorizado vê completa; fora de escopo não vê. | Modelo 2.1 |
| REQ-09 | Requisições | Cópia recalcula saldo e não copia autorizado/entregue; origem pode ser atendida ou recusada. | Service de cópia. | Copiar atendida ou recusada; bloquear item sem saldo/divergente. | Crit. 1.13 |
| ITEM-01 | Itens | Na autorização, quantidade autorizada deve ser igual à quantidade solicitada para todos os itens. | Service/constraint. | Autorizar integralmente; bloquear autorização parcial, zero ou acima do solicitado. | Crit. 2 |
| ITEM-02 | Itens | Quantidade entregue nunca maior que autorizada. | Service/constraint. | Bloquear entrega acima. | Crit. 3 |
| ITEM-03 | Itens | Atendimento parcial exige justificativa. | Service | Menor com justificativa; sem justificativa negado. | Crit. 3.3 |
| ITEM-04 | Itens | Item autorizado com zero não é permitido. | Service | Bloquear item autorizado com zero; orientar recusa inteira ou resolução da indisponibilidade. | Crit. 2.4 |
| ITEM-05 | Itens | Entrega zero exige justificativa | Service | Zero com justificativa | Crit. 3.4 |
| ITEM-06 | Itens | Requisição atendida precisa de ao menos um item entregue > 0. | Regra agregada no service. | Bloquear finalização sem entrega; orientar cancelamento. | Crit. 3.6 |
| EST-01 | Estoque | Físico e reservado são armazenados; disponível = físico - reservado. | Model/service; disponível calculado. | Cálculo após reserva, retirada e liberação. | Crit. 7.2 |
| EST-02 | Estoque | Autorização reserva integralmente o solicitado, mas não baixa físico. | Service + movimentação de reserva. | Reservado aumenta pelo total solicitado/autorizado; físico mantém. | Crit. 2.2 |
| EST-03 | Estoque | Atendimento a partir de `pronta_para_retirada` consome reserva e baixa físico. | Service transacional. | Atendimento total/parcial reduz físico do entregue e consome/libera reserva. | Crit. 3.2 |
| EST-04 | Estoque | Reserva não entregue deve ser liberada. | Service transacional. | Atendimento parcial finalizado como `atendida` libera reserva não entregue; cancelamento antes da retirada libera toda reserva. | Crit. 3.3 |
| EST-05 | Estoque | Não pode reservar acima do disponível. | Recalcular dentro do lock. | Bloqueio e concorrência entre autorizações. | Crit. 2.8-2.10 |
| EST-06 | Estoque | Operações críticas usam transação e lock. | `atomic()`, `select_for_update()`, locks determinísticos. | Teste PostgreSQL de concorrência/idempotência. | CodeRabbit |
| EST-07 | Estoque | Divergência crítica: físico < reservado. | Marcador/recalculo no service. | Importação reduz físico e marca divergência. | Crit. 7.3 |
| EST-08 | Estoque | Material divergente bloqueia novas requisições e autorizações. | Policy/service. | Bloquear criação e autorização. | Crit. 1.5, 2.11 |
| EST-09 | Estoque | Divergência resolve quando físico >= reservado. | Recalcular após operação/importação. | Remover alerta e liberar se houver disponível. | Crit. 7.4 |
| EST-10 | Estoque | Material inativo não entra em nova requisição. | Queryset/service. | Bloquear seleção; histórico preservado. | Crit. 7.1 |
| EST-11 | Estoque | Material só inativa com físico e reservado zerados. | Service/policy. | Permitir zerado; bloquear com saldo. | Crit. 7.5-7.6 |
| SAE-01 | Saída excepcional | Saída excepcional é fluxo próprio de estoque, fora de Requisição. | App/URLs/policies próprios em `estoque`. | Rotas em `/estoque/saidas-excepcionais/`; não usar `requisicoes`. | `docs/processos-saida-excepcional.md` |
| SAE-02 | Saída excepcional | Número público segue `SXP-AAAA-NNNNNN` com contador anual próprio. | Model/service transacional. | Registro emite número uma vez; estorno não cria novo número. | `docs/processos-saida-excepcional.md` |
| SAE-03 | Saída excepcional | Documento exige ao menos 1 linha por material, sem duplicidade no mesmo documento. | Form/service/constraint. | Rejeitar material repetido; rejeitar documento vazio. | `docs/processos-saida-excepcional.md` |
| SAE-04 | Saída excepcional | Registro é indivisível e all-or-nothing. | `transaction.atomic()` + lock determinístico. | Se 1 item falha, nada é persistido nem numerado. | `docs/processos-saida-excepcional.md` |
| SAE-05 | Saída excepcional | Registro baixa `saldo_fisico` e não altera `saldo_reservado`. | Service transacional. | Saldo físico reduzido; reserva intacta. | `docs/processos-saida-excepcional.md` |
| SAE-06 | Saída excepcional | Saldo aplicável é único; ausência ou ambiguidade bloqueia o documento. | Selector/service. | `saldo_nao_encontrado` ou `saldo_ambiguo`. | `docs/processos-saida-excepcional.md` |
| SAE-07 | Saída excepcional | Estorno é total only e recompõe integralmente o `saldo_fisico`. | Service transacional. | Sem estorno parcial; documento estornado preservado. | `docs/processos-saida-excepcional.md` |
| SAE-08 | Saída excepcional | Consulta é mais ampla que mutação. | Policy/view/service. | Chefe/auxiliar/superuser consultam; só chefe ou override técnico registra/estorna. | `docs/processos-saida-excepcional.md` |
| SAE-09 | Saída excepcional | Motivos do MVP são fechados e observação é obrigatória. | Form/service. | Rejeitar motivo fora do enum e observação vazia. | `docs/processos-saida-excepcional.md` |

## 4. Notas por tema

- **Usuários/setores/papéis:** dados cadastrais definem escopo; permissões completas ficam em `matriz-permissoes.md`.
- **Requisições/itens:** estados e transições ficam em `estado-transicoes-requisicao.md`; este arquivo lista invariantes que não podem ser contornados.
- **Estoque:** qualquer mutação de saldo/reserva é transacional, auditável e recalcula disponibilidade no ponto crítico.
- **Saída excepcional:** fluxo próprio de estoque; detalhes de ciclo, número, permissões e front-end ficam em `processos-saida-excepcional.md`.

## 5. Checklist para PRs

- O PR altera invariante, permissão, status, saldo, reserva, auditoria ou contrato?
- O PR altera o fluxo de Saída excepcional? Se sim, conferiu `processos-saida-excepcional.md`, `matriz-permissoes.md` e o ADR novo?
- A documentação rápida e completa afetada foi atualizada?
- Há testes de caminho feliz, permissão negada e violação de domínio?
- Há teste PostgreSQL quando envolve estoque/reserva/concorrência?
