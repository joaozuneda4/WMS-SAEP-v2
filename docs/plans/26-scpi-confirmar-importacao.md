# Plano: Issue #26 — SCPI: confirmar importação e persistir metadados

## Scope

**O que muda:**
- `selectors.py`: adiciona `denominacao_scpi` a `LinhaPreviewSCPI`; `_parse_linhas_csv_scpi` extrai `DENOMINACAO`.
- `models.py`: novo model `ImportacaoSCPI` (metadados da importação).
- `policies.py`: `pode_confirmar_importacao_scpi` / `exigir_pode_confirmar_importacao_scpi`.
- `services.py`: `confirmar_importacao_scpi` — verifica hash duplicado, cria Material+SaldoEstoque para novos, grava `ImportacaoSCPI`.
- `views.py`: `confirmar_importacao_scpi_view` (POST).
- `urls.py`: rota `importacao-scpi/confirmar/`.
- `templates/estoque/preview_importacao_scpi.html`: habilita botão de confirmação com formulário real.
- `tests/`: cobertura TDD de todos os novos comportamentos.

**O que NÃO muda:**
- `saldo_fisico` de materiais já existentes — nunca sobrescrito.
- Fluxo de preview (issue #25) — sem regressão.
- Modelo `SaidaExcepcional` ou qualquer outra entidade de estoque.
- Issue #27 (histórico) — fora de escopo aqui.

## Arquivos tocados

| Arquivo | Mudança |
|---|---|
| `apps/estoque/models.py` | +`ImportacaoSCPI` |
| `apps/estoque/selectors.py` | +`denominacao_scpi` em `LinhaPreviewSCPI`; parser extrai DENOMINACAO |
| `apps/estoque/services.py` | +`confirmar_importacao_scpi` |
| `apps/estoque/policies.py` | +`pode_confirmar_importacao_scpi`, +`exigir_pode_confirmar_importacao_scpi` |
| `apps/estoque/views.py` | +`confirmar_importacao_scpi_view` |
| `apps/estoque/urls.py` | +rota confirmar |
| `apps/estoque/templates/estoque/preview_importacao_scpi.html` | habilita botão confirm |
| `apps/estoque/tests/test_services.py` | +`TestConfirmarImportacaoScpi` |
| `apps/estoque/tests/test_views.py` | +`TestConfirmarImportacaoScpiView` |
| `apps/estoque/tests/test_selectors.py` | +`TestGerarPreviewImportacaoScpi` |

## Test strategy

| Cenário | Tipo |
|---|---|
| `confirmar_importacao_scpi` — caminho feliz: grava `ImportacaoSCPI`, cria `Material`+`SaldoEstoque` para novos | service |
| `confirmar_importacao_scpi` — hash duplicado lança `ConflitoDominio` | service |
| `confirmar_importacao_scpi` — material já existente com divergência: sem alterar `saldo_fisico` | service |
| `confirmar_importacao_scpi` — sem permissão lança `PermissaoNegada` | service (policy) |
| `gerar_preview_importacao_scpi` — retorna `denominacao_scpi` correta | selector |
| view: não autenticado → 302 | view |
| view: chefe almoxarifado → 403 | view |
| view: superusuário POST válido → redirect com mensagem sucesso | view |
| view: hash duplicado → 200 com erro | view |
| view: arquivo ausente → 200 com erro | view |

## Invariants

- `ImportacaoSCPI.arquivo_hash` é único → `ConflitoDominio` antes de qualquer mutação.
- `SaldoEstoque` criado para material novo tem `saldo_reservado=0`.
- Nenhum `SaldoEstoque` existente é atualizado pela confirmação.
- `Material` criado usa `UnidadeMedida.UNIDADE` como padrão (SCPI não informa unidade).
- Service usa `transaction.atomic`.
- View passa `request.user.id`, nunca `request.user`.

## Risks

- Coluna `DENOMINACAO` pode estar ausente no CSV: o parser deve tolerar e usar string vazia como fallback.
- Hash sha256 calculado sobre bytes crus (antes de normalização) para garantir idempotência real do arquivo.
