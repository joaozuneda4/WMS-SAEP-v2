# Plano — Issue #52: flip de contrato de policies (PapelEfetivo)

## Escopo

### O que muda

- Todas as policies passam a receber `PapelEfetivo` + o recurso avaliado; nenhuma recebe `User` como ator.
- `PapelEfetivo` ganha três novos campos que eliminam a dependência de `User` nas policies: `ativo`, `eh_superusuario`, `ator_id`.
- `papel_efetivo()` popula esses campos.
- Políticas de `estoque` que fazem IO direto (`ator.setor_chefiado`) são substituídas por `papel.eh_chefe_de_almoxarifado`.
- Helpers internos `_eh_almoxarifado`, `_setores_escopo_setor`, `_setor_chefiado_ativo` em `requisicoes/policies.py` são removidos — a lógica migra para uso direto dos campos do `PapelEfetivo`.
- Todos os callers (views e services) resolvem `papel_efetivo(ator)` **uma vez** no início do caso de uso e propagam.

### O que NÃO muda

- Assinaturas de services públicos (ainda keyword-only com `ator_id`).
- Recursos avaliados continuam como ORM objects (`Requisicao`, `User` como beneficiário, `Notificacao`) — apenas o ator muda de representação.
- `resolver_escopo_criacao_requisicao` permanece em `requisicoes/policies.py`; define QuerySets lazily, sem executar IO no momento da chamada.
- Comportamento de autorização permanece idêntico.
- `notificacoes/policies.py` não recebia `papel_efetivo` antes — apenas recebe `PapelEfetivo` no flip.

---

## Decisão de design: campos adicionais em `PapelEfetivo`

Policies como `pode_gerir_cadastro`, `pode_editar_rascunho`, `pode_ver_notificacao` precisam de:

| Atributo antes | Campo novo em `PapelEfetivo` |
|---|---|
| `ator.is_active` | `ativo: bool` |
| `ator.is_superuser` | `eh_superusuario: bool` |
| `ator.pk` | `ator_id: int` |

Alternativa descartada: passar `ator_id` e booleans como args separados. Rejeitada por criar assinatura variável entre policies — o envelope `PapelEfetivo` é uniforme.

## Decisão de design: `pode_ser_beneficiario`

`pode_ser_beneficiario(usuario: User)` é chamada em dois contextos:
1. Com o ator (`pode_ser_beneficiario(ator)` em `resolver_escopo_criacao_requisicao`)
2. Com o beneficiário (`pode_ser_beneficiario(beneficiario)` em services)

Após o flip, a assinatura vira `pode_ser_beneficiario(papel: PapelEfetivo) -> bool: return papel.pode_ser_beneficiario`. Para o beneficiário nos services, os callers resolvem `papel_efetivo(beneficiario)` e passam o papel. Alternativamente, o service faz o check inline (`beneficiario.is_active and beneficiario.setor_id is not None`) — válido porque esses são atributos já carregados, sem IO.

**Decisão**: o service `criar_requisicao` e `copiar_requisicao` resolvem `papel_efetivo(beneficiario)` separadamente e passam para `pode_ser_beneficiario`. O ADR-0011 fala "caller resolve papel_efetivo uma vez por caso de uso" no contexto do ator; para o beneficiário, uma segunda chamada é aceitável e explícita.

---

## Arquivos tocados

### `apps/accounts/papeis.py`
- Adicionar campos `ativo: bool`, `eh_superusuario: bool`, `ator_id: int` ao dataclass `PapelEfetivo`.
- Atualizar `papel_efetivo()` para popular os novos campos a partir do `usuario`.

### `apps/accounts/policies.py`
- `pode_gerir_cadastro(ator: User)` → `pode_gerir_cadastro(papel: PapelEfetivo) -> bool`
  - `return papel.ativo and papel.eh_superusuario`
- `exigir_pode_gerir_cadastro` idem.
- Remover import de `User` (usado apenas pela assinatura).

### `apps/accounts/services.py` (4 funções)
- Após carregar `ator`, inserir `papel = papel_efetivo(ator)` e passar `papel` para `exigir_pode_gerir_cadastro`.
- Funções: `trocar_chefe_setor`, `desativar_usuario`, `ativar_vinculo_auxiliar`, `desativar_vinculo_auxiliar`.

### `apps/estoque/policies.py`
- Remover `_eh_almoxarifado`, `_eh_chefe_ou_aux_setor_nao_almox` (helpers internos).
- `pode_registrar_saida_excepcional` — substituir IO direto (`ator.setor_chefiado`) por `papel.eh_chefe_de_almoxarifado`.
- `pode_consultar_historico_scpi` — idem (também faz IO com `ator.setor_chefiado`).
- `pode_consultar_movimentacoes_estoque` — remover chamada interna `papel_efetivo(ator)`, usar `papel` direto.
- Todas as funções: `ator: User` → `papel: PapelEfetivo`.
- Remover imports desnecessários (`ObjectDoesNotExist`, `SetorClassificacao`, `User` da assinatura).

### `apps/estoque/views.py`
- Resolver `papel = papel_efetivo(request.user)` uma vez por view que chama policies.
- Passar `papel` para todos os `exigir_pode_*` e `pode_*` calls.
- Afetadas: `listar_saidas_excepcionais_view`, `registrar_saida_excepcional_view`, `detalhe_saida_excepcional_view`, `estornar_saida_excepcional_view`, `visualizar_preview_scpi_view`, `confirmar_importacao_scpi_view`, `historico_importacoes_scpi_view`, `catalogo_estoque_view`, views de movimentações.

### `apps/notificacoes/policies.py`
- `pode_ver_notificacao(usuario: User, notificacao)` → `pode_ver_notificacao(papel: PapelEfetivo, notificacao)`
  - `return papel.ativo and notificacao.destinatario_id == papel.ator_id`
- `exigir_pode_ver_notificacao` idem.

### `apps/notificacoes/services.py`
- Verificar se chama `pode_ver_notificacao` / `exigir_pode_ver_notificacao`; atualizar se necessário.

### `apps/requisicoes/policies.py`
- Remover helpers `_eh_almoxarifado`, `_setores_escopo_setor`, `_setor_chefiado_ativo`.
- `pode_ser_beneficiario(usuario: User)` → `pode_ser_beneficiario(papel: PapelEfetivo)`
  - `return papel.pode_ser_beneficiario`
- `resolver_escopo_criacao_requisicao(ator: User)` → `(papel: PapelEfetivo)`
  - Usar `papel.ativo`, `papel.eh_superusuario`, `papel.pode_ser_beneficiario`, `papel.eh_almoxarifado`, `papel.setores_em_escopo`.
- `pode_criar_para_beneficiario(ator, beneficiario: User)` → `(papel: PapelEfetivo, beneficiario: User)`
  - Usar `papel.ativo`, `papel.ator_id`, `papel.eh_superusuario`, `papel.eh_almoxarifado`, `papel.setores_em_escopo`.
  - Beneficiário elegível: `beneficiario.is_active and beneficiario.setor_id is not None` (atributos carregados, sem IO).
- Todos os demais `pode_xxx(ator: User, ...)` → `(papel: PapelEfetivo, ...)`.
- Remover `papel_efetivo` do import e do uso interno.
- Remover import de `User` (usado apenas nas assinaturas).

### `apps/requisicoes/views.py`
- Resolver `papel = papel_efetivo(request.user)` uma vez por view que chama policies.
- Views afetadas: `detalhe_requisicao_view`, `criar_requisicao_view`, `editar_rascunho_view`, `copiar_requisicao_view`, `fila_autorizacao_view`, `processar_autorizacao_view`, `fila_atendimento_view`, `separar_retirada_view`, `atender_retirada_view`.

### `apps/requisicoes/services/ciclo_vida.py`
- Após carregar `ator`, inserir `papel = papel_efetivo(ator)` — uma vez por service function.
- Passar `papel` para `exigir_pode_*` calls.
- Para `pode_ser_beneficiario(beneficiario)`: `papel_beneficiario = papel_efetivo(beneficiario)` + `pode_ser_beneficiario(papel_beneficiario)`.
- Funções afetadas: `criar_requisicao`, `editar_rascunho`, `enviar_rascunho`, `retornar_para_rascunho`, `recusar_requisicao`, `autorizar_requisicao`, `estornar_requisicao`.

### `apps/requisicoes/services/atendimento.py`
- Idem: `papel = papel_efetivo(ator)` após carregar ator; passar para `exigir_pode_*`.
- Funções: `separar_para_retirada`, `atender_retirada`, `registrar_devolucao`.

### `apps/requisicoes/services/cancelamento.py`
- Idem.
- Funções: chamadas de `exigir_pode_cancelar_requisicao`.

### `apps/requisicoes/services/copia.py`
- Idem: `papel_ator = papel_efetivo(ator)`, `papel_beneficiario = papel_efetivo(beneficiario)`.
- `exigir_pode_copiar_requisicao(papel_ator, origem)`.
- `pode_ser_beneficiario(papel_beneficiario)`.

### Testes
- `apps/requisicoes/tests/test_policies.py` — atualizar fixtures e chamadas para passar `PapelEfetivo`.
- `apps/accounts/tests/` — atualizar testes de `pode_gerir_cadastro`.
- `apps/estoque/tests/` — atualizar testes de policies de estoque.
- Novos testes de `PapelEfetivo` com campos `ativo`, `eh_superusuario`, `ator_id`.

---

## Estratégia de testes

### Comportamento preservado (contratos existentes mantidos)
Todos os testes existentes em `test_policies.py` devem passar, ajustando apenas a forma de construção do ator: de `User` para `PapelEfetivo` construído sem banco.

### Cenários por categoria

| Cenário | Policy | Verificação |
|---|---|---|
| Superusuário pode tudo | `pode_gerir_cadastro`, `pode_autorizar_requisicao`, etc. | `papel.eh_superusuario=True` → True |
| Inativo bloqueado | qualquer | `papel.ativo=False` → False |
| `ator_id` para identidade | `pode_editar_rascunho`, `pode_ver_notificacao` | `papel.ator_id == recurso.criador_id` |
| Ex-IO policies | `pode_registrar_saida_excepcional`, `pode_consultar_historico_scpi` | `papel.eh_chefe_de_almoxarifado` |
| Beneficiário elegível | `pode_ser_beneficiario` | `papel.pode_ser_beneficiario` |
| Escopo criação | `pode_criar_para_beneficiario` | sem banco, dado puro |

### Negativo (opt-out)
- `pode_gerir_cadastro` com `eh_superusuario=False` → False
- `pode_editar_rascunho` com `ator_id` diferente de `requisicao.criador_id` → False
- Policy chamada com `papel` de usuário inativo → False em todos os casos

---

## Invariantes relevantes

Da `docs/matriz-invariantes.md` (se existir):
- Autorização de atores nunca muda entre verificação e execução na mesma transação → `PapelEfetivo` como snapshot é consistente com esse invariante.
- Services carregam ator internamente (ADR-0011) → `papel = papel_efetivo(ator)` no service, nunca na view passando para o service.

---

## Riscos

| Risco | Mitigação |
|---|---|
| Views com múltiplas chamadas de policy para o mesmo `request.user` podem esquecer de reutilizar `papel` | A revisão verifica uniformidade: `papel_efetivo` deve aparecer apenas uma vez por view function |
| `papel_efetivo(beneficiario)` chamado em services é uma query extra por request | Aceito — o ADR fala "caller resolve uma vez" para o ator; beneficiário é caso diferente e documentado |
| Testes de policy que constroem `User` com `create_user` podem não precisar mais do banco | Migrar para `PapelEfetivo(...)` sem banco: testes ficam mais rápidos e sem DB |
| `pode_copiar_requisicao` delega para `pode_criar_para_beneficiario` — beneficiário vem de `requisicao.beneficiario` (FK) | Caller deve garantir `requisicao.beneficiario` carregado via `select_related` antes da policy call |
| Assinatura mista User/PapelEfetivo inadvertida | Ruff + revisão de PR: grep por `def pode_` com `User` como primeiro arg após o flip |
