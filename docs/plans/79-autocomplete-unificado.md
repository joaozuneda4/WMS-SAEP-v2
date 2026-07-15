# Plano — #79 core/js/autocomplete.js unificado

Parent: #68 (Épico — extração de componentes do design system)

## Escopo

**Entra:**
- `apps/core/static/core/js/autocomplete.js` — `Alpine.data('autocomplete', (config) => ...)`, registrado via `document.addEventListener('alpine:init', ...)`, carregado em `base.html` antes de `alpine.min.js`.
- `apps/core/templates/components/autocomplete.html` — markup do combobox (input de busca + spinner + listbox + opção "nenhum resultado"). Não renderiza o hidden input do valor selecionado — isso continua em cada chamador (ver "Decisão" abaixo).
- `apps/requisicoes/templates/requisicoes/partials/_autocomplete_item_beneficiario.html` — item de resultado: nome + matrícula + setor. Partial de domínio, não vive em `core/templates/components/` (componente genérico não conhece semântica de domínio — ajustado após revisão do CodeRabbit na implementação).
- `apps/estoque/templates/estoque/partials/_autocomplete_item_material.html` — item de resultado: código + nome + saldo (compartilhado pelas 2 buscas de material). Mesmo motivo acima.
- Migração das 3 implementações inline:
  1. `beneficiarioAutocomplete()` em `rascunho_form.html`
  2. `materialAutocomplete(index)` em `rascunho_form.html` + `_item_form_row.html`
  3. `novaSaidaExcepcional()` em `nova_saida_excepcional.html` (mantém estado de linha/duplicidade, delega busca)
- 1 linha em `base.html` (`<script src="{% static 'core/js/autocomplete.js' %}" defer></script>`, antes de `alpine.min.js`).

**Não entra (fora de escopo, conforme issue):**
- Endpoints de busca (`buscar_beneficiarios`, `buscar_materiais`, `buscar_materiais_saida_excepcional`) — formato JSON inalterado.
- UX nova (highlight de match, etc).
- `docs/design-system.md` (inventário aspiracional; issue não pede atualização e não altera contrato de domínio).

## Decisões de design (divergências pontuais do texto da issue)

1. **Hidden input fica fora do partial genérico.** O texto da issue lista `name_hidden` como parâmetro do partial, mas na prática cada chamador já declara seu próprio hidden input hoje (Django-rendered com nome de campo real, ou `:name` dinâmico por índice em `nova_saida_excepcional`). Manter o hidden input no template chamador, dentro do mesmo `x-data` do componente, evita reimplementar 2 modos (nome estático vs dinâmico) dentro do partial genérico. O componente acessa o valor via `this.$refs.hiddenInput` (ref definido pelo chamador, convenção fixa: `x-ref="hiddenInput"`).
2. **IDs do combobox gerados internamente (`idBase`), não via parâmetro Django `id_base`.** `nova_saida_excepcional` itera um array 100% client-side (`x-for` sobre `itens`), sem `form_index` por linha — um `id_base` vindo de contexto Django não cobriria esse caso. O componente gera um `idBase` único por instância no `init()` (contador de módulo), usado via bindings Alpine (`:id`, `:for`, `:aria-controls`, `:aria-activedescendant`). Isso cobre os 3 usos sem exigir que o chamador calcule unicidade.
3. **Diferença de campo de saldo (`saldo_disponivel` vs `saldo_fisico`) resolvida no template do item, não via config extra.** `_autocomplete_item_material.html` usa `item.saldo_disponivel ?? item.saldo_fisico`, então o mesmo partial serve às 2 buscas de material sem parâmetro adicional.
4. **`campoDisplay` configurável.** Após selecionar, o texto exibido no input deve ser `item.nome` (beneficiário, comportamento atual) ou `item.label` (material, comportamento atual). Config `campoDisplay` (default `'label'`) resolve isso.
5. **Guarda de duplicidade via callback com veto — veto é no-op, não reset.** `config.onSelect(item)` pode retornar `false` para rejeitar a seleção. No código atual de `nova_saida_excepcional`, ao rejeitar um duplicado o item rejeitado simplesmente não é commitado — `query`/`material_id` ficam exatamente como estavam antes da tentativa (já invalidados pela digitação anterior, ou preservando uma seleção válida prévia se o dropdown reabriu com resultados em cache sem novo fetch). Reproduzir isso 1:1: se `onSelect` retornar `false`, `selecionar()` não altera `query`, não mexe no hidden e não fecha o dropdown — apenas retorna sem commitar. Nada de `limpar()` no veto (chamar `limpar()` destruiria uma seleção válida anterior, que é exatamente o defeito apontado na revisão). A lógica de duplicidade em si (comparar contra os outros itens do array, setar `erroDuplicado`) permanece 100% em `novaSaidaExcepcional()`.

## Contrato do componente (`autocomplete.js`)

Config aceito por `autocomplete(config)`:
- `endpoint` (obrigatório)
- `minChars` (default `2`) — abaixo disso (e acima de 0 chars), busca não dispara e resultados são limpos; campo vazio sempre dispara busca ao focar.
- `campoDisplay` (default `'label'`) — campo do item usado para preencher `query` após seleção.
- `initialId` / `initialLabel` (opcionais) — pré-preenchimento em edição.
- `onSelect(item)` (opcional) — callback; retornar `false` veta a seleção.
- `onInvalidate()` (opcional) — callback chamado quando a edição zera o hidden (nova busca), para sincronizar estado externo por linha (ex. `nova_saida_excepcional` limpa `itens[idx].material_id` para não bloquear indevidamente a guarda de duplicidade com um valor obsoleto). Adicionado após revisão do CodeRabbit na implementação.

Estado exposto: `query`, `resultados`, `aberto`, `buscando`, `ativo`, `idBase`.
Métodos usados pelo partial: `buscarComDebounce()`, `buscarTodos()`, `selecionar(item)`, `fecharDropdown()`, `selecionarProximo()`, `selecionarAnterior()`, `confirmarSelecao()`, `mensagemVaziaVisivel()`, `limpar()`.

**Sincronização do hidden input (convenção fixa, `x-ref="hiddenInput"` no template chamador):**
- `init()`: se `config.initialId` estiver presente, grava `initialId` em `this.$refs.hiddenInput.value` e `initialLabel` em `this.query` — hidrata o campo oculto e o texto exibido a partir do mesmo par id/label, nunca só um dos dois.
- `buscarComDebounce()`: qualquer edição zera `this.$refs.hiddenInput.value = ''` antes de disparar a busca (invalida seleção anterior até nova escolha explícita).
- `selecionar(item)` (caminho aceito, `onSelect(item) !== false`): grava `item.id` em `this.$refs.hiddenInput.value` e `item[campoDisplay]` em `this.query` — sempre os dois juntos, nunca um sem o outro.
- `selecionar(item)` (caminho vetado, `onSelect(item) === false`): não toca em `query` nem em `$refs.hiddenInput` — ver decisão 5 abaixo (veto é no-op, não reset).
- `limpar()` (chamado só pelo próprio chamador quando fizer sentido, ex. reset explícito de linha) zera `query`, `resultados` e `$refs.hiddenInput.value`.

Mensagem "nenhum resultado" visível quando `!buscando && query.length >= max(minChars, 1) && resultados.length === 0` — reproduz o threshold atual de cada tela (beneficiário mostra a partir de 1 char; material a partir de 2).

## Arquivos tocados

| Arquivo | Mudança |
|---|---|
| `apps/core/static/core/js/autocomplete.js` | novo |
| `apps/core/templates/components/autocomplete.html` | novo |
| `apps/requisicoes/templates/requisicoes/partials/_autocomplete_item_beneficiario.html` | novo |
| `apps/estoque/templates/estoque/partials/_autocomplete_item_material.html` | novo |
| `apps/core/templates/base.html` | +1 linha (script tag) |
| `apps/requisicoes/templates/requisicoes/rascunho_form.html` | remove `beneficiarioAutocomplete()`/`materialAutocomplete()` inline; migra seção 1 (beneficiário) para o componente |
| `apps/requisicoes/templates/requisicoes/partials/_item_form_row.html` | migra autocomplete de material para o componente |
| `apps/estoque/templates/estoque/nova_saida_excepcional.html` | `novaSaidaExcepcional()` simplifica `itens[]` (só `_uid`, `material_id`, `quantidade`); cada linha ganha seu próprio `x-data="autocomplete(...)"` |

## Estratégia de testes

Não há testes automatizados de JS/Alpine no projeto (suíte é `pytest`/Django). A verificação é:
- **Suíte Python inalterada** — nenhuma view/service/policy muda; rodar suíte completa para garantir zero regressão (views que servem os 3 templates continuam cobertas pelos testes existentes de view/selector).
- **Verificação manual no browser** dos 3 fluxos (exigida explicitamente pela issue), com evidência anexada ao PR:
  1. Criar requisição para outro beneficiário (digitar, setas, Enter, Esc, blur, foco em campo vazio lista todos, editar rascunho existente mostra label inicial).
  2. Adicionar/editar itens do rascunho, incluindo linha nova via HTMX (`hx-swap beforeend`) — Alpine deve inicializar no swap.
  3. Registrar nova saída excepcional com 2 materiais, incluindo tentativa de duplicidade (mensagem de erro deve aparecer e o veto deve deixar `query`, hidden input e dropdown inalterados — sem limpeza destrutiva, conforme decisão 5).
- Zero mudança de classe Tailwind nova — não deveria haver diff em `app.css`/necessidade de `npm run css:build`, mas isso será conferido no fim (critério de aceite).

## Invariantes relevantes

Não há entrada específica de autocomplete/combobox na matriz de invariantes (`docs/design-acesso-rapido/matriz-invariantes.md` cobre fluxos de acesso rápido, não este componente). Os "invariantes" aqui são os comportamentos listados nos critérios de aceite da própria issue (contrato ARIA, thresholds de busca, guarda de duplicidade) — tratados como a fonte de verdade para este trabalho.

## Riscos

- **Maior risco: UX crítica de formulário.** Cada fluxo de teclado (setas, Enter, Esc, Tab, blur) precisa ser testado manualmente nas 3 telas antes do PR — capturas de tela/descrição anexadas.
- **Compatibilidade HTMX**: nova linha de item via `hx-swap beforeend` precisa inicializar Alpine corretamente (já validado como comportamento existente; só precisa continuar funcionando com o novo `x-data`).
- **Regressão de contrato ARIA**: `idBase` gerado internamente precisa produzir os mesmos atributos (`aria-controls`, `aria-activedescendant`, `id` do listbox/opções) de forma estável entre re-renders — testar sequência buscar → navegar com setas → selecionar.
- **Zero dependência nova**; branch já criada como `refactor/autocomplete-unificado`; PT-BR nos identificadores de domínio (JS interno pode usar nomes em PT-BR como já é convenção nas 3 implementações atuais — `buscar`, `selecionar`, `fecharDropdown`, etc.).
- **`initialId` e `initialLabel` dentro de literal JS**: tanto o identificador quanto o rótulo de beneficiário/material podem conter aspas, acentos ou outros caracteres inválidos em JS — usar `|escapejs` nos dois valores interpolados dentro de `x-data="autocomplete({...})"` para não quebrar o parser JS (o código atual já teria esse risco latente; o partial genérico deve reforçar isso já que passa a ser o único ponto de entrada).
