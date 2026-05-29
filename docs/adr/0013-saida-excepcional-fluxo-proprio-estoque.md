# ADR-0013 — Saída excepcional como fluxo próprio de estoque

**Status**: Aceita

**Data**: 2026-05-29

**Decisores**: João

## Contexto

O sistema já possui um fluxo consolidado de **Requisição** com autorização,
reserva, separação, atendimento, cancelamento e estorno. Durante a
especificação do backlog surgiu uma necessidade diferente: registrar baixas
administrativas diretas de estoque sem passar por Requisição, sem reserva,
sem beneficiário, sem destinatário e sem trilha de estados da requisição.

As alternativas eram:

1. modelar a operação como uma variação de Requisição;
2. tratá-la como um tipo genérico de movimentação de estoque sem documento
   próprio;
3. criar um fluxo próprio de estoque, com documento, numeração, políticas e
   auditoria separados.

As opções 1 e 2 pareciam mais econômicas no início, mas criariam ambiguidade
com atendimento, cancelamento, doação, empréstimo, transferência e inventário
formal. A operação precisa ser auditável, indivisível e reversível apenas por
estorno total explícito.

## Decisão

Adotar **Saída excepcional** como um fluxo próprio do app `estoque`, com
documento e ciclo de vida independentes de `Requisição`.

Características obrigatórias:

- documento próprio: `SaidaExcepcional`;
- item próprio: `ItemSaidaExcepcional`;
- sequência própria: `SequenciaSaidaExcepcional`;
- service próprio para registrar e estornar;
- URL própria sob `/estoque/saidas-excepcionais/`;
- numeração própria anual no formato `SXP-AAAA-NNNNNN`;
- ciclo mínimo `registrada -> estornada`;
- cabeçalho com motivo fechado e observação obrigatória;
- registro transacional e all-or-nothing;
- baixa direta de `saldo_fisico`;
- sem alteração de `saldo_reservado`;
- estorno total only no MVP;
- estorno com justificativa obrigatória;
- sem destinatário externo, setor de destino, beneficiário ou retirante;
- consulta mais ampla que mutação, mas mutação restrita ao chefe de
  Almoxarifado com override técnico do superuser;
- front-end compartilhado com o mesmo `base_auth.html` e topbar/drawer do
  restante do sistema.

Também foi decidido que doação, empréstimo, transferência e inventário formal
não serão “encaixados” como Saída excepcional. Esses fluxos exigem
especificação própria quando forem priorizados.

## Consequências

### Positivas

1. **Fronteira clara de domínio**: Requisição continua sendo pedido e
   autorização; Saída excepcional vira baixa administrativa direta.
2. **Auditoria simples**: documento único, número próprio, timeline própria e
   estorno total explícito.
3. **Menos ambiguidade operacional**: não há risco de confundir baixa direta
   com atendimento, cancelamento ou transferência.
4. **Menos acoplamento**: o app `estoque` passa a ser o dono do fluxo sem
   invadir `requisicoes`.
5. **UI previsível**: o mesmo chrome do sistema pode acomodar a feature sem
   criar um shell paralelo.

### Negativas

1. **Mais modelos e services**: surgem cabeçalho, itens, sequência e políticas
   próprios.
2. **Mais documentação**: o fluxo precisa de processo, matriz de permissões e
   invariantes específicos.
3. **Mais implementação inicial**: um atalho por Requisição teria menos código
   hoje, mas com custo maior de ambiguidade amanhã.

### Trade-off

Aceitamos o custo adicional de um fluxo próprio em troca de um contrato de
domínio mais seguro, mais auditável e mais fácil de manter. A Saída
excepcional é um caso administrativo especial, não uma variação de
Requisição.

## Referências

- `docs/processos-saida-excepcional.md`
- `docs/matriz-permissoes.md`
- `docs/matriz-invariantes.md`
- `docs/CONVENTIONS.md`
- `CONTEXT.md`
