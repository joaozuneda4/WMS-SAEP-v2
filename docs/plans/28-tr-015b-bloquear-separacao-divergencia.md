# Plano — Issue #28: TR-015B — bloquear `separar_para_retirada` por divergência/físico insuficiente

## Escopo

**O que muda:**
- `apps/requisicoes/services.py` — `separar_para_retirada`: adicionar validação de saldo antes da transição.
- `apps/requisicoes/tests/test_services.py` — novos testes para TR-015B.

**O que NÃO muda:**
- Modelo `SaldoEstoque` (propriedade `divergente` já existe).
- Transição de estado, timeline, efeitos de estoque do caminho feliz.
- Policies, views, templates.

## Arquivos tocados

| Arquivo | Mudança |
|---|---|
| `apps/requisicoes/services.py` | Import `SaldoEstoque`; validação TR-015B em `separar_para_retirada` |
| `apps/requisicoes/tests/test_services.py` | Dois novos testes: divergência crítica e físico insuficiente |

## Implementação

Em `separar_para_retirada`, após a verificação de estado (`AUTORIZADA`) e antes de `verificar_transicao_valida`:

1. Carregar itens com `quantidade_autorizada > 0`, `select_related('material')`.
2. Adquirir lock em `SaldoEstoque` para os `material_id` desses itens, em ordem determinística `(estoque_id, material_id, id)` — consistente com ADR-0005.
3. Para cada item, verificar:
   - `saldo.divergente` → `saldo_fisico < saldo_reservado` (EST-07)
   - `saldo.saldo_fisico < item.quantidade_autorizada` (físico insuficiente)
4. Se qualquer falhar: lançar `DadosInvalidos` nomeando o material, orientar corrigir estoque ou cancelar via TR-013.
5. Não transicionar, não alterar estoque, reserva, entregue nem timeline.

**Import a adicionar:** `SaldoEstoque` de `apps.estoque.models`.

## Estratégia de testes

| Cenário | Fixture necessária | Exceção esperada |
|---|---|---|
| Caminho feliz (já coberto) | `requisicao_autorizada`, `material_disponivel` | Sem exceção |
| TR-015B: material com divergência crítica | Autorizar req com `material_divergente` depois de forçar divergência | `DadosInvalidos` com `code='separacao_bloqueada_divergencia'` |
| TR-015B: físico insuficiente (sem divergência) | Autorizar req, depois reduzir `saldo_fisico` abaixo de `quantidade_autorizada` | `DadosInvalidos` com `code='separacao_bloqueada_divergencia'` |

## Invariantes (docs/matriz-invariantes.md)

- **EST-07**: divergência crítica (`saldo_fisico < saldo_reservado`) bloqueia separação.
- **EST-08**: material divergente bloqueia TR-015B.

## Riscos

- Nenhum impacto em OpenAPI (sem serializer).
- Lock adicional em SaldoEstoque: consistente com padrão já usado por `reservar_saldos_para_autorizacao` e `consumir_e_liberar_reservas_para_atendimento`.
- Sem migração de schema.
