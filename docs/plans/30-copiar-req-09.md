# Plano — Issue #30: REQ-09 cópia com itens inelegíveis

## Escopo

Implementar TR-001 variant de cópia de requisição (REQ-09): criar rascunho com **todos** os itens
da origem (atendida ou recusada), sinalizando inelegíveis na tela de edição, sem impedir a criação.

**Não muda:** enviar_para_autorizacao (já valida elegibilidade no envio via _validar_itens).

### Decisão adotada (opção 2 do issue)
- Rascunho criado com todos os itens, incluindo inelegíveis.
- Itens inelegíveis são marcados visualmente no form de edição.
- Saldo atual exibido por item para guiar correção.
- REQ-05 só se aplica ao envio; a cópia pode criar rascunho mesmo sem itens elegíveis.

## Arquivos tocados

| Arquivo | Mudança |
|---|---|
| `apps/requisicoes/services.py` | + `copiar_requisicao` |
| `apps/requisicoes/policies.py` | + `pode_copiar_requisicao`, `exigir_pode_copiar_requisicao` |
| `apps/requisicoes/selectors.py` | + `saldos_por_materiais` |
| `apps/requisicoes/views.py` | + `copiar_requisicao_view`; atualiza `_detalhe_context`, `editar_rascunho_view` |
| `apps/requisicoes/urls.py` | + `<pk>/copiar/` |
| `apps/requisicoes/templatetags/requisicoes_tags.py` | + `get_item` filter |
| `apps/requisicoes/templates/requisicoes/detalhe.html` | + bloco "Copiar" p/ atendida/recusada |
| `apps/requisicoes/templates/requisicoes/rascunho_form.html` | + banner de inelegíveis + saldo |
| `apps/requisicoes/templates/requisicoes/partials/_item_form_row.html` | + badge inelegível |
| `apps/requisicoes/tests/test_services.py` | + testes TR-009 |
| `apps/requisicoes/tests/test_policies.py` | + testes pode_copiar |
| `apps/requisicoes/tests/test_views.py` | + testes view copiar |

## Test strategy

| Caso | Nível |
|---|---|
| Cópia de `atendida` cria rascunho com todos os itens | service |
| Cópia de `recusada` cria rascunho | service |
| Cópia não inclui quantidade_autorizada nem entregue | service |
| Origem em estado inválido (rascunho, autorizada…) → EstadoInvalido | service |
| Ator sem permissão → PermissaoNegada | service/policy |
| Itens inelegíveis incluídos (sem erro no service) | service |
| pode_copiar: criador pode, estranho não pode | policy |
| View POST copia e redireciona para editar | view |
| View POST estado inválido → mensagem erro | view |

## Invariantes

- REQ-05: rascunho criado com todos os itens; validação de elegibilidade acontece no envio (TR-005).
- REQ-09: não copia autorizado/entregue; origem pode ser atendida ou recusada.
- Setor beneficiário: snapshot do setor no momento da cópia (não da origem).

## Riscos

- Beneficiário da requisição original pode estar inativo no momento da cópia → service deve validar e lançar DadosInvalidos.
- Nenhuma mudança de estoque/reserva nesta transição.
