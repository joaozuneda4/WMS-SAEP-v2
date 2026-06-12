# WMS-SAEP

Contexto único de gestão do almoxarifado da SAEP: cobre requisições de
material, autorização, atendimento e controle de estoque. Este arquivo é o
glossário de domínio — sem detalhes de implementação.

## Language

### Organização e papéis

**Usuário**:
Pessoa com acesso ao sistema; pertence a exatamente um Setor.
_Avoid_: funcionário, colaborador

**Setor**:
Unidade organizacional da SAEP à qual um Usuário pertence.

**Almoxarifado**:
O Setor responsável pela guarda e entrega de materiais; é um Setor com
classificação própria, não uma entidade à parte.

**Chefe de setor**:
Usuário responsável por um Setor; autoriza ou recusa as requisições desse
Setor. Papel derivado de ser o chefe daquele Setor, não um atributo fixo do
Usuário.
_Avoid_: gerente, responsável

**Auxiliar de setor**:
Usuário com vínculo de apoio a um Setor, habilitado a criar requisições em
nome de outros Usuários do mesmo Setor.

**Chefe de Almoxarifado**:
O Chefe do Setor Almoxarifado; único papel autorizado a estornar e a
registrar saída excepcional.

**Auxiliar de Almoxarifado**:
Usuário com vínculo de apoio ao Setor Almoxarifado; executa separação,
atendimento e devolução.

**Solicitante**:
Condição implícita de todo Usuário ativo, capaz de criar requisições para si
mesmo; não é um papel atribuído.
_Avoid_: requerente

**Papel efetivo**:
O papel que um ator exerce diante de um Setor ou requisição específicos,
calculado a partir do ator e do contexto — nunca um atributo fixo do Usuário.

### Atores da requisição

**Criador**:
Usuário que registrou a requisição.

**Beneficiário**:
Usuário que receberá o material; define o Setor da requisição e a fila de
autorização.
_Avoid_: destinatário, solicitante

**Retirante**:
Pessoa que coleta fisicamente o material no momento do atendimento; pode não
ser o Beneficiário.

**Saída excepcional**:
Baixa administrativa de material fora do ciclo de uma Requisição. Nasce já
registrada, tem documento próprio, número público próprio e trilha de
auditoria própria. Movimenta o saldo físico diretamente e só pode ser
revertida por estorno explícito do mesmo documento.

**Número público da saída excepcional**:
Identificador anual próprio da saída excepcional, no formato `SXP-AAAA-
NNNNNN`, emitido no registro e imutável depois disso.

**Estado da saída excepcional**:
`registrada` ou `estornada`. O documento nasce registrado e só muda para
estornada por estorno explícito.

**Evento da saída excepcional**:
`registro` ou `estorno`. Evento de timeline não é estado.

**Item da saída excepcional**:
Cada material aparece uma única vez por documento; a quantidade da linha é
canônica e não deve ser somada silenciosamente com duplicatas.

**Importação SCPI**:
Carga inicial de estoque vinda do SCPI, em CSV normalizado antes da leitura.
WMS é a fonte da verdade do saldo. Não sobrescreve saldo; registra alertas de
divergência para ajuste manual posterior no SCPI.
`CADPRO` do arquivo SCPI corresponde ao `codigo` de **Material**.
Material novo pode nascer da própria importação SCPI.
Quando o material é novo, o `SaldoEstoque` do estoque principal nasce com a
quantidade trazida pelo SCPI.

**Alerta de importação**:
Aviso não bloqueante identificado no preview da importação SCPI. Alerta não
impede o processamento, mas exige confirmação explícita antes de gravar o
ajuste.

**Pré-visualização de importação SCPI**:
Leitura do CSV normalizado antes de qualquer persistência. Mostra diagnóstico
e impacto estimado, mas não altera estoque nem grava ajuste.

**Histórico de importação SCPI**:
Registro só de metadados da importação: arquivo, hash, usuário, data/hora,
status, contagens e resumo. Não guarda snapshot do preview nem do conteúdo
importado.

**Divergência SCPI**:
Diferença entre a quantidade do arquivo SCPI e o `saldo_fisico` atual do
WMS para o mesmo `CADPRO`. O preview mostra o delta para permitir
conferência antes de confirmar a importação.

**Resumo de importação SCPI**:
Resumo textual mínimo do resultado da importação: quantos materiais novos
foram criados, quantas linhas divergiram e quantos alertas foram gerados.

### Quantidades

**Entregue líquida**:
A parte de um item já entregue que ainda permanece fora do estoque — a
quantidade entregue menos o que voltou por **Devolução** ou **Estorno**.
Nunca armazenada; derivada das **Movimentações de estoque** do item.

### Estoque

**Movimentação de estoque**:
Registro imutável (livro-razão append-only) de cada variação de saldo de um
material num estoque, causada por um evento de domínio. Carrega duas variações
assinadas — uma do saldo físico, outra do saldo reservado — e aponta para o
documento de origem (uma **Requisição** ou uma **Saída excepcional**). É a fonte
de auditoria do estoque e a base de cálculo da **Entregue líquida**. Nunca
substitui o saldo corrente, que continua materializado.
_Avoid_: histórico técnico, snapshot de saldo.

**Tipo de movimentação**:
A natureza do evento que gerou a movimentação: `reserva`, `liberacao`,
`consumo`, `saida_excepcional`, `estorno_saida`, `devolucao` ou
`estorno_requisicao`. O tipo determina qual documento de origem é válido e o
sinal esperado das variações.

## Relationships

- Cada **Usuário** pertence a exatamente um **Setor**.
- Cada **Setor** tem exatamente um **Chefe de setor**.
- Um **Chefe de setor** responde por no máximo um **Setor**.
- O **Almoxarifado** é um **Setor**.
- Um **Auxiliar de setor** tem vínculo ativo com um **Setor**; o vínculo pode
  ser desativado.
- Uma requisição pertence ao **Setor** do **Beneficiário**, nunca ao do
  **Criador**.
- O **Chefe de setor** autorizador de uma requisição é o chefe do **Setor do
  Beneficiário**.
- **Saída excepcional** é independente do ciclo de vida de **Requisição** e
  não usa reserva, autorização de setor, separação nem atendimento.
- **Importação SCPI** é um fluxo de estoque próprio, fora de **Requisição**,
  e altera o estoque por ajuste auditável, não por escrita direta de saldo.
- Reimportação exata da mesma carga SCPI deve ser bloqueada.
- `Confirmar importação com alertas` significa assumir conscientemente os
  alertas de preview e persistir o ajuste.
- `Pré-visualizar importação` é sempre read-only.
- O histórico da importação guarda só metadados.
- O campo `CADPRO` da carga SCPI identifica unicamente o `Material`.
- Importação SCPI pode criar **Material** novo quando o código ainda não
  existir no catálogo.
- Material novo importado já recebe `SaldoEstoque` inicial igual à quantidade
  do SCPI no estoque principal.
- O preview da importação compara `CADPRO` x `saldo_fisico` e evidencia
  divergências por delta.
- Divergência SCPI gera alerta; nunca altera `saldo_fisico`.
- O resumo da importação informa criação de materiais, divergências e
  alertas.
- **Doação** e **empréstimo** são fluxos distintos de estoque, com regras
  próprias, e não fazem parte do MVP de **Saída excepcional**.
- O estado da **Saída excepcional** não se confunde com seus eventos de
  auditoria: estado é `registrada`/`estornada`; evento é `registro`/`estorno`.
- Cada **Saída excepcional** aceita uma única linha por **Material**; se o
  material repetir no input, o documento deve ser rejeitado.
- O vocabulário canônico da feature usa `SaidaExcepcional`,
  `ItemSaidaExcepcional`, `SequenciaSaidaExcepcional`,
  `registrar_saida_excepcional` e `estornar_saida_excepcional`.
- A feature pertence ao app **estoque**, não ao app **requisicoes**.
- Toda mutação de saldo feita pelos services de estoque gera a **Movimentação
  de estoque** correspondente na mesma transação; saldo nunca muda sem ela.
- Cada **Movimentação de estoque** tem exatamente uma origem: ou uma
  **Requisição**, ou uma **Saída excepcional**, nunca as duas.
- A **Entregue líquida** de um item é `Σ` das **Movimentações de estoque** de
  tipo `consumo`, `devolucao` e `estorno_requisicao` daquele item, calculada
  dentro da transação que trava a **Requisição** (ADR-0005).
- **Material é único por documento** (requisição ou saída): essa unicidade é o
  que permite identificar a linha pela origem mais o material, sem referência
  direta ao item.

## Example dialogue

> **Dev:** "O Usuário tem um campo que diz se ele é chefe de setor?"
> **Especialista:** "Não. Ele é chefe porque é o chefe de um Setor. Se você
> tirar ele da chefia daquele Setor, ele deixa de ser chefe — não tem o que
> atualizar no cadastro dele."
> **Dev:** "E se o Almoxarifado cria uma requisição para alguém de Obras,
> quem autoriza?"
> **Especialista:** "O chefe de Obras. A requisição é do Setor de quem
> recebe, não de quem digitou."

## Flagged ambiguities

- "Papel" era usado para conceitos heterogêneos (default implícito, vínculo
  de setor, chefia derivada, flag técnica). Resolvido: papel não é campo único
  no Usuário — **Solicitante** é implícito, **Auxiliar de setor** é vínculo
  explícito, **Chefe de setor** é derivado da chefia do Setor; superusuário é
  apenas a flag técnica do Django, fora do domínio.
- "Solicitante", "Criador" e "Beneficiário" eram usados de forma
  intercambiável. Resolvido: são distintos — Solicitante é a capacidade
  implícita, Criador é quem registrou, Beneficiário é quem recebe.
- "Almoxarifado" designava tanto um Setor quanto um escopo operacional.
  Resolvido: é um Setor classificado como almoxarifado; os papéis de
  almoxarifado derivam dele.
