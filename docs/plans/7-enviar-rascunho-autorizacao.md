# Plano: Enviar rascunho para autorização com número público (#7)

## Scope

**Inclui:**
- Service `enviar_para_autorizacao(*, ator_id, requisicao_id)` em `apps/requisicoes/services.py` — TR-005, RASCUNHO → AGUARDANDO_AUTORIZACAO.
- Helper interno `_emitir_numero_publico_se_necessario(requisicao, ano)` — usa `SequenciaRequisicao` com `select_for_update`, formato `REQ-AAAA-NNNNNN`, idempotente em reenvio.
- Policy `pode_enviar_rascunho(ator, requisicao)` + `exigir_pode_enviar_rascunho` em `policies.py` — apenas criador ativo (paridade com `pode_editar_rascunho`).
- Atualizar `TRANSICOES_VALIDAS` em `transitions.py`: `rascunho` agora também pode ir para `aguardando_autorizacao`.
- View `enviar_rascunho_view` (POST only) em `views.py`, com `_htmx_redirect` para detalhe após sucesso.
- URL `requisicoes/<int:pk>/enviar/` em `urls.py`.
- UI: botão "Enviar para autorização" no `detalhe.html`, visível apenas quando `pode_enviar_rascunho` (criador + estado `rascunho`). Inline `<form method="post">`.
- Testes:
  - `test_services.py`: caminho feliz emite `REQ-AAAA-NNNNNN`, sequência incrementa, reenvio preserva número, requisição sem itens bloqueia, estado inválido lança `EstadoInvalido`, criador inativo lança `PermissaoNegada`, terceiro lança `PermissaoNegada`, timeline `envio_autorizacao` registrada.
  - `test_policies.py`: criador True; terceiro False; criador inativo False; estado != rascunho ignorado pela policy (responsabilidade do service via transitions).
  - `test_views.py`: GET retorna 405; POST sem login → 302; POST não-criador → 403; POST sucesso → 302 detalhe + mensagem.

**Não inclui:**
- TR-006 (retorno_rascunho), TR-008 (autorizar), TR-011 (recusar), TR-012 (cancelar antes da autorização). Issues separadas.
- Fila do chefe (`/requisicoes/fila/autorizacao/`). Issue separada.
- Notificação ao chefe (side-effect `transaction.on_commit`). Fora desta issue — placeholder não criado.

## Files Touched

| Arquivo | Operação |
|---|---|
| `apps/requisicoes/transitions.py` | Adicionar destino `AGUARDANDO_AUTORIZACAO` para `RASCUNHO` |
| `apps/requisicoes/policies.py` | `pode_enviar_rascunho`, `exigir_pode_enviar_rascunho` |
| `apps/requisicoes/services.py` | `enviar_para_autorizacao`, `_emitir_numero_publico_se_necessario` |
| `apps/requisicoes/views.py` | `enviar_rascunho_view` |
| `apps/requisicoes/urls.py` | Rota `<int:pk>/enviar/` |
| `apps/requisicoes/templates/requisicoes/detalhe.html` | Botão de envio quando aplicável |
| `apps/requisicoes/tests/test_services.py` | Cobertura do envio |
| `apps/requisicoes/tests/test_policies.py` | Cobertura da policy |
| `apps/requisicoes/tests/test_views.py` | Cobertura da view |

## Implementation Order

1. `transitions.py` — adicionar destino.
2. `policies.py` — `pode_enviar_rascunho` + `exigir_*`.
3. `services.py` — `enviar_para_autorizacao` + helper de numeração.
4. `urls.py` + `views.py` — rota + view POST com PRG/HX-Redirect.
5. `detalhe.html` — botão.
6. Tests por camada.
7. `rtk make test` — confirmar verde antes de PR.

## Numeração pública — ADR-0003

- `SequenciaRequisicao.objects.select_for_update().get_or_create(ano=ano)` dentro da mesma `transaction.atomic` da transição.
- `ultimo_numero += 1`; persiste; formata `REQ-{ano}-{seq:06d}`.
- Emite somente quando `requisicao.numero_publico is None` → reenvio preserva.
- `ano` derivado de `timezone.now().year` (UTC default; sem fuso explícito — alinhar com ADR se diferir).

## Concorrência — ADR-0005

- Service recebe `requisicao_id` (não instância).
- `Requisicao.objects.select_for_update().get(pk=...)` — lock antes de qualquer leitura.
- `verificar_transicao_valida(requisicao.estado, AGUARDANDO_AUTORIZACAO)` sob lock.
- Itens revalidados (≥ 1) sob lock (matriz REQ-05).
- Sem lock de saldo: envio não toca estoque (TR-005 / EST-02).

## Test Strategy

### Service (`test_services.py`)
- `test_enviar_emite_numero_publico_no_primeiro_envio`: novo rascunho → estado vira `aguardando_autorizacao`, `numero_publico` `REQ-AAAA-NNNNNN`, timeline `envio_autorizacao`.
- `test_sequencia_anual_incrementa`: dois envios no mesmo ano → sequências 1 e 2.
- `test_reenvio_preserva_numero_publico`: enviar → retornar para rascunho via manipulação direta (preserva número; nesta issue, sem TR-006, simular setando `estado='rascunho'` e `numero_publico` preservado manualmente, depois re-enviar) → mantém mesmo número.
- `test_envio_sem_itens_bloqueia`: requisição sem itens → `DadosInvalidos('sem_itens')`. (Cria estado inconsistente artificialmente porque `criar_requisicao` exige itens.)
- `test_envio_em_estado_invalido`: estado `aguardando_autorizacao` → `EstadoInvalido`.
- `test_envio_por_terceiro_negado`: `PermissaoNegada`.
- `test_envio_por_inativo_negado`: criador inativado → `PermissaoNegada`.
- `test_envio_nao_reserva_estoque`: saldo reservado do material não muda.

### Policy (`test_policies.py`)
- Criador ativo → True.
- Terceiro → False.
- Criador inativo → False.

### View (`test_views.py`)
- GET na rota → 405.
- POST sem login → redirect login.
- POST criador → 302 (ou 204 + HX-Redirect) para detalhe; mensagem sucesso.
- POST não-criador → 403.
- POST estado inválido → 302 detalhe + `messages.error`.

## Invariants

- REQ-03: Número público `REQ-AAAA-NNNNNN` nasce no primeiro envio.
- REQ-04: Reenvios preservam número.
- REQ-05: Ao menos um item ao enviar.
- REQ-08: Timeline registra `envio_autorizacao`.
- EST-02 / EST-06: Envio não cria reserva nem baixa físico.
- ADR-0005: `select_for_update` na `Requisicao`; service recebe `requisicao_id`.
- ADR-0003: numeração via `SequenciaRequisicao` na mesma transação.
- ADR-0011: assinatura keyword-only; ator_id; exceções de domínio.

## Risks

- **Ano vs. timezone**: usar `django.utils.timezone.now().year` para evitar divergência entre worker UTC e ano fiscal local. Se já houver convenção, alinhar.
- **Reenvio sem TR-006 implementada**: ainda não há retorno_rascunho oficial; teste de reenvio precisa simular preservação via manipulação direta (`estado='rascunho'` mantendo `numero_publico`). Não inclui TR-006 no service.
- **Botão na UI**: cuidado para não exibir botão em estado != rascunho — gate por `requisicao.estado == 'rascunho' and request.user.id == requisicao.criador_id`. Avaliar uso de `pode_enviar_rascunho` em template; sem context processor, expor flag no contexto do view de detalhe.
- **Concorrência num envio simultâneo**: duas requisições do mesmo ano enviadas simultaneamente — `select_for_update` na linha de `SequenciaRequisicao` serializa.

## Out of Scope para UI rica

Botão único primário-`amber` no detalhe, sem modal de confirmação nesta fase (rascunho descartável; nenhuma transição é destrutiva). Mensagem PRG na lista de minhas requisições e detalhe.
