# Plano: #18 — Registrar saída excepcional

## Scope

**Inclui:**
- GET `/estoque/saidas-excepcionais/nova/` — formulário de novo registro (dois blocos: dados + materiais)
- POST `/estoque/saidas-excepcionais/nova/` — criação atômica do documento, geração de `SXP-AAAA-NNNNNN`, baixa de `saldo_fisico`, redirect para detalhe (stub)
- GET `/estoque/saidas-excepcionais/buscar-materiais/` — JSON autocomplete de materiais (reutiliza UI do rascunho de requisição)
- `SequenciaSaidaExcepcional` em `estoque/models.py` para emitir número público
- `exigir_pode_registrar_saida_excepcional` em `policies.py`
- `buscar_materiais_saida_excepcional` em `selectors.py`
- `registrar_saida_excepcional` em `services.py`
- Atualização dos `href="#"` da lista (Nova saída + Ver detalhe → stub `#` para detalhe, real para nova)

**Não inclui:**
- Tela de detalhe (issues futuras)
- Estorno
- Filtros/paginação na lista
- Design tokens novos

## Files touched

| Arquivo | Ação |
|---|---|
| `apps/estoque/models.py` | Add `SequenciaSaidaExcepcional` |
| `apps/estoque/policies.py` | Add `exigir_pode_registrar_saida_excepcional` |
| `apps/estoque/selectors.py` | Add `buscar_materiais_saida_excepcional` |
| `apps/estoque/services.py` | Add `registrar_saida_excepcional` |
| `apps/estoque/views.py` | Add `nova_saida_excepcional_view`, `buscar_materiais_saida_excepcional_view` |
| `apps/estoque/urls.py` | Add `nova/` e `buscar-materiais/` |
| `apps/estoque/templates/estoque/nova_saida_excepcional.html` | Create |
| `apps/estoque/templates/estoque/lista_saidas_excepcionais.html` | Update `href="#"` para nova |
| `apps/estoque/tests/test_services.py` | Create |
| `apps/estoque/tests/test_views.py` | Extend |

## Test strategy

| Caso | Tipo |
|---|---|
| Happy path: chefe cria saída, saldo_fisico decresce, numero_publico emitido | service |
| Material duplicado no mesmo documento → DadosInvalidos | service |
| Material inexistente no saldo → ConflitoDominio | service |
| Lista > 0 itens obrigatória → DadosInvalidos | service |
| GET `/nova/` → 200 para chefe/superuser | view |
| GET `/nova/` → 403 para aux/solicitante | view |
| POST válido → redirect (302) para stub detalhe | view |
| POST sem itens → 200 com erro | view |
| POST com material duplicado → 200 com erro | view |
| Buscar materiais → JSON com resultados | view |

## Invariants

- `saldo_fisico >= 0` (constraint DB em `SaldoEstoque`) — a baixa direta pode levar `saldo_fisico` a zero; constraint impede negativo
- `unico_material_por_saida_excepcional` (UniqueConstraint) — reforçado também em service e view
- `quantidade_saida_excepcional_positiva` (CheckConstraint)
- `saida_excepcional_estorno_consistente` (CheckConstraint) — novo documento começa como `REGISTRADA`

## Risks

- Schema change (SequenciaSaidaExcepcional) → executar `make setup` após alterar models.py
- `select_for_update` em `SaldoEstoque` e em `SequenciaSaidaExcepcional` na mesma transação → ordem determinística: primeiro saldos (ordenado por `material_id`), depois sequência
- Autocomplete usa `saldo_fisico` (não `saldo_disponivel`) por se tratar de baixa direta, não reserva
