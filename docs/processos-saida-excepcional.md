# 1. Processo de Saída Excepcional de Estoque

## 1.1 Objetivo

Descrever o fluxo próprio de **Saída excepcional** do WMS-SAEP: documento
administrativo de baixa física direta, independente de **Requisição**, com
documento próprio, numeração própria, auditoria própria e estorno total
explícito.

## 1.2 Escopo

A Saída excepcional:

- pertence ao app **estoque**;
- usa URLs próprias sob `/estoque/saidas-excepcionais/`;
- não nasce de Requisição;
- não gera reserva;
- não participa dos estados de Requisição;
- não tem rascunho;
- não tem destinatário externo, setor de destino, beneficiário ou retirante;
- não aceita estorno parcial no MVP;
- não mistura múltiplos estoques no mesmo documento;
- não cobre doação, empréstimo, transferência, inventário formal ou estorno
  de Requisição.

Fluxos fora do escopo do MVP e que exigem especificação própria:

- doação de material;
- empréstimo de material;
- transferência entre estoques;
- inventário formal;
- estorno de requisição.

## 1.3 Conceitos de domínio

**Saída excepcional**  
Documento de baixa administrativa que reduz `saldo_fisico` diretamente.

**Número público da saída excepcional**  
Identificador anual próprio no formato `SXP-AAAA-NNNNNN`. É emitido no
registro, nunca no rascunho porque não há rascunho, e permanece imutável.

**Estado da saída excepcional**  
`registrada` ou `estornada`.

**Evento da saída excepcional**  
`registro` ou `estorno`. Evento de auditoria não é estado.

**Item da saída excepcional**  
Linha canônica do documento. Cada material aparece uma única vez por
documento, com uma quantidade associada.

**Estoque principal**  
Saldo único aplicável para o material na operação. O sistema resolve o saldo
e falha se não encontrar saldo ou se houver ambiguidade.

## 1.4 Ciclo de vida

O ciclo de vida é mínimo:

1. **Registrada**
   - Documento criado e persistido em uma transação única.
   - Número público gerado no momento do registro.
   - `saldo_fisico` é baixado diretamente.
   - `saldo_reservado` não muda.
   - O documento é auditável e consultável.

2. **Estornada**
   - O documento original é preservado.
   - O estorno recompõe integralmente o `saldo_fisico` dos itens baixados.
   - O estorno é total; não existe estorno parcial no MVP.
   - O registro original continua visível na auditoria.

Regra operacional:

- a operação é **all-or-nothing**;
- se 1 item falhar, o documento inteiro falha;
- não existe número público, documento, item, timeline ou baixa parcial
  quando o registro falha;
- a sequência anual só avança dentro da mesma transação do registro.

## 1.5 Itens e validações

Regras dos itens:

- o documento precisa ter ao menos 1 item;
- cada item referencia `Material` e `quantidade`;
- `quantidade` deve ser decimal finito e maior que zero;
- o mesmo `Material` não pode aparecer duas vezes no mesmo documento;
- o service rejeita duplicidade com erro de domínio;
- o form pode antecipar a validação, mas o service e o banco continuam sendo
  a fonte final;
- a UI deve permitir conferência item a item antes do registro.

Campos de cabeçalho:

- `motivo` obrigatório, via enum fechado;
- `observacao` obrigatória, curta e textual;
- `observacao` não substitui `motivo` e não pode ser vazia;
- no MVP, a observação deve ter tamanho controlado pelo form/service.

Regras de saldo:

- o sistema resolve o saldo aplicável por material;
- se não existir saldo elegível, falha com `saldo_nao_encontrado`;
- se houver mais de um saldo elegível, falha com `saldo_ambiguo`;
- o registro baixa somente `saldo_fisico`;
- o registro não altera `saldo_reservado`;
- o estorno recompõe integralmente o `saldo_fisico` dos itens originais;
- o estorno não gera novo documento numerado.

## 1.6 Permissões

Consulta:

- chefe de Almoxarifado;
- auxiliar de Almoxarifado;
- superuser ativo.

Registro e estorno:

- chefe de Almoxarifado;
- superuser apenas como override técnico nas policies.

O auxiliar de Almoxarifado pode consultar, mas não registrar nem estornar.

## 1.7 Número público

O número público usa o padrão:

`SXP-AAAA-NNNNNN`

Exemplo:

`SXP-2026-000001`

Regras:

- sequência própria por ano;
- contador próprio, independente de `SequenciaRequisicao`;
- emissão somente no registro efetivo;
- número imutável depois do registro;
- estorno não gera novo número;
- a sequência só avança em transação bem-sucedida.

## 1.8 Front-end

A Saída excepcional usa o mesmo shell autenticado do restante do sistema:

- `base_auth.html`;
- topbar/drawer existente;
- mesmo tom visual de Requisições;
- sem shell próprio de estoque no MVP.

Navegação:

- o drawer deve ter grupo `Almoxarifado` separado de `Requisições`;
- `Almoxarifado` contém `Atendimento` e `Saídas excepcionais`;
- o link de `Saídas excepcionais` aponta para a lista da feature;
- a rota pós-login de Almoxarifado continua sendo a fila de atendimento.

Tela de lista:

- tabela no desktop;
- cards empilhados no mobile;
- ordenação padrão por mais recente primeiro;
- sem filtros no MVP;
- empty state com CTA `Nova saída excepcional` apenas para quem pode registrar.

Tela de novo registro:

- formulário em 2 blocos: `Dados da saída` e `Materiais`;
- autocomplete inline reaproveitando a UI já existente na tela de nova
  Requisição, mas com fonte de dados e regra de elegibilidade do contexto de
  Saída excepcional;
- quantidade por item visível na linha/card;
- o botão primário deve ser `Registrar saída excepcional`.

Tela de detalhe:

- mostra número público, estado, motivo, observação, estoque afetado,
  total de itens, itens item a item, timeline e dados de estorno;
- botão `Estornar` aparece apenas no detalhe, apenas quando o documento está
  `registrada` e o usuário pode estornar;
- confirmação de estorno via modal simples com justificativa obrigatória.
- badge de `Registrada` deve ser informativo/azul;
- badge de `Estornada` deve usar semântica de reversão/teal se houver classe
  equivalente; não criar paleta nova para isso.

Requisitos de acessibilidade (ver `.design/saida-excepcional/DESIGN_BRIEF.md`):

- contraste mínimo WCAG AA em textos, badges e botões;
- todo input deve ter `<label>` explícito;
- modal de estorno precisa de `role="dialog"`, `aria-modal="true"`, trap de foco e restauração do foco ao fechar;
- a lista precisa ser navegável por teclado e manter o link de detalhe acessível;
- o estado precisa ter label textual além da cor;
- o autocomplete precisa ser utilizável por teclado, com navegação por setas e confirmação da seleção;
- o botão de ação destrutiva deve deixar explícito o impacto da operação.

## 1.9 Estrutura canônica

Nomes canônicos da feature:

- `SaidaExcepcional`
- `ItemSaidaExcepcional`
- `SequenciaSaidaExcepcional`
- `registrar_saida_excepcional`
- `estornar_saida_excepcional`

Motivos fechados do MVP:

- `perda_extravio`
- `quebra_dano`
- `consumo_interno`
- `ajuste_operacional`

Observação:

- a observação explica o caso concreto;
- a observação não é livre sem validação;
- a observação acompanha o documento e o estorno, quando houver.

## 1.10 Fora do escopo do MVP

- estorno parcial;
- múltiplos estoques no mesmo documento;
- destinatário externo;
- setor de destino;
- beneficiário;
- retirante;
- doação;
- empréstimo;
- transferência;
- inventário formal;
- tela própria de shell;
- filtros na lista;
- duplicar documento;
- excluir fisicamente o documento;
- editar motivo, observação ou itens após registro.

## 1.11 Checklist de testes

- consulta permitida para os papéis corretos;
- registro negado para auxiliar e papéis sem permissão;
- estorno negado para auxiliar e papéis sem permissão;
- número público emitido apenas em registro bem-sucedido;
- falha de 1 item derruba o documento inteiro;
- material duplicado no input rejeita o documento;
- saldo ausente ou ambíguo rejeita o documento;
- registro baixa apenas `saldo_fisico`;
- estorno recompõe integralmente o `saldo_fisico`;
- documento estornado não pode ser estornado novamente.

## 1.12 Referências

- `docs/adr/0013-saida-excepcional-fluxo-proprio-estoque.md`
- `docs/matriz-permissoes.md`
- `docs/matriz-invariantes.md`
- `docs/CONVENTIONS.md`
- `CONTEXT.md`
