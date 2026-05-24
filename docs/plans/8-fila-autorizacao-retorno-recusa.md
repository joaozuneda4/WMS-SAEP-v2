# Plano: Fila de autorização, retorno e recusa (#8)

## Scope

**Inclui:**
- Selector `fila_autorizacao(ator_id)` em `apps/requisicoes/selectors.py`, restrito a requisições `aguardando_autorizacao` do setor chefiado pelo ator.
- Regra específica: chefe de Almoxarifado vê somente requisições do setor Almoxarifado; superusuário vê a fila completa.
- Policies `pode_ver_fila_autorizacao`, `pode_retornar_para_rascunho`, `pode_recusar_requisicao` e pares `exigir_*`.
- Service `retornar_para_rascunho(*, ator_id, requisicao_id, observacao='')`: TR-006, preserva `numero_publico`, registra timeline `retorno_rascunho`, não toca estoque.
- Service `recusar_requisicao(*, ator_id, requisicao_id, motivo)`: TR-011, exige motivo não vazio, registra timeline `recusa`, não toca estoque.
- Views finas para `/requisicoes/autorizacoes/`, POST de retorno e POST de recusa, com PRG e `HX-Redirect` quando aplicável.
- UI server-rendered: fila operacional de autorização e ações no detalhe, seguindo `.design/` e `docs/design-system.md`.
- Testes por camada: policies, selectors, services e contrato HTTP.

**Não inclui:**
- Autorização integral (`aguardando_autorizacao -> autorizada`) e reserva de estoque.
- Cancelamento antes da autorização.
- Notificações pós-commit.
- Paginação, filtros, polling HTMX ou tela dedicada de edição do rascunho.
- Alterações de schema/model.

## Files Touched

| Arquivo | Operação |
|---|---|
| `apps/requisicoes/transitions.py` | Declarar TR-006 e TR-011 como transições válidas |
| `apps/requisicoes/policies.py` | Policies de fila, retorno e recusa |
| `apps/requisicoes/selectors.py` | Selector `fila_autorizacao` com `Count('itens')` |
| `apps/requisicoes/services.py` | Services `retornar_para_rascunho` e `recusar_requisicao` |
| `apps/requisicoes/views.py` | Views de fila, retorno e recusa; flags de ação no detalhe |
| `apps/requisicoes/urls.py` | Rotas `autorizacoes/`, `<pk>/retornar-rascunho/`, `<pk>/recusar/` |
| `apps/requisicoes/templates/requisicoes/fila_autorizacao.html` | Nova tela de fila |
| `apps/requisicoes/templates/requisicoes/detalhe.html` | Ações acessíveis de retorno e recusa |
| `apps/requisicoes/tests/test_policies.py` | Cobertura de permissão |
| `apps/requisicoes/tests/test_selectors.py` | Cobertura de escopo da fila |
| `apps/requisicoes/tests/test_services.py` | Cobertura de transições e timeline |
| `apps/requisicoes/tests/test_views.py` | Contrato HTTP e HTML |

## UX Direction

Direção: **Pragmatic Minimal / Accessible & Ethical**. Interface de trabalho, densa e escaneável, sem cards decorativos, métricas ou gradientes.

Regras aplicadas:
- Fila lista somente itens pendentes; ações acontecem no detalhe.
- Botões textuais explícitos; sem ícones estruturais novos.
- Forms com `<label>`, erro inline, `aria-invalid`, `aria-describedby` e foco visível.
- Tabela semântica com `<caption>`, `<thead>`, `<th scope="col">`.
- Empty state neutro: "Nenhuma requisição aguardando autorização."
- Mobile: tabela com `overflow-x-auto`, preservando número, beneficiário e ação.
- Tailwind com `focus-visible:*`; sem `transition-all`.

## Implementation Order

1. RED selectors/policies: fila por setor, Almoxarifado, superuser e acesso negado.
2. GREEN selectors/policies.
3. RED services: retorno feliz, recusa feliz, motivo obrigatório, estado inválido, permissão negada, estoque inalterado.
4. GREEN services.
5. RED views/templates: fila GET, POST retorno, POST recusa e botões no detalhe.
6. GREEN views/templates.
7. Revisão UI/a11y contra guidelines.
8. `rtk make test`.

## Test Strategy

### Selectors
- Chefe de setor vê somente `aguardando_autorizacao` do setor do beneficiário.
- Chefe de Almoxarifado vê somente setor Almoxarifado.
- Superusuário vê toda a fila de autorização.
- Solicitante, auxiliar de setor, auxiliar de Almoxarifado e usuário inativo recebem queryset vazio.
- Selector inclui contagem de itens e ordena por envio/criação mais antigo primeiro para triagem.

### Policies
- `pode_ver_fila_autorizacao`: chefe de setor, chefe de Almoxarifado e superuser permitidos; demais negados.
- `pode_retornar_para_rascunho`: criador ou beneficiário ativo em `aguardando_autorizacao`; demais negados.
- `pode_recusar_requisicao`: chefe do setor do beneficiário, chefe de Almoxarifado apenas para setor Almoxarifado, superuser permitido.

### Services
- Retorno aplica `aguardando_autorizacao -> rascunho`, preserva `numero_publico`, registra `retorno_rascunho`.
- Retorno restaura visibilidade creator-only por efeito do estado `rascunho` e dos selectors existentes.
- Recusa aplica `aguardando_autorizacao -> recusada`, exige motivo, registra `recusa`.
- Estado inválido lança `EstadoInvalido`.
- Permissão negada lança `PermissaoNegada`.
- Motivo vazio lança `DadosInvalidos`.
- Nenhuma transição altera saldo físico ou reservado.

### Views
- GET `/requisicoes/autorizacoes/` sem login redireciona ao login.
- GET da fila por chefe retorna 200 e renderiza somente requisições autorizáveis.
- GET da fila por ator sem permissão retorna 403.
- POST retorno com permissão redireciona para detalhe e muda estado principal.
- POST recusa com motivo redireciona para detalhe e muda estado principal.
- POST recusa sem motivo re-renderiza detalhe com erro inline ou mensagem de erro sem aplicar transição.
- POST fora de escopo retorna 403.
- HTMX retorna `204` com `HX-Redirect`.

## Invariants

- PER-03: chefe autoriza/recusa somente beneficiários do próprio setor.
- PER-05: superusuário tem permissão operacional total.
- PER-06: setor da requisição é o setor do beneficiário.
- PER-08: views e services chamam a mesma policy contextual.
- REQ-04: retorno e reenvio preservam `numero_publico`.
- REQ-06: após envio, edição direta só volta a ser possível por retorno para rascunho.
- REQ-08: timeline registra eventos principais e visibilidade segue escopo da requisição.
- EST-02: retorno e recusa não criam reserva nem baixa física.
- EST-06: transições rodam sob `transaction.atomic()` e `select_for_update()` na `Requisicao`.

## Risks

- **Modal completo vs. prazo:** o design brief idealiza modal acessível; nesta slice, ações podem usar formulários inline no bloco de ações para manter contrato testável e acessível sem criar componente global amplo.
- **Data enviada:** ainda não há campo dedicado; usar timeline `envio_autorizacao` quando disponível e `atualizado_em/criado_em` como fallback visual.
- **Almoxarifado:** o nome canônico do setor deve vir de `apps.accounts.models.SETOR_NOME_ALMOXARIFADO` se existir; não duplicar string em selector/policy.
- **Erro de recusa sem motivo:** preferir erro inline no detalhe; se a estrutura atual dificultar, usar `messages.error` preservando PRG e sem transição.
- **Branch com worktree sujo:** `.claude/scheduled_tasks.lock` já estava deletado antes da branch; não tocar.
