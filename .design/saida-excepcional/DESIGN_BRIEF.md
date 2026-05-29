# Design Brief: Saída Excepcional de Estoque

## Problem

O Almoxarifado precisa registrar baixas administrativas diretas de material
sem usar o ciclo de vida de Requisição. Hoje esse tipo de operação não tem
um fluxo visual próprio, o que dificulta encontrar o documento, revisar os
itens baixados e executar estorno com clareza. Sem uma tela dedicada, a
feature corre o risco de parecer uma variação de atendimento ou cancelamento,
quando na verdade é um documento de estoque independente.

## Solution

Criar um fluxo próprio em `estoque` para **Saída excepcional**, com lista,
novo registro e detalhe. O usuário navega por uma área explícita do menu de
Almoxarifado, registra uma baixa física direta com número próprio, consulta o
histórico do documento e, no detalhe, executa estorno total com confirmação e
justificativa.

O design precisa comunicar três coisas sem ambiguidade:

- trata-se de um documento de estoque, não de Requisição;
- o registro é final, atômico e baixa `saldo_fisico` imediatamente;
- o estorno é reversão total e auditável, não edição.

## Experience Principles

1. **Documento antes de ação** -- o usuário vê número, estado, motivo,
   observação, estoque e itens antes de registrar ou estornar. Operação
   sensível pede contexto visível.
2. **Consulta ampla, mutação restrita** -- chefe, auxiliar e superuser podem
   consultar; apenas chefe e superuser (via override técnico) podem registrar/estornar.
   A interface precisa refletir essa diferença sem botões desabilitados
   confusos.
3. **Conferência item a item** -- cada material aparece de forma granular,
   com quantidade explícita. Resumo ajuda, mas nunca substitui a linha
   auditável do item.

## Aesthetic Direction

- **Philosophy**: Pragmatic Minimal -- reaproveitar o mesmo shell,
  componentes e linguagem visual já usados em Requisições, sem criar um
  produto visual paralelo para estoque.
- **Tone**: Operacional, confiável e auditável. A interface deve parecer uma
  ferramenta interna séria, não um fluxo consumer nem uma tela administrativa
  genérica.
- **Reference points**: As telas de Requisição já existentes no sistema,
  especialmente listas operacionais e detalhe. A Saída excepcional deve
  parecer parte do mesmo sistema, só com copy e entidades próprias.
- **Anti-references**: Formulário escondido atrás de modal, tela técnica com
  aparência de planilha crua, shell próprio de estoque, botões destrutivos
  espalhados na lista, scroll horizontal obrigatório no mobile.

## Existing Patterns

- **Typography**: Tailwind/system-ui, herdado do layout autenticado atual.
- **Colors**: Paleta Tailwind já usada no sistema; nenhum token novo é
  necessário nesta fase. Badge de `Registrada` deve ser azul/informativo e
  `Estornada` deve usar semântica de reversão/teal se houver classe
  equivalente.
- **Spacing**: Mesmo padrão de `base_auth.html` e das telas operacionais:
  container amplo, padding consistente, blocos com respiro suficiente para
  leitura.
- **Components**: Reaproveitar topbar/drawer, botões, badges, modal simples,
  cards/tabelas e o autocomplete inline de material já existente na tela de
  nova Requisição, adaptando apenas a fonte de dados e as regras de
  elegibilidade.

## Component Inventory

| Component | Status | Notes |
|---|---|---|
| Lista de saídas excepcionais | New | Tabela no desktop, cards empilhados no mobile, ordenada por mais recente primeiro |
| Empty state da lista | New | CTA `Nova saída excepcional` apenas para quem pode registrar |
| Formulário de novo registro | New | Dois blocos: `Dados da saída` e `Materiais` |
| Autocomplete de material | Modify | Reaproveitar a UI existente da nova Requisição, mas com contexto de saída excepcional |
| Linha/card de item | New | Material, unidade, saldo aplicável se disponível, quantidade a baixar, remover |
| Detalhe da saída excepcional | New | Cabeçalho, resumo, itens, timeline e dados de estorno |
| Badge de estado | New | `Registrada` e `Estornada` com semântica própria da feature |
| Modal de estorno | New | Confirmação simples com justificativa obrigatória |
| Menu do drawer | Modify | Grupo `Almoxarifado` com `Atendimento` e `Saídas excepcionais` |

## Key Interactions

**Navegação**
- A entrada da feature fica no grupo `Almoxarifado` do drawer.
- O link leva para a lista de saídas excepcionais.
- O redirect pós-login do Almoxarifado continua indo para `Atendimento`.

**Lista**
- Mostra número público, data, motivo, estado, registro por, itens e ação de
  detalhe.
- No mobile, cada linha vira card empilhado.
- Sem filtros no MVP.
- Empty state:
  - chefe/superuser: mostra CTA para novo registro;
  - auxiliar: mostra mensagem informativa sem CTA.

**Novo registro**
- Formulário único com dois blocos:
  - dados da saída: motivo e observação;
  - materiais: busca/autocomplete, adicionar material, quantidade por linha.
  - não permitir material duplicado no mesmo documento (1 linha por Material);
    se repetir, bloquear envio e exibir erro claro ao usuário.
- O usuário precisa ver tudo antes de submeter.
- Registro é final: ao confirmar, baixa saldo físico imediatamente.
- O botão primário deve ser `Registrar saída excepcional`.

**Detalhe**
- Mostra número público, estado, motivo, observação, estoque afetado, total
  de itens, itens item a item, timeline e dados de estorno.
- O botão `Estornar` aparece apenas quando o documento está `Registrada` e o
  usuário pode estornar.
- O estorno usa modal simples com justificativa obrigatória.
- Após sucesso, voltar para o detalhe atualizado.

## Responsive Behavior

| Breakpoint | Behavior |
|---|---|
| Mobile | Layout em uma coluna; itens em cards empilhados; nada de tabela horizontal obrigatória |
| Tablet | Layout ainda verticalizado, mas com mais espaço para tabela de itens e resumo |
| Desktop | Lista em tabela, detalhe com cabeçalho e blocos lado a lado quando fizer sentido |

O conteúdo deve continuar legível em telas menores sem obrigar rolagem lateral
para tomar decisão. Na tela de novo registro, quantidade e remover precisam
permanecer visíveis no mobile.

## Accessibility Requirements

- Contraste mínimo WCAG AA em textos, badges e botões.
- Todo input deve ter `<label>` explícito.
- Modal de estorno precisa de `role="dialog"`, `aria-modal="true"` e foco
  gerenciado corretamente.
- A lista precisa ser navegável por teclado e manter o link de detalhe
  acessível.
- O estado precisa ter label textual além da cor.
- O autocomplete precisa ser utilizável por teclado, com navegação por setas
  e confirmação da seleção.
- O botão de ação destrutiva deve deixar explícito o impacto da operação.

## Out of Scope

- Information architecture nova ou shell próprio de estoque.
- Design tokens novos.
- Tela dedicada para doação, empréstimo, transferência ou inventário.
- Estorno parcial.
- Filtros, busca e paginação na lista.
- Duplicar documento.
- Excluir fisicamente o documento.
- Editar registro após persistência.
- Qualquer implementação de backend nesta fase.
