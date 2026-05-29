# Matriz de Permissões — WMS-SAEP

## 1. Objetivo

Referência rápida de papéis, escopos e ações permitidas para implementar `policies.py`, services, testes.

## 2. Princípios

- Todo usuário ativo é solicitante por padrão.
- Autorização contextual fica em policy compartilhada por views e services.
- Services revalidam autorização em toda escrita.
- `permission_classes` não substitui validação por objeto, setor, papel ou estado.
- Superusuário tem permissões totais, incluindo administração técnica, consulta ampla e operações de negócio/estoque.

## 3. Papéis e conceitos

| Papel | Técnico sugerido | Escopo | Permite | Bloqueia |
|---|---|---|---|---|
| Solicitante | `solicitante` | Próprio usuário como criador/beneficiário | Criar para si; ver próprias requisições; agir nos estados permitidos se for criador/beneficiário | Terceiros, estoque, autorização, relatórios gerais |
| Auxiliar de setor | `auxiliar_setor` | Próprio setor | Criar em nome de funcionários do próprio setor | Outros setores, autorização, estoque |
| Chefe de setor | `chefe_setor` | Setor sob responsabilidade | Criar para o próprio setor; ver/autorizar/recusar requisições do setor | Outros setores, estoque, rascunhos de terceiros |
| Auxiliar de Almoxarifado | `auxiliar_almoxarifado` | Todos os setores na operação de Almoxarifado | Criar para qualquer funcionário; ver todos; atender; devolver; consultar saídas excepcionais | Autorizar; registrar saída excepcional; estornar saída excepcional |
| Chefe de Almoxarifado | `chefe_almoxarifado` | Todos os setores para operação; setor Almoxarifado para autorização | Herda auxiliar; consultar/registrar saída excepcional; estornar; inativação permitida; histórico importações | Autorizar outros setores; ajuste manual |
| Superusuário | `superuser` | Superuser | Tudo | Nada |

Conceitos de escopo:

| Conceito | Regra |
|---|---|
| Criador | Usuário que registrou a requisição; pode agir nos estados permitidos. |
| Beneficiário | Funcionário que receberá material; pode agir nos estados permitidos. |
| Setor do beneficiário | Define setor da requisição e fila de autorização; nunca usar setor do criador. |
| Chefe autorizador | Chefe do setor do beneficiário; chefe de Almoxarifado só autoriza setor Almoxarifado. |
| Saída excepcional | Documento de estoque próprio, sem beneficiário/destinatário/setor de destino; consulta é mais ampla que mutação. |

## 4. Matriz geral

Valores: **Sim**, **Não**, **Apenas próprio setor**, **Qualquer setor**, **Apenas suporte/admin**, **Fora do MVP**.

| Ação | Solicitante | Aux. setor | Chefe setor | Aux. Almox. | Chefe Almox. | Superusuário | Observações |
|---|---|---|---|---|---|---|---|
| Autenticar por matrícula | Sim | Sim | Sim | Sim | Sim | Sim | Usuário inativo não acessa. |
| Acessar como usuário ativo | Sim | Sim | Sim | Sim | Sim | Sim | Pré-condição geral. |
| Gerenciar usuários | Não | Não | Não | Não | Não | Sim | Administração técnica. |
| Gerenciar setores | Não | Não | Não | Não | Não | Sim | Setor exige chefe. |
| Gerenciar papéis | Não | Não | Não | Não | Não | Sim | Perfis e configurações. |
| Criar requisição para si | Sim | Sim | Sim | Sim | Sim | Sim | Superusuário tem permissão total. |
| Criar para funcionário do próprio setor | Não | Apenas próprio setor | Apenas próprio setor | Qualquer setor | Qualquer setor | Sim | Setor da requisição = setor do beneficiário. |
| Criar para funcionário de outro setor | Não | Não | Não | Qualquer setor | Qualquer setor | Sim | Almoxarifado pode criar para qualquer funcionário. |
| Ver próprias requisições como criador | Sim | Sim | Sim | Sim | Sim | Sim |  |
| Ver próprias requisições como beneficiário | Sim | Sim | Sim | Sim | Sim | Sim | Exceto rascunho criado por terceiro. |
| Ver requisições do setor | Não | Não | Apenas próprio setor | Qualquer setor | Qualquer setor | Sim | Chefe vê setor sob responsabilidade; rascunho de terceiro segue creator-only. |
| Ver todos os setores | Não | Não | Não | Sim | Sim | Sim | Operação de Almoxarifado/suporte; rascunho de terceiro segue creator-only. |
| Editar rascunho | Sim | Sim | Sim | Sim | Sim | Sim | Só criador. |
| Enviar para autorização | Sim | Sim | Sim | Sim | Sim | Sim | Só criador. |
| Retornar para rascunho | Sim | Sim | Sim | Sim | Sim | Sim | Criador ou beneficiário enquanto ainda estiver em `aguardando_autorizacao`; depois do retorno, rascunho volta a ser creator-only. |
| Cancelar aguardando autorização | Sim | Sim | Sim | Sim | Sim | Sim | Só criador ou beneficiário. |
| Cancelar autorizada/pronta para retirada | Sim | Sim | Sim | Sim | Sim | Sim | Criador/beneficiário/Almoxarifado; justificativa; libera reserva e não baixa físico. |
| Copiar atendida ou recusada | Sim | Sim | Sim | Sim | Sim | Sim | Precisa ver origem e poder criar para beneficiário resultante; não copia autorizado/entregue. |
| Ver fila de autorizações | Não | Não | Apenas próprio setor | Não | Apenas setor Almoxarifado | Sim |  |
| Autorizar | Não | Não | Apenas próprio setor | Não | Apenas setor Almoxarifado | Sim | Setor do beneficiário define autorizador. |
| Autorizar parcialmente | Não | Não | Não | Não | Não | Não | Não permitido; chefe autoriza integralmente ou recusa a requisição inteira. |
| Recusar | Não | Não | Apenas próprio setor | Não | Apenas setor Almoxarifado | Sim | Recusa inteira; motivo obrigatório. |
| Autorizar outro setor | Não | Não | Não | Não | Não | Sim | Superusuário tem permissão total; Almoxarifado não autoriza outros setores. |
| Ver fila de atendimento | Não | Não | Não | Sim | Sim | Sim | Requisições nos estados `autorizada` e `pronta_para_retirada`. |
| Separar para retirada | Não | Não | Não | Sim | Sim | Sim | Transiciona de `autorizada` para `pronta_para_retirada`; mantém reserva e não baixa físico. |
| Registrar atendimento parcial | Não | Não | Não | Sim | Sim | Sim | Só a partir de `pronta_para_retirada`; exige justificativa por item menor/zero; finaliza como `atendida`. |
| Registrar atendimento total | Não | Não | Não | Sim | Sim | Sim | Só a partir de `pronta_para_retirada`; registra retirante físico; transiciona para `atendida`; baixa físico e consome reserva. |
| Cancelar por falta operacional antes da retirada | Não | Não | Não | Sim | Sim | Sim | Permitido em `autorizada` ou `pronta_para_retirada`; também possível ao criador/beneficiário; exige justificativa. |
| Liberar reserva não entregue | Não | Não | Não | Sim | Sim | Sim | Efeito automático de atendimento parcial ou cancelamento antes da retirada final. |
| Buscar materiais para requisição | Sim | Sim | Sim | Sim | Sim | Sim | Seleção bloqueia inativo, sem saldo ou divergente. |
| Consultar materiais | Sim | Sim | Sim | Sim | Sim | Sim | Histórico amplo segue escopo de relatório. |
| Editar observação interna do material | Não | Não | Não | Sim | Sim | Sim | Único campo textual editável localmente. |
| Inativar material | Não | Não | Não | Não | Sim | Sim | Exige físico e reservado zerados. |
| Operar movimentação de estoque | Não | Não | Não | Sim | Sim | Sim | Só por operação formal. |
| Ajustar estoque manualmente | Não | Não | Não | Não | Não | Não | Fora do MVP. |
| Consultar saídas excepcionais | Não | Não | Não | Sim | Sim | Sim | Lista e detalhe do documento. |
| Registrar saída excepcional | Não | Não | Não | Não | Sim | Sim (override técnico) | Documento próprio, número `SXP-AAAA-NNNNNN`, baixa física direta, motivo fechado e observação obrigatória. |
| Estornar saída excepcional | Não | Não | Não | Não | Sim | Sim (override técnico) | Estorno total only; justificativa obrigatória; não cria novo número. |
| Consultar histórico de movimentações | Não | Não | Não | Sim | Sim | Sim | Timeline da requisição segue visibilidade da requisição. |
| Registrar devolução | Não | Não | Não | Sim | Sim | Sim | Vinculada a requisição `atendida`. |
| Estornar requisição finalizada | Não | Não | Não | Não | Sim | Sim | Apenas chefe de Almoxarifado. |
| Estornar devolução | Não | Não | Não | Não | Sim | Sim | Exige saldo disponível suficiente. |
| Executar carga inicial técnica | Não | Não | Não | Não | Não | Sim | Piloto pode usar script/modo técnico. |
| Executar importação SCPI | Não | Não | Não | Não | Não | Sim | MVP: superusuário em fluxo técnico. |
| Pré-visualizar importação | Não | Não | Não | Não | Não | Sim | Sem persistência. |
| Confirmar importação com alertas | Não | Não | Não | Não | Não | Sim | Confirmação explícita. |
| Consultar histórico de importações | Não | Não | Não | Não | Sim | Sim | Chefe consulta; superusuário completo. |
| Consultar divergências críticas | Não | Não | Não | Sim | Sim | Sim | Gestão do Almoxarifado/suporte. |
| Receber notificações das próprias requisições | Sim | Sim | Sim | Sim | Sim | Sim | Criador e beneficiário. |
| Receber autorização pendente | Não | Não | Apenas próprio setor | Não | Apenas setor Almoxarifado | Sim | Quem pode autorizar/recusar. |
| Receber notificação de atendimento | Sim | Sim | Sim | Sim | Sim | Sim | Criador e beneficiário. |
| Acessar relatórios gerais | Não | Não | Não | Sim | Sim | Sim | Solicitante não acessa. |
| Acessar relatórios do próprio setor | Não | Não | Apenas próprio setor | Sim | Sim | Sim | Chefe de setor: consumo/requisições do setor. |
| Exportar CSV de relatórios | Não | Não | Apenas próprio setor | Sim | Sim | Sim | Respeita filtros e escopo. |
| Painel Gestão do Almoxarifado | Não | Não | Não | Não | Sim | Sim | Superusuário tem acesso completo; chefe de Almoxarifado acessa gestão operacional. |

## 5. Visibilidade

- Rascunho é visível e manipulável apenas pelo criador; ao sair de `rascunho`, o beneficiário passa a poder ver a requisição e perde esse acesso se ela voltar para `rascunho`.
- Fora de `rascunho`, criador e beneficiário veem a própria requisição e timeline completa.
- Chefe de setor vê requisições do setor sob sua responsabilidade, exceto rascunhos de terceiros.
- Almoxarifado vê requisições de todos os setores fora de rascunhos e vê a fila de atendimento (estados `autorizada` e `pronta_para_retirada`).
- Chefe de setor vê fila de autorização do próprio setor; chefe de Almoxarifado vê apenas setor Almoxarifado.
- Saídas excepcionais são consultáveis por chefe de Almoxarifado, auxiliar de Almoxarifado e superuser; registro e estorno ficam restritos ao chefe de Almoxarifado e ao override técnico do superuser.
- Relatórios gerais: Almoxarifado e suporte/admin. Chefe de setor: apenas relatórios do próprio setor.
- Superusuário vê todos os registros e pode executar ações administrativas, operacionais e de estoque.

## 6. Checklist de testes

- Caminho permitido por papel.
- Ação negada por papel.
- Ação negada por setor.
- Objeto fora do escopo.
- Usuário inativo.
- Superusuário permitido em ação técnica.
- Superusuário permitido em ação operacional.
- Policy chamada pela view e pelo service.
- `403 permission_denied` versus `404 not_found`.
- Requisição usando setor do beneficiário, não do criador.
- Relatórios/exportações respeitando filtros e escopo.

## 7. Pontos a confirmar

- Superfície da carga inicial SCPI: piloto pode usar script/modo técnico; MVP exige fluxo técnico controlado por superusuário.
- Detalhe de material deve explicitar se histórico de movimentações completo é visível a todos os autenticados ou só a papéis operacionais/admin.
