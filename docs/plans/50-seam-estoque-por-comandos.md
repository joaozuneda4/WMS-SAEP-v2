# Plano #50 — Seam de saldo por comandos de negócio; entregue_liquida por referência; quebra import reverso

## Escopo

**O que muda:**
- Novos comandos públicos `registrar_devolucao_estoque` e `estornar_requisicao_estoque` em `apps/estoque/services.py`
- `apps/estoque/types.py` criado com os TypedDicts do seam (`ItemReservaEstoque`, `ItemLiberacaoReserva`, `ItemAtendimentoSaldo`)
- `entregue_liquida_por_item` renomeado para `entregue_liquida_por_material` com assinatura `(*, requisicao_id, material_id)` — remove importação reversa de `requisicoes.models`
- `_registrar_atualizacao_estoque_relevante` movida de `estoque/services.py` para `requisicoes/services/ciclo_vida.py` como `registrar_timeline_divergencia_importacao` — remove a segunda importação reversa
- `requisicoes/services/atendimento.py` e `ciclo_vida.py` migrados para os novos comandos; removem `SaldoEstoque`, `TipoMovimentacaoEstoque` e `_registrar_movimentacao` diretos
- `confirmar_importacao_scpi` aceita `_pos_importacao_hook` (callable opcional, interno) e continua retornando apenas `ImportacaoSCPI` — linhas ficam encapsuladas no serviço
- VIEW `confirmar_importacao_scpi_view` passa `registrar_timeline_divergencia_importacao` como hook; não depende do retorno de linhas

**O que NÃO muda:**
- `OrigemMovimentacaoEstoque` permanece em `estoque/services.py`
- Comportamento de saldo, contratos de reserva/liberação/consumo
- `liberar_reservas_para_cancelamento` (já é comando público, cancelamento.py não precisa mudar)
- URL contracts, templates, forms

## Dependências atuais (o problema)

### Importações reversas `estoque → requisicoes` (bloqueadores)

| Arquivo | Símbolo | Importa de |
|---------|---------|-----------|
| `apps/estoque/selectors.py::entregue_liquida_por_item` | `ItemRequisicao` | `apps.requisicoes.models` |
| `apps/estoque/services.py::_registrar_atualizacao_estoque_relevante` | `EstadoRequisicao, EventoTimeline, ItemRequisicao, TimelineRequisicao` | `apps.requisicoes.models` |

### Importações de private `_registrar_movimentacao` por `requisicoes`

| Arquivo | Causa |
|---------|-------|
| `apps/requisicoes/services/atendimento.py::registrar_devolucao` | lock manual de `SaldoEstoque` + chamada direta |
| `apps/requisicoes/services/ciclo_vida.py::estornar_requisicao` | lock manual de `SaldoEstoque` + chamada direta |

## Arquivos alterados

| Arquivo | Tipo de mudança |
|---------|----------------|
| `apps/estoque/types.py` | CRIAR — TypedDicts do seam |
| `apps/estoque/selectors.py` | MODIFICAR — renomear `entregue_liquida_por_item` → `entregue_liquida_por_material`; remover `ItemRequisicao` import |
| `apps/estoque/services.py` | MODIFICAR — add `registrar_devolucao_estoque`, `estornar_requisicao_estoque`; remover `_registrar_atualizacao_estoque_relevante`; add parâmetro `_pos_importacao_hook` em `confirmar_importacao_scpi` (retorno permanece `ImportacaoSCPI`) |
| `apps/estoque/tests/test_selectors.py` | MODIFICAR — atualizar chamadas `entregue_liquida_por_item` → `entregue_liquida_por_material(material_id=...)` |
| `apps/estoque/tests/test_services.py` | MODIFICAR — unpack `(importacao, linhas)` no retorno de `confirmar_importacao_scpi`; add testes dos novos comandos |
| `apps/requisicoes/services/atendimento.py` | MODIFICAR — `registrar_devolucao` usa `registrar_devolucao_estoque`; resolve `item.material_id` antes de chamar |
| `apps/requisicoes/services/ciclo_vida.py` | MODIFICAR — `estornar_requisicao` usa `estornar_requisicao_estoque`; add `registrar_timeline_divergencia_importacao`; remove imports privados de estoque |
| `apps/requisicoes/views.py` | MODIFICAR — `entregue_liquida_por_material(material_id=item.material_id)` |
| `apps/requisicoes/tests/test_services.py` | MODIFICAR — atualizar chamadas do seletor renomeado |
| `apps/estoque/tests/test_selectors.py` | MODIFICAR — atualizar assinatura |
| `apps/notificacoes/tests/test_services.py` | SEM mudança no retorno — `confirmar_importacao_scpi` continua retornando `ImportacaoSCPI` |
| `apps/estoque/views.py` | MODIFICAR — passa `_pos_importacao_hook=registrar_timeline_divergencia_importacao`; sem unpack de tuple |

## Novos comandos de estoque

### `registrar_devolucao_estoque`

```python
@transaction.atomic
def registrar_devolucao_estoque(
    *,
    requisicao_id: int,
    material_id: int,
    quantidade: Decimal,
    ator_id: int,
) -> None:
```

**Responsabilidade:** lock de `SaldoEstoque`, validação de material ativo e saldo único, validação `quantidade <= entregue_liquida`, incremento de `saldo_fisico`, emissão de `MovimentacaoEstoque(DEVOLUCAO)`.

**Pré-condições do chamador:** Requisicao já travada (`select_for_update`); `ator_id` e `item` já validados. O lock da Requisicao é o mutex que impede inserções concorrentes em `MovimentacaoEstoque` para esse `(requisicao_id, material_id)` — conforme ADR-0005, toda mutação de saldo via requisição exige o lock da requisição antes.

**Fluxo interno (todos os passos dentro de `@transaction.atomic`):**
1. Validar `quantidade > 0` (`DadosInvalidos`) — fail-fast antes de qualquer lock
2. Lock `SaldoEstoque` para `material_id` em ordem `(estoque_id, material_id, id)` via `select_for_update`
3. Validar saldo existe e não é ambíguo (`ConflitoDominio`)
4. Validar `material.ativo` (`ConflitoDominio`)
5. Computar `entregue_liquida = entregue_liquida_por_material(requisicao_id, material_id)` — **dentro do lock do SaldoEstoque e da mesma transação**; seguro porque o lock da Requisicao (pré-condição) já bloqueia qualquer nova movimentação para esse par
6. Validar `quantidade <= entregue_liquida` (`ConflitoDominio`)
7. `saldo.saldo_fisico += quantidade; saldo.save(update_fields=['saldo_fisico'])`
8. `_registrar_movimentacao(DEVOLUCAO, origem=OrigemMovimentacaoEstoque(requisicao_id=requisicao_id), ...)`

### `estornar_requisicao_estoque`

```python
@transaction.atomic
def estornar_requisicao_estoque(
    *,
    requisicao_id: int,
    material_ids: list[int],
    ator_id: int,
) -> None:
```

**Responsabilidade:** para cada material com `entregue_liquida > 0`, restaura `saldo_fisico` e emite `MovimentacaoEstoque(ESTORNO_REQUISICAO)`. Levanta `ConflitoDominio` se nenhum material tem entregue líquida > 0.

**Pré-condições do chamador:** Requisicao já travada (`select_for_update`); `ator_id` validado; `material_ids` extraídos dos itens da requisicao. O lock da Requisicao (ADR-0005) garante que nenhuma nova movimentação será inserida para esses materiais/requisicao durante a operação.

**Fluxo interno (todos os passos dentro de `@transaction.atomic`):**
1. Lock `SaldoEstoque` para todos os `material_ids`, em ordem determinística `(estoque_id, material_id, id)` via `select_for_update`
2. Para cada: validar saldo existe e não é ambíguo (`ConflitoDominio`)
3. Computar `entregue_liquida_por_material(requisicao_id, material_id)` para cada material — **dentro do lock**, consistente porque a Requisicao está travada
4. Filtrar `itens_com_liquida = [(mid, liq) for ... if liq > 0]`
5. Se `itens_com_liquida` vazio → `ConflitoDominio('Não há entregue líquida a estornar.', code='sem_liquida_para_estorno')`
6. Para cada item com liquida > 0: `saldo.saldo_fisico += liquida; saldo.save(update_fields=['saldo_fisico'])`
7. `_registrar_movimentacao(ESTORNO_REQUISICAO, origem=OrigemMovimentacaoEstoque(requisicao_id=requisicao_id), ...)` por material

### Mudança de assinatura: `entregue_liquida_por_material`

```python
def entregue_liquida_por_material(*, requisicao_id: int, material_id: int) -> Decimal:
```

Remove importação de `apps.requisicoes.models.ItemRequisicao`. O cálculo via `MovimentacaoEstoque` permanece idêntico — apenas não resolve mais `item_id → material_id`, pois o chamador já passa `material_id` diretamente.

**Callers que precisam de `item.material_id` antes de chamar:**
- `atendimento.py::registrar_devolucao` — já tem `item = ItemRequisicao.objects.get(...)`; usa `item.material_id`
- `ciclo_vida.py::estornar_requisicao` — itera `requisicao.itens`; usa `item.material_id`
- `views.py::detalhe_requisicao_view` — itera `itens`; usa `item.material_id`
- Testes em `test_selectors.py` e `test_services.py` — passam `material_id` direto

### Quebra da aresta `estoque → requisicoes`

#### `entregue_liquida_por_item` → `entregue_liquida_por_material`

O seletor deixa de importar `ItemRequisicao`. A referência por `material_id` é exatamente o contrato do ADR-0015 §3 ("granularidade por material; sem FK de item").

#### `_registrar_atualizacao_estoque_relevante` → `registrar_timeline_divergencia_importacao`

Movida para `apps/requisicoes/services/ciclo_vida.py` (ou novo `apps/requisicoes/services/hooks_estoque.py`). Mantém a mesma lógica: encontra requisições AUTORIZADAS afetadas por divergência crítica de saldo e cria `TimelineRequisicao`.

**`confirmar_importacao_scpi` permanece retornando apenas `ImportacaoSCPI`** (sem tuple — não vaza `linhas` para os callers). Aceita parâmetro interno `_pos_importacao_hook: Callable | None = None` que, se fornecido, é chamado dentro da mesma `transaction.atomic` com `(linhas, estoque, importacao, ator)`.

```python
def confirmar_importacao_scpi(
    *,
    ator_id: int,
    conteudo_bytes: bytes,
    arquivo_nome: str,
    estoque_id: int,
    _pos_importacao_hook=None,  # Callable[[linhas, estoque, importacao, ator], None] | None
) -> ImportacaoSCPI:
    ...
    with transaction.atomic():
        ...
        importacao = ImportacaoSCPI.objects.create(...)
        if _pos_importacao_hook is not None:
            _pos_importacao_hook(linhas=linhas, estoque=estoque, importacao=importacao, ator=ator)
    return importacao
```

`confirmar_importacao_scpi_view` em `apps/estoque/views.py` importa e passa o hook:

```python
from apps.requisicoes.services import registrar_timeline_divergencia_importacao

importacao = confirmar_importacao_scpi(
    ...,
    _pos_importacao_hook=registrar_timeline_divergencia_importacao,
)
```

O VIEW pode importar de `requisicoes` (camada de adaptação — ADR-0004). `estoque/services.py` continua sem importar `requisicoes`. Testes de `confirmar_importacao_scpi` sem VIEW **não precisam mudar** — o hook é opcional e ausente por padrão.

## `apps/estoque/types.py`

```python
from typing import TypedDict
from decimal import Decimal

class ItemReservaEstoque(TypedDict):
    material_id: int
    quantidade_solicitada: Decimal

class ItemLiberacaoReserva(TypedDict):
    material_id: int
    quantidade_reservada: Decimal

class ItemAtendimentoSaldo(TypedDict):
    material_id: int
    quantidade_autorizada: Decimal
    quantidade_entregue: Decimal
```

`services.py` importa de `types.py` para evitar duplicação; as importações atuais em `requisicoes` passam a importar de `apps.estoque.types`.

## Estratégia de testes

### Novos testes em `apps/estoque/tests/test_services.py`

**`registrar_devolucao_estoque`:**
- Happy path: saldo_fisico incrementado + MovimentacaoEstoque DEVOLUCAO criada
- Erro: `material_id` sem saldo → `ConflitoDominio`
- Erro: material inativo → `ConflitoDominio`
- Erro: `quantidade > entregue_liquida` → `ConflitoDominio`
- Erro: mais de um saldo para o material → `ConflitoDominio`

**`estornar_requisicao_estoque`:**
- Happy path: saldo_fisico restaurado + MovimentacaoEstoque ESTORNO_REQUISICAO por item
- Erro: nenhum material com entregue_liquida > 0 → `ConflitoDominio`
- Erro: material_id sem saldo → `ConflitoDominio`
- Atomicidade: falha em saldo_item.save deve rollback toda a operação

### Testes de `entregue_liquida_por_material`

Mesmos cenários existentes dos testes de `entregue_liquida_por_item` em `test_selectors.py`, com `material_id=item.material_id`.

### Testes de integração dos services migrados

- `registrar_devolucao` em `atendimento.py` — comportamento externo inalterado
- `estornar_requisicao` em `ciclo_vida.py` — comportamento externo inalterado
- `confirmar_importacao_scpi` — retorno `ImportacaoSCPI` inalterado; hook de timeline via `_pos_importacao_hook` passado pelo VIEW

### Permissões / estado inválido

Cobertura existente mantida. Não há mudança de policy ou transição de estado.

## Invariantes (ADR-0015)

- Todo `SaldoEstoque.saldo_fisico` mutado emite `MovimentacaoEstoque` na mesma transação
- `Σ delta_fisico` por `(estoque, material)` = `saldo_fisico`
- `entregue_liquida = -Σ delta_fisico(CONSUMO, DEVOLUCAO, ESTORNO_REQUISICAO)` por `(requisicao, material)`

## Riscos

**Atomicidade do hook:** O `_pos_importacao_hook` é chamado dentro de `with transaction.atomic():` em `confirmar_importacao_scpi`. A VIEW não precisa de `@transaction.atomic` extra — o hook já participa da mesma transação do serviço.

**Segurança do `entregue_liquida` dentro do lock (ADR-0005):** `registrar_devolucao_estoque` e `estornar_requisicao_estoque` computam `entregue_liquida_por_material` DEPOIS de adquirir o lock de `SaldoEstoque` e dentro de `@transaction.atomic`. A consistência é garantida porque toda movimentação de estoque vinculada a uma requisição exige o lock da Requisicao — pré-condição fornecida pelo chamador. Portanto, nenhuma nova entrada pode ser inserida em `MovimentacaoEstoque` para esse `(requisicao_id, material_id)` enquanto o lock da Requisicao é mantido.

**Renomeação de `entregue_liquida_por_item`:** função referenciada em 3 services + 2 views + ~15 testes. Renomeação mecânica sem risco lógico — verificar por `grep 'entregue_liquida_por_item'` pós-migração.
