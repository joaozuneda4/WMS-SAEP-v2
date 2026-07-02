# Plano — Issue #61: achados críticos da auditoria UI/UX

Fonte: `.design/audit-uiux-2026-07/AUDITORIA_UIUX.md` (seção "Críticos").

## Scope

Três correções críticas e independentes, cada uma end-to-end (selector/form/view → template → comportamento observável):

- **C1** — `historico_requisicoes_visiveis_para` vaza rascunho de terceiro (RBAC), renderiza PK interna (`"Rascunho #2"`) e gera 404 ao clicar em "Ver".
- **C2** — `ItemAtendimentoForm.quantidade_entregue` não pré-preenche o campo "Quantidade entregue" para materiais com casas decimais (vírgula decimal PT-BR rejeitada por `<input type="number">`).
- **C3** — Notificações mostram PK crua (`"Requisição #3"`) em vez de `numero_publico`, e o item não é clicável.

**O que NÃO muda:**
- N+1 de `historico_requisicoes_visiveis_para`/`pode_filtrar_historico_por_setor` (resolução repetida de `papel_efetivo`) — já sinalizado e conscientemente adiado no PR #65 (sync do fork); não faz parte desta issue.
- Templates fora do histórico que usam `"Rascunho #{{ req.pk }}"` (ex. `lista_minhas.html`) — lá o ator é o próprio dono do rascunho, não há vazamento entre atores; fora de escopo.
- `Requisicao.__str__` (usa fallback `Rascunho #{pk}` para uso interno/admin) — não é superfície user-facing coberta pela auditoria.
- Nenhuma migration nova (C1/C2/C3 não tocam schema).

## Files touched

- `apps/requisicoes/selectors.py` — `historico_requisicoes_visiveis_para` (linha ~266): aplicar `nao_rascunho` nos ramos almoxarifado e chefe-de-setor, espelhando `requisicoes_visiveis_para` (linha ~87).
- `apps/requisicoes/templates/requisicoes/historico_requisicoes.html` e `partials/_tabela_historico_requisicoes.html`: fallback `"Rascunho #{{ req.pk }}"` → `"Rascunho"` (mesmo padrão de `detalhe.html`), defesa em profundidade mesmo após a exclusão de RASCUNHO no selector.
- `apps/requisicoes/forms.py` — `ItemAtendimentoForm.quantidade_entregue` (linha ~261): `localize=False` no `DecimalField`.
- `apps/notificacoes/models.py`: nenhuma mudança de schema — `requisicao_id` continua `IntegerField` solto (quebra de import reverso, ADR já estabelecido).
- `apps/notificacoes/views.py` / novo `apps/notificacoes/selectors.py`: resolver `requisicao_id → (numero_publico, pk)` em lote (uma query `Requisicao.objects.filter(pk__in=...)`, sem N+1) para popular o contexto do template.
- `apps/notificacoes/templates/notificacoes/lista.html`: trocar `"Requisição #{{ notificacao.requisicao_id }}"` por `numero_publico` (fallback `"Rascunho"` quando nulo ou requisição não encontrada) envolto em link para `requisicoes:detalhe`.

## Test strategy

**C1** (`apps/requisicoes/tests/test_selectors.py`, `test_views.py`):
- Regressão: chefe de setor e almoxarifado não veem rascunho de terceiro no histórico (fixture com rascunho de subordinado) — comparação de conjunto de IDs.
- View: GET `/requisicoes/historico/` não lista o rascunho; clicar em "Ver" (GET detalhe) não retorna 404 para nenhuma linha listada (porque rascunho de terceiro nunca aparece).
- Regressão de não-regressão: criador continua vendo o próprio rascunho em `requisicoes:minhas` (não afetado, escopo diferente).

**C2** (`apps/requisicoes/tests/test_forms.py` ou `test_views.py`):
- GET em `/requisicoes/<id>/atender/` para requisição com item de material com `decimal_places` (ex. `kg`, quantidade `5.000`) retorna o campo `Entregue` pré-preenchido com valor parseável por `<input type="number">` (ponto decimal, não vírgula).

**C3** (`apps/notificacoes/tests/test_views.py`):
- Notificação com `requisicao_id` de requisição com `numero_publico` exibe o número público, não o PK.
- Notificação cujo `requisicao_id` aponta para rascunho (`numero_publico is None`) ou requisição inexistente exibe fallback `"Rascunho"`, sem erro.
- Item de notificação é um link (`<a href=...>`) para `requisicoes:detalhe` do `requisicao_id` correspondente.

## Invariants (docs/design-acesso-rapido/matriz-invariantes.md)

- RBAC nunca decidido em view/template — C1 mantém a checagem de visibilidade inteiramente em `selectors.py`.
- Mensagens e templates em PT-BR.
- Filtros/selectors nunca ampliam o universo de visibilidade já definido pelo RBAC (C1 apenas estreita).

## Risks

- **C1**: mudar `historico_requisicoes_visiveis_para` pode reduzir contagens em testes existentes que dependiam do comportamento antigo (incluir rascunho de terceiro) — checar `test_selectors.py`/`test_views.py` de histórico já existentes antes de alterar.
- **C3**: `requisicao_id` é `IntegerField` solto (não FK) por design (quebra de import reverso) — resolução em lote precisa tratar PKs inexistentes/de rascunho sem lançar exceção, e sem N+1 (uma query para todas as notificações da página).
- Nenhum risco de concorrência, transação ou saldo — as três correções são de leitura/apresentação.
