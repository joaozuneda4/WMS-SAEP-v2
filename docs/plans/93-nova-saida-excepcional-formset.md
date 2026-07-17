# Plano: #93 — Migrar `nova_saida_excepcional` pro paradigma HTMX formset (ADR-0016)

## Scope

**Inclui:**
- `ItemSaidaExcepcionalForm` + `BaseItemSaidaExcepcionalFormSet` (novo `apps/estoque/forms.py`), espelhando `ItemRequisicaoForm`/`BaseItemRequisicaoFormSet` (`apps/requisicoes/forms.py`)
  - `quantidade` como `DecimalField` (baixa é sobre `saldo_fisico`, que é decimal — diferente de `quantidade_solicitada` inteira de requisições)
  - `clean()` do form: material + quantidade > 0 obrigatórios quando linha preenchida (linha vazia é ignorada, mesma regra de `is_linha_valida`)
  - `clean()` do formset: duplicidade de material (SAE-03) e elegibilidade (`ativo=True` + `saldo_fisico > 0`, mesmo critério de `buscar_materiais_saida_excepcional`) — erro anexado à linha específica, não a um dict `erros` solto
- Endpoint HTMX `nova_linha_item_saida_excepcional` em `apps/estoque/views.py` + rota em `apps/estoque/urls.py`, espelhando `requisicoes:nova_linha_item`
- `SaidaExcepcionalForm` novo em `apps/estoque/forms.py` para o cabeçalho (`motivo` `ChoiceField` com `MOTIVO_SAIDA_OPCOES`, `observacao` `CharField` obrigatório) — substitui a validação manual de `motivo`/`observação` em dict, seguindo o mesmo padrão de `RequisicaoForm`
- `nova_saida_excepcional_view` reescrita seguindo exatamente o padrão de `nova_requisicao` (`apps/requisicoes/views.py:229-298`): `form.is_valid() and formset.is_valid()` decide se chama `registrar_saida_excepcional`; dentro do `try`, `except DadosInvalidos as exc: messages.error(request, str(exc))` e `except ConflitoDominio as exc: messages.warning(request, str(exc))` (mapeamento padrão de `docs/CONVENTIONS.md`) — sem redirect nesses `except`, cai no mesmo `return render(..., {'form': form, 'formset': formset, ...})` do fluxo de erro de formulário (mesma request, sem necessidade de PRG); no `else` do `try`, sucesso dispara `messages.success(...)` e `htmx_redirect(request, reverse('estoque:listar_saidas_excepcionais'))` (import de `apps.core.http.htmx_redirect`, já usado em `apps/requisicoes/views.py`) em vez do `redirect()` cru atual
- Extração do partial de linha de item para `apps/core/templates/components/item_form_row.html` (diretório já usado por `button.html`, `badge.html`, `autocomplete.html` — sem underscore, componente incluído diretamente, não partial interno) parametrizado por: endpoint de autocomplete, `item_template` do autocomplete, nome/prefixo dos campos, `step`/`decimal_places` da quantidade, label da quantidade, e `saldo_info` opcional (dict por material, mesma forma usada em requisições)
  - `apps/requisicoes/templates/requisicoes/rascunho_form.html` e `apps/requisicoes/views.py` (`nova_linha_item`) passam a incluir o partial compartilhado — requer regressão manual da tela de requisições (ver Test strategy)
- `apps/estoque/templates/estoque/nova_saida_excepcional.html` reescrito: `{{ formset.management_form }}`, loop `{% for item_form in formset %}` incluindo o partial compartilhado, botão "Adicionar material" via `hx-get` para o novo endpoint (idêntico ao padrão de `rascunho_form.html`)
- JS da tela (`novaSaidaExcepcional()` Alpine): mantém `selecionarMaterial` como veto instantâneo client-side (feedback otimista), mas deixa de ser a única fonte de verdade — o `clean()` do formset é quem decide de fato (ADR-0016, decisão vigente mesmo com PR aceito ainda não mergeada). Ajusta a função para trabalhar sobre linhas do formset em vez do array `itens` local
- `apps/estoque/tests/test_views.py::TestNovaSaidaExcepcionalView`: reescreve os testes que hoje leem `response.context['erros']` para o contrato de formset (`response.context['formset'].errors` / `non_form_errors`); adiciona os 3 cenários exigidos pelo escopo da issue: item duplicado, quantidade inválida, material inelegível — todos via formset, não via service

**Não inclui:**
- Mudança de regra de domínio em `registrar_saida_excepcional`, `exigir_pode_registrar_saida_excepcional` ou `buscar_materiais_saida_excepcional` (services/policies/selectors intocados, só a view muda como os chama)
- Estorno de saída excepcional
- Novo componente de design system além do partial de linha de item já pedido pela issue (badge, button, etc. são issues próprias do épico #68)
- Dependência nova (`django-formtools` ou similar) — `formset_factory` puro, igual a requisições

## Files touched

| Arquivo | Ação |
|---|---|
| `apps/estoque/forms.py` | Create — `SaidaExcepcionalForm`, `ItemSaidaExcepcionalForm`, `BaseItemSaidaExcepcionalFormSet`, `ItemSaidaExcepcionalFormSet` |
| `apps/estoque/views.py` | Update `nova_saida_excepcional_view`; add `nova_linha_item_saida_excepcional_view` |
| `apps/estoque/urls.py` | Add rota da nova linha |
| `apps/estoque/templates/estoque/nova_saida_excepcional.html` | Rewrite — formset em vez de array Alpine |
| `apps/core/templates/components/item_form_row.html` | Create — extraído/parametrizado a partir de `requisicoes/partials/_item_form_row.html` |
| `apps/requisicoes/templates/requisicoes/rascunho_form.html` | Update — passa a incluir o partial compartilhado |
| `apps/requisicoes/views.py` | Update — `nova_linha_item` aponta pro partial compartilhado (mesmos parâmetros) |
| `apps/estoque/tests/test_views.py` | Update `TestNovaSaidaExcepcionalView` + novos casos |
| `apps/estoque/tests/test_forms.py` | Create — testes do formset isolados (duplicidade, quantidade, elegibilidade) |
| `apps/requisicoes/tests/test_views.py` | Regression check — garantir que a extração do partial não quebra `rascunho_form` |

## Test strategy

| Caso | Tipo |
|---|---|
| Formset válido com 1+ linha → `linhas_validas()` retorna dicts corretos | form |
| Linha vazia (sem material nem quantidade) → ignorada, não gera erro | form |
| Material duplicado entre duas linhas → erro anexado à 2ª linha + `ValidationError` no formset | form |
| Quantidade <= 0 ou ausente com material preenchido → erro na linha | form |
| Material inativo ou sem saldo (`saldo_fisico <= 0`) → erro de elegibilidade na linha | form |
| Nenhuma linha válida → erro geral do formset | form |
| GET `/nova/` → 200, formset com 1 linha inicial vazia (`extra=0`, `initial=[{}]`, mesmo truque de `nova_requisicao`) | view |
| POST não-HTMX válido → 302 para `listar_saidas_excepcionais` + `SaidaExcepcional` criada (mantém teste existente) | view |
| POST HTMX válido → resposta 204 com header `HX-Redirect` + `SaidaExcepcional` criada | view |
| POST sem motivo → 200, erro em `form.errors['motivo']` (form de cabeçalho, não mais dict `erros`) | view |
| POST sem itens → 200, erro em `formset.non_form_errors()` | view |
| POST com item duplicado → 200, erro na linha correspondente (`formset.errors[i]`) | view |
| POST com quantidade inválida → 200, erro na linha correspondente (`formset.errors[i]`) | view |
| POST com material inelegível (inativo/sem saldo) → 200, erro na linha correspondente (`formset.errors[i]`) | view |
| Service levanta `ConflitoDominio` após formset válido (race de saldo) → 200, `messages.warning` renderizado, formset re-exibido | view |
| GET endpoint nova linha → 200, partial HTML com form vazio no índice pedido | view |
| Permissões (403 aux/solicitante, 302 anônimo) — mantém cobertura atual | view |
| `rascunho_form.html` renderiza e submete igual após extração do partial | view (regressão, requisições) |

## Invariants

- SAE-03 — duplicidade de material e documento vazio, agora garantidos também no `clean()` do formset (antes só no service)
- SAE-05 — baixa de `saldo_fisico`, sem tocar `saldo_reservado` — inalterado, service não muda
- SAE-09 — motivo fechado (enum) e observação obrigatória — agora validados via `SaidaExcepcionalForm` (`forms.py`), não mais dict manual na view (correção de escopo pós-review: `docs/CONVENTIONS.md` exige validação de input em `forms.py`, view fina)
- ADR-0016 — paradigma único formset server-side; guarda de domínio no `clean()`, JS só como replicação de feedback, nunca fonte única

## Risks

- ADR-0016 ainda não está mergeada em `main` (PR joaozuneda4/WMS-SAEP-v2#10 aberto) — a decisão já está confirmada no comentário de fechamento da issue #82 (HITL), então a migração não fica bloqueada por isso, mas o link do ADR no plano aponta pra um arquivo que só existe nessa branch até lá
- Extrair o partial de linha de item toca `requisicoes/rascunho_form.html`, tela em produção — regressão manual + suíte de `apps/requisicoes` obrigatória antes de considerar a issue pronta
- Duplo veto (JS + formset) de duplicidade é a decisão confirmada com o usuário (paridade de comportamento), mas mantém lógica de duplicidade em 2 lugares — se divergirem no futuro, o formset é a fonte de verdade
- `clean()` do formset consulta `Material`/`SaldoEstoque` para elegibilidade — evitar N+1: usar um único `filter(pk__in=...)` para todos os `material_id` do formset, não uma query por linha
- Elegibilidade validada no `clean()` (checagem otimista) não elimina a validação equivalente no service (`material_inativo`, `saldo_insuficiente` em `registrar_saida_excepcional`) — entre o `clean()` e o `select_for_update()` do service o estado pode mudar (race genuína); por isso o `except ConflitoDominio` na view continua necessário mesmo com o formset validando elegibilidade
