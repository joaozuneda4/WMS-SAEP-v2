# Plano — #19 Exibir detalhe de saída excepcional

## Scope

### Muda
- `apps/estoque/policies.py`: adicionar `pode_estornar_saida_excepcional` + `exigir_pode_estornar_saida_excepcional`
- `apps/estoque/services.py`: adicionar `estornar_saida_excepcional`
- `apps/estoque/selectors.py`: adicionar `buscar_detalhe_saida_excepcional`
- `apps/estoque/views.py`: adicionar `detalhe_saida_excepcional_view`
- `apps/estoque/urls.py`: adicionar rota `saidas-excepcionais/<int:pk>/`
- `apps/estoque/templates/estoque/detalhe_saida_excepcional.html`: novo template
- `apps/estoque/templates/estoque/lista_saidas_excepcionais.html`: substituir `href="#"` por URL real do detalhe

### Não muda
- Modelos (nenhuma mudança de schema)
- Fluxo de nova saída excepcional
- Outros apps

## Files touched

| Arquivo | Ação |
|---------|------|
| `apps/estoque/policies.py` | Adicionar 2 funções |
| `apps/estoque/services.py` | Adicionar `estornar_saida_excepcional` |
| `apps/estoque/selectors.py` | Adicionar `buscar_detalhe_saida_excepcional` |
| `apps/estoque/views.py` | Adicionar `detalhe_saida_excepcional_view` |
| `apps/estoque/urls.py` | Adicionar 1 rota |
| `apps/estoque/templates/estoque/detalhe_saida_excepcional.html` | Novo |
| `apps/estoque/templates/estoque/lista_saidas_excepcionais.html` | Atualizar hrefs |
| `apps/estoque/tests/test_policies.py` | Adicionar testes `pode_estornar_*` |
| `apps/estoque/tests/test_services.py` | Adicionar testes `estornar_saida_excepcional` |
| `apps/estoque/tests/test_selectors.py` | Adicionar teste `buscar_detalhe_saida_excepcional` |
| `apps/estoque/tests/test_views.py` | Adicionar `TestDetalheSaidaExcepcionalView` |

## Test strategy

### Policy: `pode_estornar_saida_excepcional`
- chefe almox → True
- aux almox → False (consulta, não estorna)
- superuser → True
- inativo → False

### Service: `estornar_saida_excepcional`
- happy path: REGISTRADA → ESTORNADA, saldo_fisico restaurado, estornado_em/por preenchidos
- estado ESTORNADA → ConflitoDominio (já estornada)
- ator sem permissão → PermissaoNegada
- saida inexistente → DadosInvalidos
- justificativa vazia → DadosInvalidos

### Selector: `buscar_detalhe_saida_excepcional`
- retorna SaidaExcepcional com itens prefetchados
- saida inexistente → None ou raises (decidir na impl)

### View: `detalhe_saida_excepcional_view`
- GET chefe almox → 200
- GET aux almox → 200
- GET superuser → 200
- GET solicitante → 403
- GET anonimo → redirect login
- GET inexistente → 404
- Contexto: `saida`, `pode_estornar`, `itens`
- POST estorno chefe → 302 para detalhe
- POST estorno aux → 403
- POST sem justificativa → 200 com erro
- POST saida já ESTORNADA → 200 com erro

## Invariants

- `saida_excepcional_estorno_consistente` (CheckConstraint no model): REGISTRADA↔estornado_em null; ESTORNADA↔estornado_em not null
- Estorno é total (todos os itens); sem estorno parcial (out of scope)

## Risks

- Nenhuma migração necessária (campos `estornado_em`, `estornado_por`, `justificativa_estorno` já existem)
- Sem concorrência adicional (estorno faz `select_for_update` nos saldos)
