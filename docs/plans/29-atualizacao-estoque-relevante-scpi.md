# Plano — Issue #29: registrar `atualizacao_estoque_relevante` em requisições autorizadas

## Scope

### O que muda
- `apps/estoque/services.py` — `confirmar_importacao_scpi`: após criar `ImportacaoSCPI`, identificar materiais com divergência crítica superveniente e registrar evento na timeline das requisições autorizadas afetadas.
- `apps/estoque/tests/test_services.py` — nova classe de testes `TestConfirmarImportacaoScpiTimelineRequisicoes`.
- `apps/estoque/tests/conftest.py` — duas fixtures auxiliares: `material_scpi_critico` e `requisicao_autorizada_critico`.

### O que NÃO muda
- Estado da requisição (permanece `autorizada`).
- Reserva de estoque (não liberada).
- `SaldoEstoque` (não atualizado pelo import — o import apenas registra a divergência).
- Outros services ou views.

## Files touched

| Arquivo | Alteração |
|---|---|
| `apps/estoque/services.py` | Adicionar lógica pós-criação de `ImportacaoSCPI` dentro do `transaction.atomic()` |
| `apps/estoque/tests/test_services.py` | Nova classe de testes |
| `apps/estoque/tests/conftest.py` | Duas novas fixtures |

## Algoritmo (inside `transaction.atomic()`, after `importacao` is created)

1. Coletar `material_id` de todas as linhas com `status == 'divergente'`.
2. Query `SaldoEstoque` filtrando `saldo_fisico__lt=F('saldo_reservado')` para esses materiais — divergência crítica.
3. Se nenhuma saldo crítico, encerrar.
4. Query `ItemRequisicao` filtrando `material_id__in=criticos`, `requisicao__estado=AUTORIZADA`, `quantidade_autorizada__gt=0`.
5. Agrupar por `requisicao_id` → lista de materiais afetados.
6. `TimelineRequisicao.objects.bulk_create(...)` com `EventoTimeline.ATUALIZACAO_ESTOQUE_RELEVANTE` para cada requisição.

## Metadata shape

```json
{
  "importacao_id": 42,
  "materiais": [
    {"codigo": "000.000.001", "nome": "Tinta Branca 18L"}
  ]
}
```

## Test strategy

| Cenário | Resultado esperado |
|---|---|
| Material crítico + requisição autorizada com qty_autorizada > 0 | Evento criado, metadata correto |
| Material divergente mas NÃO crítico (saldo_fisico >= saldo_reservado) | Sem evento |
| Material crítico mas sem requisição autorizada | Sem evento |
| Material crítico, requisição autorizada, qty_autorizada é nulo | Sem evento |
| Dois materiais críticos na mesma requisição | Um evento com lista agregada |

## Invariants

- `docs/estado-transicoes-requisicao.md` §4: `atualizacao_estoque_relevante` — um evento por requisição por importação.
- A requisição não muda de estado automaticamente.
- Evento na mesma transação da criação do `ImportacaoSCPI`.
- Registrar apenas para `estado == 'autorizada'`.

## Risks

- Nenhuma mudança de schema (modelo `TimelineRequisicao` já existe com `metadata` JSONField).
- Import circular: `requisicoes.models` importado dentro da função (padrão já estabelecido no codebase).
- Sem lock adicional necessário: apenas leitura de `Requisicao` (sem mudar estado), append-only em `TimelineRequisicao`.
