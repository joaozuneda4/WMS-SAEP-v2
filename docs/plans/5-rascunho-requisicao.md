# Plano: Criar rascunho de requisição (#5)

## Scope

**Inclui:**
- TR-001: criar requisição (N/A → rascunho)
- TR-002: editar rascunho (rascunho → rascunho)
- Autocomplete HTMX de materiais
- Form + formset de itens com add/remove dinâmico via HTMX
- Policy de escopo de criação por papel efetivo
- `transitions.py` mínimo (RASCUNHO→RASCUNHO)
- Testes: `test_policies.py`, `test_services.py`, `test_forms.py`, `test_views.py`

**Não inclui:**
- TR-005 (enviar para autorização)
- TR-003/TR-004 (descartar/cancelar rascunho)
- View de detalhe e lista
- Top nav (pré-existente ou separado)

## Files Touched

| Arquivo | Operação |
|---|---|
| `apps/requisicoes/transitions.py` | Criar |
| `apps/requisicoes/policies.py` | Criar |
| `apps/requisicoes/services.py` | Criar |
| `apps/requisicoes/forms.py` | Criar |
| `apps/requisicoes/views.py` | Preencher (estava vazio) |
| `apps/requisicoes/urls.py` | Criar |
| `apps/requisicoes/selectors.py` | Criar (busca de materiais) |
| `apps/requisicoes/tests/__init__.py` | Criar |
| `apps/requisicoes/tests/conftest.py` | Criar |
| `apps/requisicoes/tests/test_policies.py` | Criar |
| `apps/requisicoes/tests/test_services.py` | Criar |
| `apps/requisicoes/tests/test_forms.py` | Criar |
| `apps/requisicoes/tests/test_views.py` | Criar |
| `apps/requisicoes/templates/requisicoes/rascunho_form.html` | Criar |
| `apps/requisicoes/templates/requisicoes/partials/_item_form_row.html` | Criar |
| `config/urls.py` | Incluir `apps.requisicoes.urls` |

## Implementation Order

1. `transitions.py` — tabela declarativa mínima
2. `policies.py` — `resolver_escopo_criacao_requisicao`, `pode_ser_beneficiario`, `pode_criar_para_beneficiario`, `pode_editar_rascunho` + `exigir_*`
3. `selectors.py` — `materiais_para_requisicao(q)` → queryset filtrado
4. `services.py` — `criar_requisicao`, `editar_rascunho`
5. `forms.py` — `RequisicaoForm`, `ItemRequisicaoFormSet`
6. `views.py` + `urls.py` — `nova_requisicao`, `editar_rascunho_view`, `nova_linha_item`, `buscar_materiais`
7. Templates
8. Testes
9. `config/urls.py` — incluir namespace `requisicoes`

## Test Strategy

### `test_policies.py` (chamada direta, banco real)
- `resolver_escopo_criacao_requisicao`: solicitante puro → modo=proprio; ator sem setor → PermissaoNegada; chefe setor não-almox → modo=setor; aux setor não-almox → modo=setor; aux almox → modo=qualquer; chefe almox → modo=qualquer; ator com papel mas sem setor → pode_criar_para_si=False
- `pode_ser_beneficiario`: ativo+setor→True; inativo→False; sem setor→False
- `pode_editar_rascunho`: criador+rascunho→True; não-criador→False; estado≠rascunho→False
- Precedência de múltiplos papéis: chefe setor + aux almox → modo=qualquer

### `test_services.py` (3 casos/transição)
**TR-001 `criar_requisicao`:**
- Feliz: estado=RASCUNHO, numero_publico=None, setor_beneficiario=snapshot, timeline evento=criacao
- PermissaoNegada: ator cria para beneficiário fora do escopo
- DadosInvalidos: material inativo / divergente / sem saldo / qtd≤0 / beneficiário sem setor / sem itens

**TR-002 `editar_rascunho`:**
- Feliz: itens atualizados, observação salva, timeline evento=edicao (se houver)
- PermissaoNegada: não-criador
- EstadoInvalido: estado≠RASCUNHO

### `test_forms.py`
- Duplicidade de material → erro inline na linha duplicada
- Linha DELETE ignorada na validação de duplicidade
- Formset sem linha válida → erro mínimo 1 item

### `test_views.py` (contrato HTTP)
- GET /nova/ sem login → 302 login
- GET /nova/ → 200
- POST válido → 302 /`<pk>`/editar/ + mensagem sucesso
- POST inválido → 200 + erros no form
- POST forjado (beneficiário fora de escopo) → 200 + messages.error
- GET /`<pk>`/editar/ sem login → 302 login
- GET /`<pk>`/editar/ não-criador → 403
- GET /`<pk>`/editar/ estado≠rascunho → 403
- POST /`<pk>`/editar/ válido → 302 /`<pk>`/editar/ + mensagem
- POST /`<pk>`/editar/ material inativo → 200 + messages.error

## Invariants (desta entrega)

| ID | Verificação |
|---|---|
| REQ-01 | `criar_requisicao` → estado=RASCUNHO |
| REQ-02 | `criar_requisicao` → numero_publico=None |
| REQ-05 | Bloquear criação e edição sem ao menos 1 item |
| REQ-07 | Registrar criador, beneficiário, setor_beneficiario snapshot |
| REQ-08 | Timeline evento `criacao` registrado |
| PER-01 | Solicitante cria apenas para si |
| PER-02 | Aux setor cria apenas dentro do próprio setor |
| PER-04 | Almoxarifado cria para qualquer usuário |
| PER-06 | setor_beneficiario = setor do beneficiário, nunca do criador |
| PER-08 | View e service chamam a mesma policy |
| EST-08 | Material divergente bloqueia criação |
| EST-10 | Material inativo bloqueia criação |
| USR-01 | Beneficiário inativo negado |

## Risks

- `setor_chefiado` (reverse OneToOne) lança `RelatedObjectDoesNotExist` se ator não é chefe — usar `hasattr` ou `try/except`
- Formset management form (`TOTAL_FORMS`) deve ser atualizado via HTMX swap ao adicionar linha
- Autocomplete endpoint deve exigir login — não expor saldo sem autenticação
- `setor_beneficiario` é snapshot imutável — service não deve aceitar `setor_beneficiario_id` em edição
