# ADR-0015 — Ledger de estoque por `MovimentacaoEstoque`

## Status

Aceita

## Contexto

`docs/estado-transicoes-requisicao.md` §6 afirma que a *entregue líquida* de um
item é "derivada das `MovimentacaoEstoque`, nunca armazenada". ADR-0002 já havia
nomeado `MovimentacaoEstoque` como a fonte de auditoria das mutações de estoque,
em vez de snapshots técnicos de `save()`. O model, porém, **não existia**.

Sem esse livro-razão não há como reconstruir o histórico de movimentações nem
calcular a entregue líquida com corretude. Devolução (TR-020) e estorno de
requisição (TR-021/TR-022) dependem dela: ambas operam sobre `quantidade > 0` e
`<= entregue líquida atual` do item, e o estorno total reverte a entregue
líquida atual — não a entregue bruta —, para não duplicar a contagem com
devoluções anteriores.

Hoje cinco services mutam `SaldoEstoque` diretamente e perdem o registro de
*quanto* cada evento moveu:

- `reservar_saldos_para_autorizacao` (+ reservado);
- `liberar_reservas_para_cancelamento` (− reservado);
- `consumir_e_liberar_reservas_para_atendimento` (− físico do entregue, −
  reservado do autorizado);
- `registrar_saida_excepcional` (− físico);
- `estornar_saida_excepcional` (+ físico).

Esta decisão introduz o ledger e faz o *retrofit* desses services **sem alterar
o comportamento de saldo**. As features TR-020/TR-021/TR-022 e qualquer UI estão
fora de escopo.

## Decisão

### 1. Linha = evento de domínio, com dois deltas assinados

`MovimentacaoEstoque` registra **uma linha por material afetado por evento de
domínio**, com duas colunas assinadas:

- `delta_fisico` — variação de `saldo_fisico`;
- `delta_reservado` — variação de `saldo_reservado`.

Ambos `DecimalField(max_digits=12, decimal_places=3, default=0)`, mesma precisão
de `SaldoEstoque`. São **variações assinadas**, não saldos absolutos — daí o
prefixo `delta_`.

O caso decisivo é `consumo`, que reduz `saldo_fisico` pela quantidade entregue e
`saldo_reservado` pela quantidade autorizada, valores que podem ser diferentes.
Uma única coluna de quantidade assinada não representaria isso. Com dois deltas,
um evento continua sendo uma linha e a reconciliação é independente por balde:

```text
Σ delta_fisico    por (estoque, material) = saldo_fisico
Σ delta_reservado por (estoque, material) = saldo_reservado
```

Não há linha agregada por documento: cada material tem deltas próprios.

### 2. Origem documental por duas FKs nuláveis

A origem é modelada por **duas FKs nuláveis explícitas**, `requisicao` e
`saida_excepcional`, ambas `on_delete=PROTECT`, com `CheckConstraint`
garantindo **exatamente uma** preenchida. O ator é ortogonal à origem e fica em
campo próprio (`ator`, FK `User`, `on_delete=PROTECT`, **obrigatório**).

`GenericForeignKey` foi rejeitado: não garante FK real no banco, enfraquece
`PROTECT`, dificulta constraints e contraria o estilo explícito do domínio
(ADR-0002). `tipo_documento` + `documento_id` em texto é ainda mais fraco — sem
integridade nem tipagem.

### 3. Granularidade por material; sem FK de item

O ledger é granular por **material**, identificando a linha do documento pela
chave natural `(origem, material)`. As constraints `unico_material_por_requisicao`
e `unico_material_por_saida_excepcional` garantem que material é único por
documento, então `(requisicao, material)` identifica univocamente o
`ItemRequisicao` e `(saida_excepcional, material)` a linha de saída.

Uma FK `item_requisicao` seria redundante, ficaria sempre nula para saída e
introduziria risco de inconsistência entre `requisicao`, `material` e item. Esta
decisão **depende da manutenção da invariante "material é único por documento"**;
se ela mudar, o ledger precisa ser reavaliado.

### 4. Tipos do movimento

`tipo` é um enum PT-BR (`TextChoices`) com sete valores:

| `tipo` | origem | `delta_fisico` | `delta_reservado` | fase |
|---|---|---|---|---|
| `reserva` | requisicao | 0 | > 0 | ativa |
| `liberacao` | requisicao | 0 | < 0 | ativa |
| `consumo` | requisicao | < 0 | < 0 | ativa |
| `saida_excepcional` | saida_excepcional | < 0 | 0 | ativa |
| `estorno_saida` | saida_excepcional | > 0 | 0 | ativa |
| `devolucao` | requisicao | > 0 | 0 | declarado, não emitido |
| `estorno_requisicao` | requisicao | > 0 | 0 | declarado, não emitido |

`devolucao` e `estorno_requisicao` são declarados agora mas **não emitidos**
nesta fase (TR-020/TR-021 fora de escopo). A constraint `tipo → origem` já os
cobre.

### 5. Constraints estruturais no banco; sinais nos services

O banco reforça apenas invariantes **estruturais**:

1. exatamente uma origem (`requisicao` XOR `saida_excepcional`);
2. pelo menos um delta diferente de zero;
3. coerência `tipo → origem` (os cinco tipos de requisição exigem `requisicao`;
   os dois de saída exigem `saida_excepcional`).

A matriz `tipo → sinal dos deltas` é **regra semântica de negócio**, centralizada
no helper/funções por tipo e coberta por testes — **não** em `CheckConstraint`.
Constraints por tipo seriam verbosas e frágeis (sete tipos, casos como `consumo`
com ambos os deltas negativos e possivelmente distintos) para ganho marginal,
ainda mais com tipos futuros no enum. Isso espelha `SaldoEstoque`, cujos checks
são estruturais (`>= 0`) enquanto a lógica de sinal vive nos services.

### 6. Escrita centralizada; saldo nunca muda sem movimentação

Toda linha é criada por um helper privado único em `apps/estoque/services.py`:

```text
_registrar_movimentacao(*, tipo, material_id, estoque_id,
                        delta_fisico, delta_reservado, origem, ator_id)
```

chamado **uma vez por material**, dentro do loop de mutação de saldo de cada
service, na **mesma `transaction.atomic`**. Regra de domínio: nenhum
`SaldoEstoque` é alterado por esses services sem a `MovimentacaoEstoque`
correspondente na mesma transação.

A origem é um value object explícito, e o helper aceita **apenas** o value
object — nunca FKs soltas:

```python
@dataclass(frozen=True)
class OrigemMovimentacaoEstoque:
    requisicao_id: int | None = None
    saida_excepcional_id: int | None = None
    # valida "exatamente uma origem" na construção

    @classmethod
    def de_requisicao(cls, requisicao) -> "OrigemMovimentacaoEstoque": ...
    @classmethod
    def de_saida_excepcional(cls, saida) -> "OrigemMovimentacaoEstoque": ...
```

Os services de requisição passam a receber `origem: OrigemMovimentacaoEstoque` e
`ator_id: int`. Os de saída montam a origem internamente a partir da
`SaidaExcepcional` criada ou estornada. Isso mantém "exatamente uma origem" fora
dos loops e reduz ambiguidade no call site.

### 7. Imutabilidade em app-level

O ledger é *append-only*. `MovimentacaoEstoque.save()` impede alteração de
instância já persistida e `delete()` impede exclusão, levantando uma exceção
**de guarda de invariante** (`MovimentacaoEstoqueImutavel`), **fora da árvore
`ErroDominio`** — violação de imutabilidade é erro de programação, não condição
de negócio user-facing, e não deve ser traduzida para HTTP por uma view.

Não se adota trigger no Postgres nesta fase: introduziria migration custom,
acoplamento ao banco e um padrão divergente do repo, que usa constraints
declarativas. Trigger fica como defesa-em-profundidade futura se houver requisito
de auditoria externa mais rígida.

### 8. Selector `entregue_liquida_por_item` — leitura pura, tipos explícitos

```text
entregue_liquida_por_item(requisicao_id, item_id) -> Decimal
```

Valida que `item_id` pertence à `requisicao_id` (senão `DadosInvalidos`),
resolve `item_id → material_id` e calcula:

```text
entregue_liquida = − Σ delta_fisico,
  filtrando por (requisicao_id, material_id) e
  tipo ∈ {consumo, devolucao, estorno_requisicao}
```

O conjunto de tipos é uma constante nomeada
(`TIPOS_MOVIMENTO_ENTREGA_LIQUIDA`). O filtro é **explícito**, não "somar todos
os `delta_fisico`": embora hoje `reserva`/`liberacao` tenham `delta_fisico = 0`,
isso é propriedade incidental dos tipos atuais; um tipo futuro ligado a
requisição que toque físico sem ser reversão de entrega quebraria a soma cega em
silêncio.

O selector é **leitura pura**: não faz `select_for_update`. Quem muda, trava —
o service mutante futuro (TR-020/TR-021) abre a transação e trava a `Requisicao`
(ADR-0005) envolvendo a chamada. O selector apenas lê o ledger.

## Consequências

A auditoria de cada mutação de saldo passa a ter representação de domínio
explícita, cumprindo ADR-0002. A entregue líquida deixa de ser derivável só na
teoria e passa a ter fonte real.

`SaldoEstoque` continua sendo a fonte de verdade do saldo corrente; o ledger é
histórico reconciliável, não substitui o saldo materializado. O comportamento de
saldo dos cinco services não muda — o retrofit só acrescenta a escrita do ledger
na mesma transação.

A ordem de locks do ADR-0005 é preservada: a movimentação é gravada dentro da
transação que já travou `Requisicao` e os `SaldoEstoque` afetados.

TR-020/TR-021/TR-022 ganham a fundação para operar sobre entregue líquida.

### Limitações desta fase

- `confirmar_importacao_scpi` cria `SaldoEstoque` inicial para material novo
  **fora** do ledger. Essa é uma lacuna de auditoria conhecida, **fora do
  escopo** da issue #39. Tratada por issue/ADR futura, possivelmente com tipo
  `importacao_scpi` e uma origem documental própria (lote de importação).
- Imutabilidade é garantida em app-level; `QuerySet.update()`/`.delete()` em
  massa podem burlá-la. Mitigado por ausência de UI/admin de edição, criação
  exclusiva pelo helper e testes/revisão garantindo que não há call site de
  update/delete sobre `MovimentacaoEstoque`.

## Trade-off

Auditar por ledger com dois deltas e origem explícita exige modelar e manter o
retrofit de cada service, em vez de inferir movimentação de snapshots técnicos.
Aceita-se esse custo em troca de histórico reconciliável, entregue líquida com
fonte real e integridade referencial forte.

Uma terceira origem de movimentação no futuro exigirá nova coluna e migration —
custo desejável, porque nova origem é mudança relevante de domínio e deve ser
modelada explicitamente, não absorvida por uma FK genérica.

## Emenda — 2026-06-26 (revisão de arquitetura)

> **Natureza desta emenda.** Registra **decisões** de arquitetura (estado-alvo),
> a serem implementadas pelas issues #48–#58; o código atual ainda **não** as
> reflete. Os trechos que descrevem o **problema atual** estão marcados. Onde a
> assinatura-alvo difere do código vigente, ambas aparecem.

**Problema atual.** Não existem comandos públicos de devolução/estorno no app de
estoque; por isso `requisicoes` muta o ledger **por fora** do boundary deste
ADR: importa o helper privado `_registrar_movimentacao`
(`apps/requisicoes/services.py:30`, chamado em `:1119` e `:1382`), trava
`SaldoEstoque.objects.select_for_update()` e monta as linhas à mão para
devolução e estorno. Três das cinco operações vão pela interface pública do
estoque; duas furam o encapsulamento. A invariante "saldo nunca muda sem
movimentação" passa a depender de o **chamador** lembrar de fazer as duas
coisas — a localidade que o ledger deveria garantir vaza.

### Toda mutação de saldo atrás de comandos de negócio completos

A interface pública do estoque é composta por **comandos de negócio**, não por
primitivas do ledger. Devolução e estorno de requisição viram comandos públicos
do estoque (ex.: `registrar_devolucao_estoque`, `estornar_requisicao_estoque`),
simétricos aos três existentes. Cada comando é **completo e atômico**: encapsula
movimentação + saldo + reservas numa transação; o chamador não participa nem
monta linhas. Com isso:

- `_registrar_movimentacao` volta a ser **estritamente privado** — sem import
  por `requisicoes`;
- `SaldoEstoque` e seu `select_for_update` **saem** de `requisicoes`;
- os verbos devem permanecer **capacidades do domínio de estoque** (origem pode
  ser Requisição **ou** Saída excepcional), não espelho do workflow de um único
  cliente.

`estorno_requisicao` (comando): aplica a movimentação inversa do consumo,
restaurando o `saldo_fisico` da **entregue líquida** atual do item e gerando
`MovimentacaoEstoque` de tipo `estorno_requisicao`.

### `entregue_liquida` por referência estável; sem import reverso

O selector vivia em `estoque` mas importava `requisicoes.models.ItemRequisicao`
para resolver `item → material` — a única aresta `estoque → requisicoes`. O
cálculo continua no estoque (dono do ledger), mas a interface recebe uma
**referência estável** `(requisicao_id, material_id)` como contrato público de
leitura (promover a tipo de referência frozen se um terceiro parâmetro surgir).
`requisicoes` resolve `item → material` **antes** de chamar. `estoque` deixa de
importar `requisicoes.models`: a dependência fica unidirecional `requisicoes →
estoque`.

**Estado atual vs. alvo.** Hoje o selector é
`entregue_liquida_por_item(*, requisicao_id, item_id)` e **ainda importa**
`apps.requisicoes.models.ItemRequisicao` para resolver o material — a aresta
reversa `estoque → requisicoes` **persiste**. O alvo acima
(`(requisicao_id, material_id)`, sem import reverso) é **pendente** (issue #50);
até a implementação, código e este contrato divergem conscientemente.

### Tipos do seam = contrato explícito + factory

Os tipos que cruzam o seam (ex.: o `TypedDict ItemAtendimentoSaldo`, hoje passado
por estrutura) viram **contrato explícito** (`estoque/types.py`) com value
objects, mantendo o padrão `OrigemMovimentacaoEstoque.de_requisicao(...)`.
`requisicoes` não importa símbolos privados nem tipos internos do estoque.

O bootstrap de `confirmar_importacao_scpi` segue fora do ledger (lacuna já
registrada nas Limitações).
