# Plano — #94: Padronizar botões para `components/button.html`

## Escopo

**Muda:**
- Todos os botões `primary` (azul sólido) e `danger`/`danger-outline` (vermelho) implementados com classes Tailwind cruas nos 9 arquivos listados na issue passam a usar `{% include "components/button.html" with variant=... %}`.
- `apps/core/templates/components/button.html` ganha suporte a passthrough adicional, necessário porque vários botões cru têm comportamento dinâmico que o componente hoje não cobre:
  - `icon_class` (opcional, default `"h-4 w-4"`) — classe repassada ao `icon_template` incluído (hoje o `icon_template` nunca foi usado em produção; sem isso, `{{ class }}` dentro do parcial de ícone resolveria para o `class` do próprio botão em vez de um tamanho de ícone).
  - `loading_label` (opcional) — padrão `data-submit-loading-label` / `data-submit-text` já usado pelo `form-submit.js` (anti-duplo-submit). Quando presente, o `label` é envolvido em `<span data-submit-text>` e o atributo `data-submit-loading-label` é emitido. `form-submit.js` também sabe exibir `[data-submit-spinner]`, mas nenhum dos botões convertidos com `loading_label` (`rascunho_form.html`, `nova_saida_excepcional.html`) tem esse elemento hoje — não implementado agora (YAGNI); se um caller futuro precisar de spinner + `loading_label` juntos, estender então.
  - `label_mobile` (opcional) — quando presente junto de `loading_label`, renderiza dois `<span data-submit-text>` (um `hidden sm:inline`, outro `sm:hidden`) em vez de um único label — cobre o botão "Criar e enviar" de `rascunho_form.html`, que hoje tem rótulo responsivo diferente para mobile/desktop.
  - `x_disabled` / `x_aria_busy` (opcionais, expressão Alpine) — emitem `:disabled="..."` / `:aria-busy="..."` no lugar do `disabled` estático, para os botões que usam `x-data`/Alpine para estado de loading em vez do `form-submit.js`.
  - `label_bind` (opcional, expressão Alpine) — envolve o label em `<span x-text="...">{{ label }}</span>`, preservando o texto estático original como fallback pré-hidratação.
  - `spinner_show` (opcional, expressão Alpine) — quando presente, renderiza `{% icon "spinner" %}` num `<span x-show="...">` antes do ícone/label, e — se `icon_template` também estiver setado — envolve esse ícone em `x-show="!(...)"` (o ícone "idle" some durante o loading, o spinner aparece).
  - Escopo dos params novos: `loading_label`/`label_mobile`/`x_disabled`/`x_aria_busy`/`spinner_show`/`label_bind` só têm efeito no ramo `<button>` de `button.html` (o ramo `<a>` não tem `disabled` nem faz sentido ter loading state). Nenhum dos botões convertidos neste plano usa esses params com `href` setado. Precedência: se `x_disabled` for passado, ele substitui o `disabled` estático (não emite os dois); nenhum botão convertido aqui usa as duas formas ao mesmo tempo.
- 3 ícones novos no catálogo vendorizado (`apps/core/templatetags/core_tags.py` `ICONES_CATALOGO` + `apps/core/templates/components/icons/*.svg`), extraídos de SVGs inline hoje embutidos nos botões convertidos, porque os paths não são idênticos ao ícone `lixeira` já cadastrado nem entre si:
  - `confirmar` — check usado em `nova_saida_excepcional.html` (ícone estático, sempre visível).
  - `confirmar_check` — check usado em `preview_importacao_scpi.html` (ícone condicional, escondido durante loading).
  - `estornar` — lixeira usada no botão "Estornar requisição" de `detalhe.html` (path diferente do `lixeira` cadastrado — variante mais detalhada).
- Consistência danger vs danger-outline (critério 3 da issue): todo trigger que **abre** modal/diálogo de confirmação vira `danger-outline`; a ação final dentro do modal já usa `bg-danger` sólido via `components/_modal_body.html` (não listado na issue, não alterado — é a referência do padrão correto).

**NÃO muda:**
- Botões `secondary` (borda slate, ex: "Cancelar" simples, "Editar rascunho", "Repetir requisição", "Voltar para a lista", "Limpar") — não usam `bg-blue-600`/`bg-red-600`, fora do critério de aceite literal ("nenhuma classe bg-blue-600, bg-red-600 etc"), e o `variant="secondary"` já teria de ser normalizado seguindo um padrão de padding/ícone diferente não pedido pela issue.
- Botão "Retornar para rascunho" em `detalhe.html` (âmbar) — não é primary nem danger, `button.html` não tem variant âmbar/warning.
- Botões-link estilo texto ("Adicionar material"/"Adicionar item", `text-blue-600 hover:text-blue-800`, sem background) em `rascunho_form.html` e `nova_saida_excepcional.html` — não são `bg-blue-600`, usam `hx-vals`/`hx-include`/handler de evento customizado que `button.html` não suporta, e não estão nas linhas citadas pela issue.
- `components/modal.html` / `components/_modal_body.html` — não estão na lista de arquivos da issue; já usam tokens (`bg-primary`/`bg-danger`), é o padrão de referência.
- Padding/border-radius exatos de cada botão cru (ex: `px-4 py-2.5 rounded-lg` vs `rounded-lg` com `gap-2`) — ao consolidar no componente compartilhado, o botão passa a usar o padding/raio padrão de `button.html` (`px-3 py-2`, `rounded-md`). Isso é o resultado esperado de "padronizar" (a própria issue nasce da divergência de padding entre telas); cor, ícone, texto, estados de loading/disabled e comportamento continuam idênticos. Documentado aqui para review explícito.
- Classes de pseudo-estado `disabled:` (ex: `login.html` usa `disabled:cursor-wait disabled:opacity-75`, `button.html` já embute `disabled:cursor-not-allowed disabled:opacity-60`) — padroniza para o valor do componente, mesma lógica do ponto acima.

## Arquivos alterados

| Arquivo | Botões convertidos | Novo param usado |
|---|---|---|
| `apps/core/templates/components/button.html` | — (extensão) | define os novos params |
| `apps/core/templatetags/core_tags.py` | — | +3 entradas em `ICONES_CATALOGO` |
| `apps/core/templates/components/icons/confirmar.svg` (novo) | — | — |
| `apps/core/templates/components/icons/confirmar_check.svg` (novo) | — | — |
| `apps/core/templates/components/icons/estornar.svg` (novo) | — | — |
| `apps/core/tests/test_icons.py` | — | +3 testes de catálogo |
| `apps/requisicoes/templates/requisicoes/rascunho_form.html` | "Criar e enviar para autorização" (primary), "Salvar rascunho" modo editar (primary) | `label_mobile`, `loading_label` |
| `apps/requisicoes/templates/requisicoes/detalhe.html` | "Enviar para autorização" (primary), "Cancelar" ×2 triggers (danger-outline), "Autorizar" (primary), "Recusar" trigger (danger→danger-outline, corrige divergência), "Registrar retirada" (primary), "Separar para retirada" (primary), "Estornar requisição" trigger (danger-outline) | nenhum (todos estáticos, sem loading) |
| `apps/requisicoes/templates/requisicoes/atender_retirada.html` | "Confirmar retirada" trigger (primary) | nenhum |
| `apps/requisicoes/templates/requisicoes/copiar_confirmacao.html` | "Criar rascunho" (primary) | nenhum |
| `apps/estoque/templates/estoque/lista_materiais.html` | "Buscar" (primary) | nenhum |
| `apps/estoque/templates/estoque/nova_saida_excepcional.html` | "Registrar saída excepcional" (primary) | `loading_label`, `icon_template="components/icons/confirmar.svg"` |
| `apps/estoque/templates/estoque/preview_importacao_scpi.html` | "Gerar pré-visualização" (primary), "Tentar novamente" (primary), "Confirmar importação" (primary) | `x_disabled`, `x_aria_busy` (nos 2 primeiros), `label_bind`, `spinner_show`, `icon_template="components/icons/confirmar_check.svg"` (no 3º) |
| `apps/estoque/templates/estoque/detalhe_saida_excepcional.html` | "Estornar" trigger (danger-outline, corrige divergência) | nenhum |
| `apps/accounts/templates/accounts/login.html` | "Entrar" (primary) | `x_disabled`, `label_bind` |

## Estratégia de testes

Não há lógica de domínio nova — é refatoração de apresentação. Estratégia:
1. `uv run pytest -q -ra --tb=short --strict-markers --disable-warnings -n logical` completo antes de tocar em qualquer arquivo (baseline).
2. Novos testes unitários de template para os params novos de `button.html` em `apps/core/tests/test_button_component.py` (arquivo novo, segue convenção de `test_icons.py`: `Template(...).render(Context(...))` sem DB/view):
   - `loading_label` gera `data-submit-loading-label` + `<span data-submit-text>`.
   - `label_mobile` gera os dois spans responsivos.
   - `x_disabled`/`x_aria_busy` geram `:disabled="..."` / `:aria-busy="..."`.
   - `label_bind` gera `<span x-text="...">` com fallback estático.
   - `spinner_show` gera o spinner com `x-show` e esconde `icon_template` com `x-show="!(...)"`.
   - `icon_class="h-5 w-5"` chega ao `{{ class }}` do SVG incluído, e um `class="mt-4"` do próprio botão (contexto do `include` sem `icon_class`) não vaza pro parcial do ícone — isolamento de contexto do `with class=icon_class`.
   - variant `danger-outline` mantém classes de borda vermelha; `danger` mantém fundo sólido (regressão dos variants existentes).
3. 3 testes novos em `test_icons.py` (`test_icon_confirmar_...`, `test_icon_confirmar_check_...`, `test_icon_estornar_...`), mesmo formato dos existentes (path original, viewBox, class repassada).
4. Para cada view afetada, os testes de view/HTML existentes (ex: `apps/requisicoes/tests/test_views_detalhe.py`, `apps/estoque/tests/test_views_saida_excepcional.py`, `apps/accounts/tests/test_views_login.py` — nomes exatos a confirmar durante implementação) continuam passando sem alteração — eles não devem estar acoplados a classes Tailwind literais; se algum teste fizer `assertContains(response, "bg-blue-600")` ele será atualizado para checar o texto/atributo funcional (label, `hx-*`, `data-modal-trigger`) em vez da classe.
5. Suite completa novamente ao final, comparando contagem de pass com o baseline do passo 1.
6. Verificação manual no browser (dev server) das telas com maior risco visual/funcional: login (loading state), `nova_saida_excepcional` (loading + ícone), `preview_importacao_scpi` (3 estados: upload, erro/retry, preview com spinner), `detalhe.html` (todas as seções de ação).

## Invariantes

Projeto não tem `docs/design-acesso-rapido/matriz-invariantes.md` (referência genérica do skill não se aplica aqui). Invariantes relevantes deste projeto:
- ADR-0008 / `docs/design-system.md`: variantes de botão e tokens semânticos (`bg-primary`, `bg-danger`, etc.) são a fonte de verdade visual — a conversão reforça esse contrato em vez de violá-lo.
- `docs/CONVENTIONS.md`: frontend server-rendered, sem introdução de JS framework — todos os novos params de `button.html` são só Django template + Alpine/data-attrs já existentes no projeto, nada novo do lado de framework.
- Nenhuma alteração de `models`/`views`/`services` — mudança 100% de template, não dispara os fluxos de `make setup` (schema) do ambiente efêmero.

## Riscos

- **Regressão visual de padding/raio**: mitigado documentando explicitamente em Scope; é o resultado pretendido da padronização.
- **`form-submit.js` param mismatch**: `loading_label`/`label_mobile` precisam gerar exatamente os seletores que o JS já lê (`[data-submit-loading-label]`, `[data-submit-text]`) — testado unitariamente (test strategy #2) e verificado no browser (test strategy #6, cliques reais disparando loading state).
- **Alpine reativo (`x_disabled`/`label_bind`/`spinner_show`) sem cobertura de teste de integração real (Alpine só roda no browser)** — os testes unitários de template garantem que o HTML gerado tem os atributos/expressões Alpine corretos; o comportamento reativo em si é verificado manualmente no browser (test strategy #6), não há suite JS no projeto.
- **Novos ícones podem já existir sob outro nome** — verificado contra `ICONES_CATALOGO` (`apps/core/templatetags/core_tags.py`) antes de criar: `confirmar`, `confirmar_check`, `estornar` não colidem com o catálogo atual (voltar/lixeira/remover/spinner/adicionar/enviar/copiar).
- **`icon_template` nunca foi exercitado em produção antes desta mudança** — risco de bug latente na própria mecânica do componente (contexto vazando `class` do botão para o ícone). Mitigado adicionando `icon_class` com `with class=icon_class` explícito no include, testado unitariamente.
- **Espaçamento duplicado ícone↔label**: vários botões crus usam `gap-1.5`/`gap-2` no container flex para separar ícone e texto; `button.html` já aplica `mr-2` no wrapper do ícone/spinner. Passar o `gap-*` original via `class` somaria às duas margens e alargaria o espaçamento. Regra de implementação: nunca repassar `gap-*` via `class` em botões com `icon_template`/`spinner_show` — o espaçamento é só o `mr-2` do componente.
