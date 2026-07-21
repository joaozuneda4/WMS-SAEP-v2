# Plano — Migrar banners de alerta para components/alert.html (#95)

## Scope

Migrar 6 pontos de banner de alerta implementados com classes Tailwind cruas
para `{% include "components/alert.html" %}` — login (1), confirmar
importação SCPI (2: sucesso/erro), preview importação SCPI (2: novos/
divergências) e o `role="note"` customizado em `copiar_confirmacao.html`
(1) — resolvendo esse último para um variant padrão.

**Muda:**
- `apps/accounts/templates/accounts/login.html` — banner de erro não-ligado-a-campo (`~L19`)
- `apps/estoque/templates/estoque/confirmar_importacao_scpi.html` — banner de sucesso (`~L14`) e banner de erro (`~L61`)
- `apps/estoque/templates/estoque/preview_importacao_scpi.html` — banner de materiais novos (`~L373`) e banner de divergências (`~L383`)
- `apps/requisicoes/templates/requisicoes/copiar_confirmacao.html` — remove `role="note"` custom (`L23`)

**Não muda:**
- Erros de campo em `login.html` (`username-error`, `password-error`) — já são `role="alert"` simples, não são "banner", fora do escopo do issue.
- Bordas de seção com tom vermelho em `nova_saida_excepcional.html` (`border-red-300 bg-red-50` em `<section>`) — não é um componente de alerta, é destaque de seção com erro; fora do escopo.
- Barra de estatísticas e legenda de cores em `preview_importacao_scpi.html` (`~L165-237`) — não são alertas, são widgets de resumo/legenda.
- Contrato de `components/alert.html` em si — nenhuma mudança de assinatura.

## Files touched

| Arquivo | Ação |
|---|---|
| `apps/accounts/templates/accounts/login.html` | Substitui `<div id="login-error" role="alert">` por `{% include "components/alert.html" with variant="danger" id="login-error" body_template=... %}` |
| `apps/accounts/templates/accounts/partials/_alert_login_erro_corpo.html` | Novo — loop de `form.non_field_errors` |
| `apps/estoque/templates/estoque/confirmar_importacao_scpi.html` | Substitui 2 divs cruas (sucesso `role=status`, erro `role=alert`) por `alert.html` |
| `apps/estoque/templates/estoque/partials/_alert_sucesso_importacao_corpo.html` | Novo — título + `dl` de métricas + rodapé com nome/data do arquivo |
| `apps/estoque/templates/estoque/partials/_alert_erro_confirmacao_corpo.html` | Novo — título + mensagem de erro |
| `apps/estoque/templates/estoque/preview_importacao_scpi.html` | Substitui 2 divs cruas por `alert.html`: `novos>0` → `variant="info" aria_live="polite"`; `divergencias>0` → `variant="warning" role="status" aria_live="polite"` (override de `role` preserva o `status`/`polite` original — ver tabela ARIA em Test strategy) |
| `apps/estoque/templates/estoque/partials/_alert_novos_materiais_corpo.html` | Novo — parágrafo com contagem de materiais novos |
| `apps/estoque/templates/estoque/partials/_alert_divergencias_corpo.html` | Novo — parágrafo com contagem de divergências |
| `apps/requisicoes/templates/requisicoes/copiar_confirmacao.html` | Remove `role="note"` do include existente; comentário inline justificando `variant="warning"` |
| `apps/accounts/tests/test_login.py` | Atualiza/adiciona asserts de ARIA no banner de erro |
| `apps/estoque/tests/test_views.py` | Atualiza/adiciona asserts de ARIA nos 4 banners (sucesso, erro confirmação, novos, divergências) |
| `apps/requisicoes/tests/test_views.py` | Atualiza `test_copiar_requisicao_view_get_retorna_confirmacao` com asserts de `role="alert"` (não `note`) |

Total: 6 pontos de alerta migrados (1 login + 2 SCPI-confirmação + 2 SCPI-preview + 1 copiar_confirmacao), com 3 arquivos de teste atualizados cobrindo os 6.

## Decisão: `role="note"` em `copiar_confirmacao.html`

Conteúdo do alerta (`_alert_nota_copia_corpo.html`): *"Atenção: quantidades
autorizadas e entregues não são copiadas. Somente as quantidades solicitadas
originais são aproveitadas."* — é um aviso de comportamento/perda de dados no
fluxo de cópia, não uma confirmação neutra nem um erro bloqueante.

**Variant escolhido: `warning`** (mantém o visual atual — já era `warning`
com `role` sobrescrito). Ação: remover o parâmetro `role="note"` do include,
deixando o componente aplicar seu `role="alert"` automático de acordo com o
contrato documentado (warning/danger → alert). Adiciona comentário inline no
template explicando a escolha.

Alternativa descartada: `info`. Rejeitada porque o conteúdo alerta para uma
perda de dado (quantidades não copiadas), que é mais bem representado como
aviso (`warning`) do que como notificação neutra (`info`).

## Test strategy

- **Happy path**: cada banner migrado renderiza com o texto original preservado e a classe de variante correta (`border-success-border`, `border-danger-border`, `border-warning-border`, `border-primary-border`).
- **ARIA**: mapeamento explícito de `role`/`aria_live` por include, um assert por linha na suíte:

  | # | Local | `variant` | `role` renderizado | `aria_live` passado | Preserva original? |
  |---|---|---|---|---|---|
  | 1 | `login.html` | `danger` | `alert` (automático) | — (não passado) | Sim — original não tinha `aria-live` |
  | 2 | `confirmar_importacao_scpi.html` sucesso | `success` | `status` (automático) | `polite` (explícito) | Sim — original já era `status`/`polite` |
  | 3 | `confirmar_importacao_scpi.html` erro | `danger` | `alert` (automático) | `assertive` (explícito) | Sim — original já era `alert`/`assertive` |
  | 4 | `preview_importacao_scpi.html` novos | `info` | `status` (automático) | `polite` (explícito) | Sim — original já era `status`/`polite` |
  | 5 | `preview_importacao_scpi.html` divergências | `warning` | `status` (**override explícito** via `role="status"`) | `polite` (explícito) | Sim — mantém `status`/`polite` original; sem o override, o automático da variante `warning` seria `alert`, mudando a assertividade do anúncio (regressão de comportamento não pedida pelo issue) |
  | 6 | `copiar_confirmacao.html` | `warning` | `alert` (automático, `role="note"` removido) | — (não passado) | Corrigido por design — é exatamente o pedido do issue: sair do `role="note"` fora de contrato para o `role` automático documentado |

  `components/alert.html` não define `aria-live` por padrão (só renderiza quando `aria_live` é passado) — por isso os itens 2-5 exigem o parâmetro explícito no include, não só a escolha do `variant`.
- **Regressão de contrato**: `id="login-error"` preservado (usado por `aria-describedby` nos campos do form, coberto por teste já existente `test_login_preserva_ids_de_erros_aria`).
- Nenhum teste de domínio/serviço é afetado — mudança é puramente de apresentação.
- **Permissão negada / violação de domínio / erro de contrato**: N/A — nenhuma view, service ou policy é tocada; os testes de permissão e contrato HTTP já existentes (`test_sem_permissao_retorna_403`, etc.) continuam cobrindo o comportamento não-visual sem alteração.

## Invariants

Nenhuma entrada de `docs/design-acesso-rapido/matriz-invariantes.md` se
aplica — essa matriz cobre o fluxo de acesso rápido, não os templates
tocados aqui.

`CONTEXT.md` (glossário "Divergência SCPI" e regras de `preview_importacao_scpi`,
`~L110-196`) documenta: *"Pré-visualizar importação é sempre read-only"* e
*"Divergência SCPI gera alerta; nunca altera `saldo_fisico`"*, com *"o preview
mostra o delta para permitir conferência"*. Essas invariantes seguem intactas
nesta migração: o delta por linha já é exibido na coluna `Delta` da tabela
(`~L290-302` de `preview_importacao_scpi.html`, fora do escopo desta issue) e
continua inalterado; o banner de divergências (`~L383`) migrado preserva o
texto original — que já é só uma contagem com a reassurance "saldo do WMS
não será alterado" — sem incluir o delta agregado, pois o conteúdo do banner
não muda nesta migração puramente de apresentação, só sua casca de markup.

## Risks

- **Baixo risco geral** — mudança é só de apresentação (HTML/template), sem alteração de views, services ou models.
- Risco de regressão visual: variant automático de `alert.html` usa cores fixas do design system (`primary`/`success`/`warning`/`danger`), diferente das cores customizadas atuais em `preview_importacao_scpi.html` (teal para "novos", que não tem variant equivalente — mapeado para `info`/azul). Aceito como consequência esperada da padronização pedida no issue.
- Risco de quebra de `aria-describedby`: mitigado preservando `id="login-error"` via parâmetro `id` do componente.
