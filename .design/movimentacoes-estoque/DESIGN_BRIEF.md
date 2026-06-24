# Design Brief: Histórico de Movimentações de Estoque

> Origem: US-17 — "Como auditor interno, quero listar todas as movimentações de estoque
> de um material em ordem cronológica". Ampliado em grill para servir também chefes e
> auxiliares de setor (escopo do próprio setor) e o almoxarifado (escopo global).
>
> **Mapeamento RBAC**: "auditor interno" é um sinônimo de negócio (visão global do ledger),
> **não** um papel próprio no modelo de acesso. O contrato de visibilidade em
> `apps/estoque/selectors.py::movimentacoes_visiveis_para` reconhece apenas
> **superuser / almoxarifado / setor**; a visão global do auditor é servida hoje por
> `superuser` ou `almoxarifado`. Não há permissão nova nesta entrega — alinhado a CONTEXT.md
> e à matriz de permissões. Se um papel "auditor" dedicado surgir, será decisão futura.

## Problem

Hoje não há tela alguma para enxergar o ledger `MovimentacaoEstoque`. O selector
`entregue_liquida_por_item` resolve reconciliação por item (US-11), mas ninguém
consegue **navegar** o histórico:

- O **auditor interno** precisa rastrear, em ordem cronológica, tudo que aconteceu com
  um material — e não tem por onde olhar.
- O **chefe / auxiliar de setor** quer entender o que saiu para o próprio setor, sem ver
  o estoque inteiro nem dados de outros setores.
- O **chefe / auxiliar de almoxarifado** precisa da visão completa de todas as saídas,
  para todos os setores, incluindo as baixas administrativas (saídas excepcionais).

A informação existe no banco (ledger imutável, append-only), mas é invisível ao usuário.

## Solution

Uma tela única de **ledger filtrável**: lista cronológica de movimentações de estoque,
onde cada linha é um evento atômico do ledger. O **mesmo** ecrã serve aos três atores —
o que muda é o universo de dados que o RBAC revela e quais filtros aparecem. O auditor
filtra por material; o chefe vê só o próprio setor; o almoxarifado vê tudo e ainda pode
filtrar por setor. Os filtros vivem na URL, então qualquer recorte é compartilhável e o
botão voltar funciona.

A tela não calcula métricas nem desenha gráficos — entrega o histórico navegável. O
selector de visibilidade nasce como **fundação reutilizável** para o futuro dashboard de
estoque (curva ABC, ponto de pedido, alertas).

## Experience Principles

1. **Fidelidade ao ledger sobre conveniência visual** — uma linha = uma
   `MovimentacaoEstoque`. Não colapsamos eventos nem escondemos deltas; o auditor precisa
   ver a verdade append-only, com os dois deltas (físico e reservado) assinados.
2. **O papel define o universo, o filtro define o recorte** — RBAC decide o que é
   visível (regra de domínio, no selector); os filtros só estreitam dentro do permitido.
   Nunca o contrário. Setor jamais vê dado de outro setor por manipular a URL.
3. **Recorte compartilhável sobre estado efêmero** — todo filtro é querystring. Auditor
   manda um link, marca um favorito, recarrega sem perder contexto. HTMX troca só a
   tabela, mas a URL acompanha.

## Aesthetic Direction

- **Philosophy**: Ferramenta de trabalho operacional — pragmático, neutro, denso de
  informação sem ser ruidoso. Segue `docs/design-system.md` à risca.
- **Tone**: Clínico e confiável. É uma tela de auditoria; transmite exatidão, não
  entusiasmo.
- **Reference points**: `lista_saidas_excepcionais.html` (tela-irmã: filtros + tabela +
  cards mobile), changelist administrativa densa, extrato bancário.
- **Anti-references**: dashboard colorido com cards de métrica; nada de gráficos,
  gradientes ou "hero". Sem alarmismo cromático — cor comunica tipo, não emoção.

## Existing Patterns

Componentes e convenções já no código que esta tela respeita e estende:

- **Tipografia**: `ui-sans-serif, system-ui` (sem CDN). Títulos via `app-bar__title`.
  Números com `tabular-nums`.
- **Cores** (`docs/design-system.md`): slate (neutro/fundos/texto), blue (ação/foco),
  green (success), amber (atenção), red (perigo/divergência), teal (devolução/reversão
  não-negativa), info=slate. Shades 50–100 fundo de badge; 700–900 texto colorido.
- **Espaçamento / layout**: container `max-w-screen-xl mx-auto`; cards `rounded-xl border
  border-slate-200 bg-white shadow-sm`; alvos de toque `min-h-11`.
- **Acessibilidade já praticada**: `focus-visible:ring-2 ring-blue-500`, `<caption
  class="sr-only">` em tabelas, `aria-label` em ações, `scope="col"` em headers.
- **Split responsivo**: mobile = `<article>` cards empilhados (`sm:hidden`); desktop =
  `<table>` (`hidden sm:block`). Padrão herdado de `lista_saidas_excepcionais.html`.
- **Stack de interação**: Django templates + Tailwind + HTMX + Alpine. Paginação e
  filtros server-side; HTMX faz swap parcial da tabela.
- **Camada de dados**: selectors retornam `QuerySet`/dados; views finas; RBAC no
  selector espelhando `requisicoes/selectors.py::requisicoes_visiveis_para`
  (helpers `_setores_chefiados_nao_almox`, `_eh_almoxarifado`).

## Component Inventory

| Component | Status | Notes |
| --------- | ------ | ----- |
| App-bar / título da página | Exists | Reusa `block topbar_leading` + `app-bar__title`. |
| Tabela densa (desktop) | Modify | Mesmo esqueleto de `lista_saidas_excepcionais`; novas colunas (tipo, deltas, origem, ator). |
| Cards empilhados (mobile) | Modify | Mesmo padrão `<article>`; adaptado às colunas de movimentação. |
| Badge de tipo de movimentação | New | Pill semântica por `TipoMovimentacaoEstoque` (7 tipos). Cor comunica identidade do tipo, não alarme. Reusa formato pill existente. |
| Barra de filtros | New | Form GET: busca de material, multi-seleção de tipo, período (data ini/fim), setor (só almox). Submete via HTMX preservando querystring. |
| Chip "só saídas" | New | Atalho que seta o filtro de tipo para `consumo` + `saida_excepcional`. |
| Célula de delta assinado | New | Δfísico / Δreservado com `tabular-nums`; sinal +/− visível; zero atenuado (`text-slate-400`). |
| Célula de origem | New | Renderiza **texto** com o nº público da requisição **ou** da saída excepcional (exatamente uma origem por linha). **Sem link nesta entrega** — deep-links de origem ficam em "Out of Scope". |
| Paginação | New/Modify | Controle server-side; preserva querystring de filtros. Verificar se há partial de paginação reutilizável antes de criar. |
| Empty state | Exists | Padrão `border-dashed` + ícone + mensagem; texto adaptado ("Nenhuma movimentação encontrada para este filtro"). |
| Item de menu "Movimentações" | New | Entrada na navegação da área de estoque (`_topbar_nav.html`). Visível conforme RBAC. |

## Key Interactions

- **Abrir a tela**: carrega a 1ª página do ledger visível ao ator, ordenada por
  `criado_em` decrescente (mais recente no topo), filtro de tipo = todos. Sem filtro de
  material/período aplicado.
- **Filtrar**: usuário ajusta material/tipo/período/setor → submit dispara HTMX GET →
  só o bloco da tabela+paginação é trocado; a URL é atualizada (`hx-push-url`) para o
  recorte ficar compartilhável. Página volta para 1.
- **Chip "só saídas"**: um clique seta tipo = consumo+saída_excepcional e reaplica o
  filtro. Estado ativo do chip visível.
- **Ordenar**: clicar no header de data inverte cronologia (asc ↔ desc) — auditor lê
  reconciliação de baixo para cima quando quiser. Indicador de direção no header.
- **Paginar**: navegação de páginas via HTMX, mantendo todos os filtros na URL.
- **Sem resultados**: empty state contextual ("Nenhuma movimentação para este filtro" —
  diferente de "ledger vazio").
- **RBAC invisível**: chefe de setor não vê o filtro de setor (já está escopado) nem
  saídas excepcionais; tentar forçar via querystring não vaza dado — o selector é a
  fronteira.

## Responsive Behavior

- **≥ sm (desktop/tablet)**: tabela densa com todas as colunas — data/hora · tipo ·
  material · Δfísico · Δreservado · origem · ator. `overflow-x-auto` protege em larguras
  intermediárias.
- **< sm (mobile)**: cada movimentação vira card. Hierarquia no card: tipo (badge) +
  data/hora no topo; material em destaque; deltas em `<dl>`; origem e ator como
  metadados secundários. Sem rolagem horizontal.
- **Barra de filtros**: em mobile colapsa em layout empilhado / disclosure; campos full-
  width com `min-h-11`. Chip "só saídas" sempre visível.

## Accessibility Requirements

- Contraste mínimo WCAG AA (4.5:1 texto normal). Badges de tipo: par fundo-100/texto-900
  conforme regra de shades do design system.
- Cor **nunca** é único portador de significado: o tipo tem rótulo textual no badge; o
  sinal do delta é explícito (+/−), não só cor.
- Navegação completa por teclado: filtros, chip, ordenação e paginação focáveis e
  operáveis; `focus-visible:ring-2 ring-blue-500`.
- Tabela com `<caption class="sr-only">` descrevendo conteúdo e ordenação corrente;
  `scope="col"` nos headers; header de ordenação com `aria-sort`.
- Região da tabela atualizada por HTMX anuncia mudança para leitores de tela: contêiner de
  resultados com `aria-live="polite"` **e** `aria-atomic="true"` — contrato completo de
  `docs/design-system.md` (linha 267) para updates HTMX críticos.
- Alvos de toque `min-h-11` em todos os controles.

## Out of Scope

- **Qualquer agregação ou métrica**: curva ABC, ponto de pedido, consumo médio, alertas,
  cards de resumo, gráficos. O selector é projetado como fundação para isso, mas nada
  dessa camada é entregue aqui.
- **Exportação** (CSV/PDF) do resultado filtrado — task futura.
- **Deep-links** a partir de `lista_materiais` / detalhe do material / detalhe da
  requisição. Os filtros em querystring tornam isso trivial depois, mas não montamos os
  links de origem nesta entrega (entrada só pelo menu).
- **Agrupamento por origem** (colapsar N movimentações de uma requisição) — rejeitado no
  grill por contrariar o eixo de auditoria.
- **Edição/estorno a partir desta tela** — ledger é imutável; esta tela é estritamente
  leitura.
- **Saldo inicial de importação SCPI** no histórico — lacuna conhecida do ledger
  (ADR-0015); não é responsabilidade desta tela resolver.
