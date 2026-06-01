# Plano de implementação — #25 SCPI: pré-visualizar importação com alertas

## Scope

**O que muda:**
- `apps/estoque/selectors.py` — normalização CSV + geração de preview (read-only)
- `apps/estoque/policies.py` — `pode_visualizar_preview_scpi` + `exigir_pode_visualizar_preview_scpi`
- `apps/estoque/views.py` — `preview_importacao_scpi_view`
- `apps/estoque/urls.py` — `importacao-scpi/preview/`
- `apps/estoque/templates/estoque/preview_importacao_scpi.html`
- `apps/estoque/tests/test_selectors.py` — testes de normalização + preview
- `apps/estoque/tests/test_policies.py` — testes de permissão SCPI
- `apps/estoque/tests/test_views.py` — testes de contrato HTTP
- `apps/estoque/tests/conftest.py` — fixtures auxiliares se necessário

**O que NÃO muda:**
- Nenhum modelo novo (preview é read-only, sem persistência)
- `saldo_fisico` não é mutado
- Nenhuma criação de `Material` (pertence ao #26)
- Nenhum bloqueio por hash (pertence ao #26)
- `services.py` intocado

## Formato CSV SCPI (assumido)

Semicolon-delimited, UTF-8 com BOM opcional, cabeçalho na primeira linha.
Colunas mínimas: `CADPRO` e `QUANTIDADE`.
Registros podem ocupar múltiplas linhas (campo com quebra interna).

Normalização:
1. Strip BOM (`﻿`)
2. Normalizar CRLF → LF
3. `csv.DictReader` resolve aspas e campos multi-linha nativamente

## Files touched

| Arquivo | Operação |
|---------|----------|
| `apps/estoque/selectors.py` | adicionar funções ao final |
| `apps/estoque/policies.py` | adicionar funções ao final |
| `apps/estoque/views.py` | adicionar view ao final |
| `apps/estoque/urls.py` | adicionar path |
| `apps/estoque/templates/estoque/preview_importacao_scpi.html` | novo |
| `apps/estoque/tests/test_selectors.py` | novos casos |
| `apps/estoque/tests/test_policies.py` | novos casos |
| `apps/estoque/tests/test_views.py` | novos casos |

## Test strategy

### Selectors
| Caso | Entrada | Saída esperada |
|------|---------|---------------|
| CSV simples OK | `CADPRO;QUANTIDADE\nMAT001;10.000` | 1 linha, status `ok` |
| Divergência | saldo WMS = 100, SCPI = 80 | status `divergente`, delta = -20 |
| Material novo | CADPRO não existe | status `novo`, saldo_wms = 0 |
| CSV com BOM | `﻿CADPRO;...` | parse correto |
| CSV vazio (só cabeçalho) | `CADPRO;QUANTIDADE\n` | lista vazia |
| CSV sem coluna CADPRO | `FOO;BAR\n` | `DadosInvalidos` |
| Quantidade inválida | `MAT001;abc` | `DadosInvalidos` |

### Policies
| Ator | Resultado |
|------|-----------|
| Superusuário ativo | `True` |
| Usuário inativo | `False` |
| Auxiliar almoxarifado | `False` |
| Chefe almoxarifado | `False` |
| Solicitante | `False` |

### Views
| Caso | Método | Esperado |
|------|--------|---------|
| Não autenticado | GET | redirect login |
| Sem permissão (aux. almox) | GET | 403 |
| Superuser GET | GET | 200, form upload |
| Superuser POST CSV válido | POST | 200, preview table |
| POST arquivo inválido | POST | 200, mensagem de erro |
| POST sem arquivo | POST | 200, erro de campo |

## Invariants verificados

| ID | Verificação |
|----|-------------|
| EST-01 | saldo_fisico não é escrito durante preview |
| PER-05 | superusuário tem acesso |
| PER-08 | view e policy chamam mesmo `pode_*` |

## Risks

- Formato real do CSV SCPI pode divergir da coluna `QUANTIDADE` assumida; normalização é extensível
- Materiais sem `SaldoEstoque` no estoque principal retornam `saldo_wms = 0` (correto: material existe mas sem saldo)

## Design da UI

**Aesthetic:** Industrial/utilitarian — ferramenta analítica interna.
**Unforgettable:** Tabela com row highlighting por status (amber = divergente, teal = novo, green = ok).
**Fluxo:**
1. GET → formulário de upload (drag-and-drop visual)
2. POST com CSV → preview table com resumo de stats
3. POST com erro → estado de erro inline

Layout da tabela:
- Colunas: CADPRO | Material | Saldo WMS | Saldo SCPI | Delta | Status
- Row colors: `bg-amber-50` (divergente), `bg-teal-50` (novo), branco (ok)
- Delta: número colorido com sinal (+/-) e indicador direcional
- Stats bar: total de linhas / divergências / novos
- Ação futura (issue #26): botão "Confirmar importação" desabilitado nesta fase
