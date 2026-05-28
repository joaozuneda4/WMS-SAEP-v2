# Plano — Issue #8: Dispatcher pós-login + preservação ?next (Batch C)

## Scope

**O que muda:**
- `core.views.home` reescrita como dispatcher por papel (302 puro)
- `LOGIN_REDIRECT_URL` setado para `'/'`
- Painel `/requisicoes/` (rota, view, template) deletado
- `core/templates/core/home.html` deletado
- `DetalheRequisicaoView` já expõe `voltar_url` via `_detalhe_context` → só validar
- Modais de autorizar/enviar/separar ganham `hidden_inputs` com `next`
- Views POST de autorizar/enviar/separar/atender redirecionam via `_voltar_url`
- "Registrar retirada" link no detalhe passa `?next={{ voltar_url|urlencode }}`
- `atender_retirada.html` recebe hidden `next`

**O que NÃO muda:**
- Lógica das policies (`pode_ver_fila_atendimento`, `pode_ver_fila_autorizacao`)
- Estrutura de modais (componente `modal.html` já suporta `hidden_inputs`)
- Views de cancelar/recusar/retornar (já usam `_voltar_url` no sucesso)

## Files touched

| Arquivo | Ação |
|---|---|
| `apps/core/views.py` | Reescrever `home` como dispatcher |
| `config/settings/base.py` | `LOGIN_REDIRECT_URL = '/'` |
| `apps/core/templates/core/home.html` | Deletar |
| `apps/requisicoes/templates/requisicoes/home.html` | Deletar |
| `apps/requisicoes/urls.py` | Remover `path('', views.home, name='home')` |
| `apps/requisicoes/views.py` | Remover fn `home`; add hidden_inputs no ctx; _voltar_url nos POSTs de autorizar/enviar/separar/atender |
| `apps/requisicoes/templates/requisicoes/detalhe.html` | hidden_inputs em autorizar/enviar/separar; ?next no link "Registrar retirada" |
| `apps/requisicoes/templates/requisicoes/atender_retirada.html` | hidden input `next` |

## Dispatcher logic

```
1. @login_required → redireciona para login automaticamente se não autenticado
2. superuser ou staff → /admin/
3. pode_ver_fila_atendimento(user) → /requisicoes/atendimentos/
4. pode_ver_fila_autorizacao(user) → /requisicoes/autorizacoes/
5. else → /requisicoes/minhas/
```

Prioridade implícita: chefe_almox ≈ aux_almox > chefe_setor > aux_setor / solicitante > superuser/staff

## Test strategy

| Cenário | Assertion |
|---|---|
| GET `/` não autenticado | 302 → `/login/?next=/` |
| GET `/` superuser | 302 → `/admin/` |
| GET `/` chefe_almoxarifado | 302 → `/requisicoes/atendimentos/` |
| GET `/` auxiliar_almoxarifado | 302 → `/requisicoes/atendimentos/` |
| GET `/` chefe_setor (não-almox) | 302 → `/requisicoes/autorizacoes/` |
| GET `/` auxiliar_setor | 302 → `/requisicoes/minhas/` |
| GET `/` solicitante (sem papel especial) | 302 → `/requisicoes/minhas/` |
| GET `/requisicoes/<id>/?next=/requisicoes/autorizacoes/` | `voltar_url == /requisicoes/autorizacoes/` |
| POST autorizar com `next=/foo/` | redirect → `/foo/` |
| POST enviar com `next=/bar/` | redirect → `/bar/` |
| POST separar com `next=/baz/` | redirect → `/baz/` |

## Invariants

Nenhuma invariante de domínio afetada (sem mudança em models, services, ou permissões).

## Risks

- `LOGIN_REDIRECT_URL` muda de nome de URL para path: testar login flow completo
- `requisicoes:home` referenciada em algum template/code → grep necessário antes de deletar
