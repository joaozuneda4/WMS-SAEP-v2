# Plano #20 — Estornar saída excepcional

## Scope

Adicionar URL dedicada `saidas-excepcionais/<pk>/estornar/` para ação de estorno,
seguindo o padrão já consolidado em `requisicoes` (`/autorizar/`, `/cancelar/`, `/recusar/`).

**O que muda:**
- Nova view `estornar_saida_excepcional_view` (POST-only)
- Nova URL `estornar_saida_excepcional`
- `detalhe_saida_excepcional_view` reduzida a GET-only
- Modal no template aponta para a nova URL
- Testes atualizados/adicionados para a nova view

**O que NÃO muda:**
- Lógica de negócio (service, selector, policy — já corretos)
- Template HTML (exceto `action=` do form do modal)
- Nenhum modelo ou migration

## Files touched

| Arquivo | Ação |
|---|---|
| `apps/estoque/views.py` | Refatorar detalhe (GET-only) + nova view estornar |
| `apps/estoque/urls.py` | Adicionar URL `estornar_saida_excepcional` |
| `apps/estoque/templates/estoque/detalhe_saida_excepcional.html` | Atualizar `action=` do form |
| `apps/estoque/tests/test_views.py` | Adicionar `TestEstornarSaidaExcepcionalView`, mover testes POST |

## Test strategy

- **Happy path**: POST chefe → 302 → detalhe
- **Permissão negada**: auxiliar → 403
- **Domínio**: justificativa vazia → 302 para detalhe com erro via messages; já estornada → idem
- **Auth**: anônimo → redirect login; superuser → 302 sucesso

## Invariants

- SAE-07: estorno total; recompõe `saldo_fisico`; `saldo_reservado` intocado
- SAE-02: estado só transita REGISTRADA → ESTORNADA (uma vez)

## Risks

Baixo. Nenhuma mudança de model, migration, nem contrato de serviço.
