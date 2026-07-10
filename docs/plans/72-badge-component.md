# Plano — #72 components/badge.html + partials de domínio

## Parent

Issue #68 (Fase 1 — fundações)

## Escopo

**Constrói:**
1. `apps/core/templates/components/badge.html` — componente global (`variant`, `label`, `aria_label` opcional, `role` opcional).
2. Refatoração de `requisicoes/partials/_estado_badge.html` e `estoque/partials/_badge_tipo_movimentacao.html` para delegar em `badge.html`.
3. Novo `estoque/partials/_badge_estado_saida.html` (registrada→`blue-strong`, estornada→`teal`).
4. Migração dos pills inline restantes (7 templates) para `badge.html`/partial adequado.

**Não muda:** mapa semântico cor↔estado, views, services/policies/selectors, tokens semânticos.

**`status_badge.html` vs `badge.html`:** `docs/design-system.md` (§Inventário inicial) planejava o nome `status_badge.html`, mas nenhum arquivo com esse nome existe no repositório — é só um nome de inventário, nunca implementado. A issue #72 nomeia o componente real como `badge.html`; não há dois contratos concorrentes. Este plano atualiza as seis menções de `status_badge.html` em `docs/design-system.md` (linhas 287, 331, 346, título da §5, e os dois exemplos de `{% include %}` em §Exemplos de uso) para `badge.html` como parte da entrega, eliminando a divergência de nome na documentação.

## Contrato ARIA de `badge.html`

- `role` (opcional): quando informado, é renderizado literalmente como `role="{{ role }}"` no `<span>`. Sem valor por padrão (nenhum `role` é emitido) — decisão do chamador, `badge.html` não infere role a partir de `variant`.
- `aria_label` (opcional): quando informado, é renderizado como `aria-label="{{ aria_label }}"`. Sem valor por padrão.
- Convenção adotada pelos partials de domínio (`docs/CONVENTIONS.md`): estados neutros/informativos passam `role="status"`; nenhum dos 34 usos migrados é warning/error bloqueante o suficiente para exigir `role="alert"` (todos são indicadores de estado em listagem, não alertas ativos) — mantém-se `role="status"` onde já existia (`_estado_badge.html`) e nenhum `role` novo é introduzido nos pills antes sem `role` (preserva o comportamento atual, não expande escopo).
- Cada linha da tabela "Arquivos tocados" abaixo mantém exatamente o `role`/`aria-label` que o ponto de uso já tem hoje, exceto a nova `_badge_estado_saida.html`, que passa a emitir `aria-label="Estado: …"` em todos os pontos (issue pede explicitamente; hoje falta no desktop de `lista_saidas_excepcionais.html` — ganho de acessibilidade, não regressão).

## Variantes do componente

12 variantes pedidas na issue + 1 adição (`amber-strong`) — justificativa abaixo.

Padrão de classes (uma string literal por `{% if %}`, exigência do JIT):
```text
inline-flex items-center rounded-full bg-{cor}-{100|200} px-2.5 py-0.5 text-xs font-semibold text-{cor}-900 ring-1 ring-inset ring-{cor}-{200|300}
```

| Variante | bg | text | ring |
|---|---|---|---|
| slate | slate-100 | slate-900 | slate-200 |
| blue | blue-100 | blue-900 | blue-200 |
| blue-strong | blue-200 | blue-900 | blue-300 |
| amber | amber-100 | amber-900 | amber-200 |
| amber-strong (**adição**) | amber-200 | amber-900 | amber-300 |
| green | green-100 | green-900 | green-200 |
| red | red-100 | red-900 | red-200 |
| red-strong | red-200 | red-900 | red-300 |
| orange | orange-100 | orange-900 | orange-200 |
| teal | teal-100 | teal-900 | teal-200 |
| indigo | indigo-100 | indigo-900 | indigo-200 |
| violet | violet-100 | violet-900 | violet-200 |
| yellow | yellow-100 | yellow-900 | yellow-200 |

**Desvio da issue — `amber-strong`:** a issue lista só "amber" para o contador de `fila_autorizacao.html` (hoje `bg-amber-200`), mas `preview_importacao_scpi.html` também tem pills `amber-100` (divergência de linha) sem nome de variante próprio. Resolvido criando `amber-strong` (200/900/300) para os badges de "atenção forte" (aguardando autorização, contador de itens) e mantendo `amber` (100/900/200) para a divergência de linha do SCPI — evita escurecer/clarear um indicador existente sem necessidade. Registrar no PR.

## Normalização (permitida e registrada por §Critérios de aceite da issue)

Todos os pills que já usam `bg-X-100` mas com `font-medium`, `text-X-800` ou sem `ring` são normalizados para o padrão dominante (`font-semibold`, `text-X-900`, `ring-1 ring-inset`) — mesmo par fundo-100/texto-900 já documentado em `_badge_tipo_movimentacao.html` para AA. `px-3`/`px-2` → `px-2.5`.

Único ponto com mudança de **tom** (100→200): `lista_materiais.html` "Divergente" (hoje `bg-red-100`/`text-red-800`/`ring-red-300` — combinação já inconsistente) migra para `red-strong` (200/900/300), conforme pedido explícito da issue. Registrar no PR.

**Critério de aceite adicional — remoção de ícone decorativo (aprovado neste plano):** `preview_importacao_scpi.html` tem 3 badges desktop (OK/Divergência/Novo) com `<svg aria-hidden="true">` inline junto ao texto; as versões mobile equivalentes não têm ícone — já são visualmente distintas hoje. `badge.html` não recebe slot de ícone (contrato da issue é só `variant`/`label`); adicionar um slot só para este caso isolado violaria "proibido qualquer referência a enum de domínio" por extensão de escopo do componente global. Decisão: os 3 ícones desktop são removidos, alinhando desktop e mobile. Como são puramente decorativos (`aria-hidden="true"`) e o texto (`OK`/`Divergência`/`Novo`) já é o portador primário de significado, não há perda de informação nem impacto de acessibilidade — é uma mudança visual menor, aprovada explicitamente aqui como parte do critério de aceite da paridade visual (a paridade exigida pela issue é de cor/peso por variante, não de ícones decorativos pré-existentes e inconsistentes entre mobile/desktop).

## Arquivos tocados

| Arquivo | Ação |
|---|---|
| `apps/core/templates/components/badge.html` | criar |
| `apps/requisicoes/templates/requisicoes/partials/_estado_badge.html` | refatorar para incluir `badge.html` |
| `apps/estoque/templates/estoque/partials/_badge_tipo_movimentacao.html` | refatorar para incluir `badge.html` |
| `apps/estoque/templates/estoque/partials/_badge_estado_saida.html` | criar |
| `apps/estoque/templates/estoque/lista_saidas_excepcionais.html` | usar `_badge_estado_saida` (mobile :31-45, desktop :104-112) |
| `apps/estoque/templates/estoque/detalhe_saida_excepcional.html` | usar `_badge_estado_saida` (:20-34) |
| `apps/requisicoes/templates/requisicoes/fila_atendimento.html` | `badge.html` direto (:29-37 mobile, :90-98 desktop) — não reusa `_estado_badge` (mapa de cor já diverge hoje: "Pronta para retirada" é teal aqui, blue-strong em `_estado_badge`; fora de escopo mudar) |
| `apps/requisicoes/templates/requisicoes/fila_autorizacao.html` | `badge.html` variant `amber-strong` (:29-31) |
| `apps/estoque/templates/estoque/lista_materiais.html` | `badge.html` variant `red-strong`, aria-label atual (:61-68, :117-123) |
| `apps/estoque/templates/estoque/historico_importacoes_scpi.html` | `badge.html` Concluída(green)/Com alertas(yellow)/default(slate) (:55-61) |
| `apps/estoque/templates/estoque/preview_importacao_scpi.html` | `badge.html` para as 6 pills de status de linha (desktop :324-339, mobile :358-364) |
| `apps/core/static/core/css/input.css` / `app.css` | rebuild via `npm run css:build` |

## Estratégia de teste

Modelos puros (sem lógica Python nova) — sem testes unitários de service/view. Cada etapa tem critério de sucesso explícito:

| Etapa | Critério de sucesso |
|---|---|
| `ruff format . && ruff check .` | Saída limpa (nenhum `.py` é tocado, mas roda para confirmar zero regressão acidental). |
| `uv run mypy apps` | Saída limpa — mesma razão acima; nenhuma mudança de tipo esperada. |
| `uv run pytest -q -ra --tb=short --strict-markers --disable-warnings -n logical` | Suíte 100% verde, contagem de passes igual à baseline pré-mudança (nenhuma view/model muda). |
| `npm run css:build` | Roda sem erro; `apps/core/static/core/css/app.css` aparece no diff. Confirmar presença de todas as classes literais das 13 variantes no CSS gerado: `bg-slate-100`/`ring-slate-200`, `bg-blue-100`/`ring-blue-200`, `bg-blue-200`/`ring-blue-300`, `bg-amber-100`/`ring-amber-200`, `bg-amber-200`/`ring-amber-300`, `bg-green-100`/`ring-green-200`, `bg-red-100`/`ring-red-200`, `bg-red-200`/`ring-red-300`, `bg-orange-100`/`ring-orange-200`, `bg-teal-100`/`ring-teal-200`, `bg-indigo-100`/`ring-indigo-200`, `bg-violet-100`/`ring-violet-200`, `bg-yellow-100`/`ring-yellow-200` — nenhuma ausente. |
| Contraste WCAG AA | Verificar com ferramenta de contraste (ex. DevTools) as 13 variantes, cobrindo os dois pares usados (`fundo-100/texto-900` e `fundo-200/texto-900`, ambos já documentados como AA-compliant em `_badge_tipo_movimentacao.html`) — razão de contraste texto/fundo ≥ 4.5:1 em cada uma das 13. O `ring` é puramente decorativo (delimita o pill, não carrega informação própria) e não precisa atingir 3:1 de contraste gráfico. |
| Verificação manual no navegador | Checklist da issue, 9 telas: minhas requisições, fila de atendimento, fila de autorização, histórico de requisições, lista de saídas excepcionais, detalhe de saída excepcional, catálogo de materiais, histórico de importações SCPI, preview de importação SCPI — sem regressão visual fora do documentado em "Normalização". |
| Diff ARIA | Conferência atributo a atributo dos 34 pontos de `role`/`aria-label` contra o estado antes da migração (ver "Contrato ARIA" acima) — zero divergência não documentada. |

## Invariantes (docs/design-acesso-rapido/matriz-invariantes.md)

Refactor puro de apresentação — não altera nenhuma regra de domínio, RBAC, transição de estado ou contrato de dados. Nenhum invariante de domínio é tocado.

## Riscos

- **Tailwind JIT**: strings de classe devem ser literais completas por ramo — nenhuma interpolação de cor. Confirmado no design do componente.
- **Drift de contraste**: normalizações text-800→900 sobre fundo-100, e a mudança de tom `bg-red-100→red-200` da variante `red-strong` (§Normalização), são as únicas mudanças de tom previstas; risco de over-normalizar além do documentado — mitigado seguindo estritamente a tabela de variantes acima.
- **Escopo do componente**: proibido qualquer `{% if estado == %}` dentro de `badge.html` — só partials de domínio conhecem enums.
