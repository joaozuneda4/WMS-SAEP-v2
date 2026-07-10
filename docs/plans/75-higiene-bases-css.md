# Plano — Issue #75: higiene estrutural (base única de app + CSS inline → input.css)

Parent: #68 (Épico — extração de componentes do design system)

## Escopo

1. **Base única de app.** `apps/requisicoes/templates/requisicoes/base.html` e
   `apps/estoque/templates/estoque/base.html` são idênticos (9 linhas cada,
   ambos apenas estendem `base_auth.html` e preenchem `topbar_domain` com
   `core/_topbar_nav.html` e `sidebar_nav` com `core/partials/_side_nav.html`).
   - Mover os dois `{% include %}` para dentro do conteúdo *default* dos
     blocks `topbar_domain` e `sidebar_nav` em `apps/core/templates/base_auth.html`
     (hoje vazios: `{% block topbar_domain %}{% endblock %}` /
     `{% block sidebar_nav %}{% endblock %}`).
   - Trocar `{% extends "requisicoes/base.html" %}` / `{% extends "estoque/base.html" %}`
     por `{% extends "base_auth.html" %}` nos 16 templates que hoje estendem
     as bases duplicadas (confirmado por grep, não os ~20 estimados na issue):
     - `apps/requisicoes/templates/requisicoes/{fila_atendimento,copiar_confirmacao,atender_retirada,detalhe,rascunho_form,lista_minhas,fila_autorizacao,historico_requisicoes}.html`
     - `apps/estoque/templates/estoque/{historico_movimentacoes,historico_importacoes_scpi,preview_importacao_scpi,confirmar_importacao_scpi,lista_saidas_excepcionais,lista_materiais,detalhe_saida_excepcional,nova_saida_excepcional}.html`
   - Apagar `apps/requisicoes/templates/requisicoes/base.html` e
     `apps/estoque/templates/estoque/base.html`.
   - `apps/accounts/templates/accounts/login.html` já estende `base.html`
     (raiz, não autenticado) — sem mudança, confirmado.
   - `apps/notificacoes/templates/notificacoes/lista.html` já estende
     `base_auth.html` diretamente, sem sobrescrever `topbar_domain`/`sidebar_nav`
     — **passa a ganhar a navegação por padrão** (intencional: o novo default
     dos blocks é global, não opt-in por template; efeito colateral desejado
     pela issue — "qualquer app autenticado ganha a navegação por padrão").
     A nav continua condicionada a `user.is_authenticated` em `base_auth.html`,
     então `accounts/login.html` (não autenticado) permanece sem nav.

2. **CSS inline → `apps/core/static/core/css/input.css`** (`@layer components`,
   ao final do bloco existente, antes do `}` de fechamento em torno da linha 485):
   - `.scroll-shadow-x` — hoje duplicado em `requisicoes/detalhe.html:49-59` e
     `requisicoes/atender_retirada.html:23-32`. Regra idêntica nos dois — migra
     como está.
   - Animações de modal (`modal-entrar`, `modal-backdrop-entrar`, keyframes,
     media query `prefers-reduced-motion: no-preference`) — hoje só em
     `requisicoes/detalhe.html:23-47`. Vira global via seletor de elemento
     (`dialog[open]` / `dialog::backdrop`), sem restrição por classe — decisão
     deliberada, não um efeito colateral acidental. Modais existentes que
     passam a herdar a animação (confirmado por grep de `<dialog` no repo):
     `apps/core/templates/components/modal.html:46` e
     `apps/requisicoes/templates/requisicoes/atender_retirada.html:235`
     (ganho explicitamente desejado pela issue: "modais de outras telas ganham
     a animação").
   - `[x-cloak] { display: none !important; }` — hoje duplicado em
     `requisicoes/rascunho_form.html:9` e `estoque/nova_saida_excepcional.html:7`.
     Vira global.
   - Remover os 4 blocks `{% block extra_head %}...{% endblock %}` inteiros
     (ficam vazios após a migração) de:
     `requisicoes/detalhe.html`, `requisicoes/atender_retirada.html`,
     `requisicoes/rascunho_form.html`, `estoque/nova_saida_excepcional.html`.
   - Rebuild: `npm run css:build` (gera `apps/core/static/core/css/app.css`,
     staticfiles é artefato de coleta e não entra no diff).

## Fora de escopo

- Refatorar `_side_nav.html` / `_topbar_nav.html` (issue de nav própria, #80).
- Tocar em `apps/core/templates/base.html` (raiz) além do necessário — nenhuma
  mudança prevista nele.
- Qualquer mudança de comportamento de domínio (services/policies/selectors).

## Arquivos tocados

| Arquivo | Ação |
|---|---|
| `apps/core/templates/base_auth.html` | edita blocks `topbar_domain`/`sidebar_nav` com include default |
| `apps/requisicoes/templates/requisicoes/base.html` | apagar |
| `apps/estoque/templates/estoque/base.html` | apagar |
| 16 templates (listados acima) | trocar `extends` |
| `requisicoes/detalhe.html`, `requisicoes/atender_retirada.html`, `requisicoes/rascunho_form.html`, `estoque/nova_saida_excepcional.html` | remover `<style>` + block `extra_head` vazio |
| `apps/core/static/core/css/input.css` | adicionar 3 regras a `@layer components` |
| `apps/core/static/core/css/app.css` | gerado por `npm run css:build`, entra no diff |

## Estratégia de teste

Refactor puro de template/CSS, sem mudança de domínio. Estratégia:

- **Suíte existente como regressão principal**: views que renderizam os 16
  templates afetados (requisições e estoque) já têm cobertura de smoke/status
  em `apps/requisicoes/tests/` e `apps/estoque/tests/` — um `extends` quebrado
  (`TemplateDoesNotExist`) ou bloco vazio derruba essas views com 500,
  detectável pela suíte sem teste novo dedicado.
- **Verificação manual pós-implementação** (não automatizável neste projeto,
  sem teste de snapshot de HTML/CSS):
  - Nav lateral (desktop) + drawer mobile aparecem em todas as 16 telas
    afetadas e ausentes em `accounts/login.html`.
  - Scroll shadow visível em `detalhe.html` e `atender_retirada.html`.
  - Animação de modal preservada em `detalhe.html` e agora presente em
    qualquer outro `<dialog>` do app (ex.: `components/modal.html`).
  - `x-cloak` sem flash de conteúdo em `rascunho_form.html` e
    `nova_saida_excepcional.html`.
  - Verificação restrita aos 4 arquivos alterados (não ao repo inteiro, que
    tem usos legítimos de `style=` inline fora de escopo, ex.
    `apps/core/templates/base_auth.html:133-146` no badge de notificação):
    `grep -n "<style\|style=" apps/requisicoes/templates/requisicoes/detalhe.html apps/requisicoes/templates/requisicoes/atender_retirada.html apps/requisicoes/templates/requisicoes/rascunho_form.html apps/estoque/templates/estoque/nova_saida_excepcional.html`
    deve retornar vazio.

## Invariantes relevantes

Nenhum invariante de domínio (`docs/design-acesso-rapido/matriz-invariantes.md`)
é tocado — mudança é puramente de apresentação (template/CSS). O único
invariante de UI aplicável é "nav só aparece para usuário autenticado", já
garantido por `{% if user.is_authenticated %}` em `base_auth.html` e não
alterado por este plano.

## Riscos

- **Baixo.** Sem migrations, sem mutação de estoque, sem state machine.
- Risco principal é mecânico: `extends` apontando para arquivo apagado
  (`TemplateDoesNotExist`) se algum dos 16 templates for esquecido — mitigado
  por grep de verificação final em todo o repositório, não só em `apps/`
  (`rg -n --glob '*.html' 'requisicoes/base\.html|estoque/base\.html' .`
  deve retornar vazio) + suíte completa.
- Migração da animação de modal para escopo global é o único comportamento
  novo (efeito colateral desejado pela issue) — risco de regressão visual em
  outros `<dialog>` é aceito e coberto por verificação manual.
