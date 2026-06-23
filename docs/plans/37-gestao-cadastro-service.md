# Plano: Gestão de cadastro por service — #37

## Escopo

### O que muda
- Novos services em `apps/estoque/services.py`: `desativar_material`
- Novo módulo `apps/accounts/services.py` com: `trocar_chefe_setor`, `desativar_usuario`, `ativar_vinculo_auxiliar`, `desativar_vinculo_auxiliar`
- Proteção do admin: `apps/accounts/admin.py` e `apps/estoque/admin.py` sobrescrevem `save_model` / `delete_model` para chamar os services correspondentes, restringindo operações sensíveis a superusuário e aplicando validações de domínio
- Testes: `apps/estoque/tests/test_services.py` (novos casos), novo `apps/accounts/tests/test_services.py`

### O que NÃO muda
- UI completa de CRUD de usuários (fora de escopo explícito da issue)
- SCIM/SSO
- Models (nenhuma alteração de schema — logo, sem nova migration local)
- Quaisquer outros services de estoque já implementados

## Decisão humana resolvida

Gestão via **Django admin restrito** com validação em `save_model()` (delegando aos services). Admin de material (`MaterialAdmin`) e admin de usuário/setor/vínculo (`UserAdmin`, `SetorAdmin`, `VinculoAuxiliarAdmin`) chamarão os services ao salvar objetos. Operações sensíveis só acessíveis a superusuário.

## Arquivos tocados

| Arquivo | Ação |
|---------|------|
| `apps/estoque/services.py` | Adicionar `desativar_material` |
| `apps/accounts/services.py` | Criar com `trocar_chefe_setor`, `desativar_usuario`, `ativar_vinculo_auxiliar`, `desativar_vinculo_auxiliar` |
| `apps/accounts/policies.py` | Criar com `pode_gerir_cadastro`, `exigir_pode_gerir_cadastro` (superusuário ou staff designado) |
| `apps/estoque/admin.py` | Sobrescrever `save_model` em `MaterialAdmin` para chamar `desativar_material` ao desativar |
| `apps/accounts/admin.py` | Sobrescrever `save_model` em `SetorAdmin`, `UserAdmin`, `VinculoAuxiliarAdmin` para delegar aos services; restringir acesso a superusuário |
| `apps/estoque/tests/test_services.py` | Adicionar casos EST-11 |
| `apps/accounts/tests/test_services.py` | Criar com casos USR-04, USR-05, USR-07 e vínculo auxiliar |

## Estratégia de teste (ADR-0010)

Cada behavior é um RED → GREEN → REFACTOR. Sem factory_boy. Testes criam dados diretamente via ORM. Fixtures locais em cada `test_*.py` ou `conftest.py` de app.

### Casos EST-11

| Caso | Saldo | Esperado |
|------|-------|----------|
| `desativar_material` com `saldo_fisico > 0` | físico=10, reservado=0 | `ConflitoDominio` code=`saldo_fisico_nao_zerado` |
| `desativar_material` com `saldo_reservado > 0` | físico=0, reservado=5 | `ConflitoDominio` code=`saldo_reservado_nao_zerado` |
| `desativar_material` com ambos zerados | físico=0, reservado=0 | `material.ativo == False` |
| `desativar_material` já inativo | físico=0, reservado=0 | idempotente (retorna sem erro) |

### Casos USR-04 / USR-05 — `trocar_chefe_setor`

| Caso | Esperado |
|------|----------|
| Novo chefe ativo, do setor, sem chefia atual | OK — `setor.chefe = novo_chefe` |
| Novo chefe inativo | `DadosInvalidos` code=`chefe_inativo` |
| Novo chefe de outro setor | `DadosInvalidos` code=`chefe_setor_errado` |
| Novo chefe já chefia outro setor | `ConflitoDominio` code=`chefe_duplicado` |

### Casos USR-07 — `desativar_usuario`

| Caso | Esperado |
|------|----------|
| Usuário chefe de setor ativo sem novo chefe | `ConflitoDominio` code=`usuario_chefe_sem_substituto` |
| Usuário chefe, fornecido `novo_chefe_id` válido | Troca chefe e desativa usuário |
| Usuário não é chefe de nenhum setor ativo | Desativa normalmente |
| Usuário já inativo | idempotente |

### Casos VinculoAuxiliar

| Caso | Esperado |
|------|----------|
| `ativar_vinculo_auxiliar` novo (usuario+setor sem vínculo ativo) | Cria `VinculoAuxiliar` com `ativo=True` |
| `ativar_vinculo_auxiliar` já ativo | `ConflitoDominio` code=`vinculo_ja_ativo` |
| `desativar_vinculo_auxiliar` ativo | `ativo=False`, `desativado_em` preenchido |
| `desativar_vinculo_auxiliar` já inativo | `ConflitoDominio` code=`vinculo_ja_inativo` |

## Invariantes cobertos

| ID | Reforçado em |
|----|-------------|
| EST-11 | `desativar_material` — valida saldo zerado antes de `ativo=False` |
| USR-04 | `trocar_chefe_setor` — valida que novo chefe é ativo |
| USR-05 | `trocar_chefe_setor` — `Setor.chefe` é `OneToOneField` (constraint DB), service valida previamente |
| USR-07 | `desativar_usuario` — bloqueia desativação de chefe de setor ativo sem substituto |

## Proteção do admin

- `MaterialAdmin.save_model`: se `ativo` mudou de `True` para `False`, chama `desativar_material(ator_id=request.user.pk, material_id=obj.pk)` dentro de try/except traduzindo `ErroDominio` para `ValidationError`.
- `SetorAdmin.save_model`: se `chefe` mudou, chama `trocar_chefe_setor(...)`.
- `UserAdmin.save_model`: se `is_active` mudou para `False`, chama `desativar_usuario(...)`.
- `VinculoAuxiliarAdmin.save_model`: se `ativo` mudou, chama `ativar_vinculo_auxiliar` / `desativar_vinculo_auxiliar`.
- Acesso às operações sensíveis limitado a `request.user.is_superuser`.

## Riscos

- `Setor.chefe` é `OneToOneField` — constraint DB já garante USR-05. Service valida antecipadamente para mensagem de erro legível.
- `desativar_usuario` precisa chamar `trocar_chefe_setor` internamente para desativar com substituição — garantindo que as duas operações ficam numa transação.
- Admin não usa `save()` diretamente para a desativação de material; todo o comportamento sensível passa pelo service para respeitar ADR-0011.
