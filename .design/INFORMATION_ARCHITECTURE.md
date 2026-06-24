# Information Architecture: WMS-SAEP

Cobre o escopo dos três briefs produzidos: login, telas operacionais (listas) e detalhe da requisição. Outros módulos (estoque, materiais, admin operacional) são fora do escopo desta IA.

## Site Map

```
/                               → redirect por papel (ver fluxo de login)
/login/                         → Tela de login (accounts:login)
/logout/                        → POST logout (accounts:logout)

/requisicoes/
  minhas/                       → Minhas Requisições (solicitante, aux. setor)
  nova/                         → Criar nova requisição [fora de escopo atual]
  autorizacoes/                 → Fila de Autorização (chefe de setor)
  atendimentos/                 → Fila de Atendimentos (aux/chefe almoxarifado)
  <id>/                         → Detalhe da Requisição
    editar/                     → Editar rascunho [fora de escopo atual]
    atender/                    → Formulário de atendimento [fora de escopo atual]
    devolucao/                  → Registrar devolução [fora de escopo atual]

/admin/                         → Django admin (superuser)

/estoque/
  movimentacoes/                → Histórico de Movimentações (estoque:historico_movimentacoes)
                                   [visível: almoxarifado (chefe/aux) + chefe/aux de setor]
```

Páginas marcadas `[fora de escopo atual]` são mapeadas na IA para completude, mas não têm brief ainda.

## Redirect Pós-Login

`/` é o destino padrão após autenticação. A view em `core:home` detecta o papel efetivo e redireciona:

| Papel efetivo | Destino |
|---|---|
| Solicitante | `/requisicoes/minhas/` |
| Auxiliar de setor | `/requisicoes/minhas/` |
| Chefe de setor | `/requisicoes/autorizacoes/` |
| Auxiliar de almoxarifado | `/requisicoes/atendimentos/` |
| Chefe de almoxarifado | `/requisicoes/atendimentos/` |
| Superuser | `/admin/` |

Usuário com múltiplos papéis: hierarquia de prioridade `chefe_almox > aux_almox > chefe_setor > aux_setor > solicitante`. Superuser sempre vai para admin.

`LOGIN_REDIRECT_URL = '/'` em `settings.py`.

## Navigation Model

### Primary navigation (top nav, visível após login)

Máximo de 4 links por papel. Links são condicionais — o usuário só vê o que pode usar.

| Papel | Links visíveis |
|---|---|
| Solicitante | Minhas Requisições · Nova Requisição |
| Auxiliar de setor | Minhas Requisições · Nova Requisição |
| Chefe de setor | Minhas Requisições · Autorizações |
| Auxiliar de almoxarifado | Atendimento |
| Chefe de almoxarifado | Atendimento |
| Superuser/staff | Admin |

Usuário com múltiplos papéis: união dos links permitidos.

> **Módulo Estoque** — navegação secundária dentro da área de almoxarifado (`_topbar_nav.html`):
>
> | Papel | Links visíveis |
> |---|---|
> | Chefe de almoxarifado | Atendimento · Saídas excepcionais · Catálogo de materiais · **Movimentações** · Importar SCPI · Histórico de importações SCPI |
> | Auxiliar de almoxarifado | Atendimento · Saídas excepcionais · Catálogo de materiais · **Movimentações** · Importar SCPI · Histórico de importações SCPI |
> | Chefe de setor | **Movimentações** (escopo do próprio setor) |
> | Auxiliar de setor | **Movimentações** (escopo do próprio setor) |
>
> Condição RBAC para "Movimentações": `pode_consultar_movimentacoes_estoque` (derivado de `_eh_almoxarifado` ou vínculo de setor).

### Utility navigation (top nav, extremidade direita)

```
[nome do usuário]   Sair
```

"Nome do usuário" mostra `user.nome`. Sem dropdown de perfil nesta fase.

### Secondary navigation

Não há sidebar. Dentro do detalhe da requisição: link `← Voltar` para lista de origem (preservado via query param `?next=`).

### Mobile navigation

Hamburger → dropdown simples via Alpine.js `x-show`. Links mesmos do desktop. Sem sidebar mobile.

## Content Hierarchy

### `/login/`
1. Campos de autenticação — ação primária da tela
2. Mensagem de erro de credencial (se existir) — bloqueia o fluxo
3. Copy institucional (título, subtítulo, helper) — orienta sem distrair
4. Footer restritivo — informação secundária

### `/requisicoes/minhas/`
1. Lista de requisições (número, estado, beneficiário, data, ação) — razão de estar na tela
2. Empty state com CTA "Nova Requisição" — próxima ação óbvia se lista vazia
3. Top nav — orientação e saída

### `/requisicoes/autorizacoes/`
1. Lista de requisições pendentes (número, beneficiário, setor, data enviada, qtd itens, "Analisar") — trabalho pendente
2. Empty state — confirmação de fila zerada
3. Top nav

### `/requisicoes/atendimentos/`
1. Lista de requisições a atender (número, beneficiário, setor, data autorizada, qtd itens, "Atender") — trabalho pendente
2. Empty state
3. Top nav

### `/requisicoes/<id>/`
1. Cabeçalho (número, estado, beneficiário, setor, criador, datas) — contexto da decisão
2. Itens (tabela com colunas por estado) — objeto da operação
3. Ações disponíveis — trabalho do usuário neste momento
4. Timeline — auditoria e contexto histórico

## User Flows

### Solicitante cria e acompanha requisição

```
1. Login → / → redirect → /requisicoes/minhas/
2. Clica "Nova Requisição" → /requisicoes/nova/ [escopo futuro]
3. Preenche itens, submete → POST → redirect → /requisicoes/<id>/
4. Clica "Enviar para autorização" → POST → redirect → /requisicoes/<id>/ (estado: aguardando)
5. Acompanha em /requisicoes/minhas/
6. Notificado quando autorizada/recusada
```

### Chefe de setor autoriza requisição

```
1. Login → / → redirect → /requisicoes/autorizacoes/
2. Vê fila de requisições aguardando autorização do seu setor
3. Clica "Analisar" → /requisicoes/<id>/
4. Lê cabeçalho + itens + timeline
5. Decide:
   - "Autorizar" → POST → redirect → /requisicoes/<id>/ (estado: autorizada)
   - "Recusar" → abre modal → preenche motivo → POST → redirect → /requisicoes/<id>/ (estado: recusada)
```

### Almoxarife atende requisição

```
1. Login → / → redirect → /requisicoes/atendimentos/
2. Vê fila de requisições autorizadas
3. Clica "Atender" → /requisicoes/<id>/
4. Lê cabeçalho + itens + timeline
5. Clica "Separar para retirada" → POST → redirect → /requisicoes/<id>/ (estado: pronta_para_retirada)
6. Clica "Atender" → /requisicoes/<id>/atender/ [escopo futuro]
7. Preenche quantidades entregues por item → POST → redirect → /requisicoes/<id>/ (estado: atendida)
```

### Criador cancela requisição

```
1. Acessa /requisicoes/minhas/
2. Clica "Ver" na requisição → /requisicoes/<id>/
3. Clica "Cancelar" → modal com justificativa (se exigida pelo estado)
4. Confirma → POST → redirect → /requisicoes/<id>/ (estado: cancelada)
```

## Naming Conventions

Labels usadas na interface. Mapeiam os termos do `CONTEXT.md` para o contexto visual.

| Conceito (CONTEXT.md) | Label na UI | Notas |
|---|---|---|
| Requisição | Requisição | Nunca "pedido", "solicitação" |
| Numero público | REQ-2026-0042 | Formatado; fallback "Rascunho" |
| Solicitante | (implícito) | Nunca aparece como label de papel |
| Beneficiário | Beneficiário | Nome + matrícula |
| Criador | Criado por | Campo de cabeçalho |
| Setor beneficiário | Setor | No detalhe; no contexto de autorização "Setor" é sempre o do beneficiário |
| Aguardando autorização | Aguardando autorização | Badge de estado; nunca "pendente" |
| Pronta para retirada | Pronta para retirada | Nunca "separada", "pronta" sozinho |
| Chefe de setor | (implícito) | Papel derivado; não aparece como label |
| Auxiliar de almoxarifado | (implícito) | Idem |
| Enviar para autorização | Enviar para autorização | Botão; nunca "submeter" |
| Retornar para rascunho | Retornar para rascunho | Botão; nunca "rejeitar", "voltar" |
| Separar para retirada | Separar para retirada | Botão |
| Atendimento parcial | Atendimento parcial | Label de evento de timeline |

## Component Reuse Map

| Componente | Usado em | Variações |
|---|---|---|
| Top nav global | Todas as telas pós-login | Links condicionais por papel |
| Badge de estado | Listas + detalhe | Mesmo mapeamento cor/label |
| Tabela de requisições | Minhas Req, Fila Auth, Fila Atend | Colunas diferem por tela |
| Empty state | As 3 listas | Copy diferente; CTA só em Minhas Req |
| Modal de confirmação | Detalhe (recusa, cancel, estorno) | Textarea obrigatório vs opcional |
| Feed de timeline | Detalhe | — |
| `_messages.html` | Todas as telas | Já existe; integrado ao chrome |
| Link `← Voltar` | Detalhe | Query param `?next=` preserva origem |

## Content Growth Plan

| Seção | Crescimento esperado | Estratégia |
|---|---|---|
| Minhas Requisições | Cresce com o tempo (histórico do usuário) | Paginação + filtro por estado (fase seguinte) |
| Fila de Autorização | Fluxo contínuo; itens saem ao autorizar/recusar | Sem paginação inicial; fila tende a ser pequena |
| Fila de Atendimentos | Idem fila de autorização | Idem |
| Timeline | Cresce por requisição (13 eventos possíveis) | Sem paginação; quantidade é razoável por requisição |

## URL Strategy

### Padrões

```
/requisicoes/                    → namespace `requisicoes`
/requisicoes/minhas/             → lista por papel
/requisicoes/autorizacoes/       → fila de autorização
/requisicoes/atendimentos/       → fila de atendimento
/requisicoes/nova/               → criação
/requisicoes/<id>/               → detalhe (pk numérico)
/requisicoes/<id>/editar/        → edição de rascunho
/requisicoes/<id>/atender/       → formulário de atendimento
/requisicoes/<id>/devolucao/     → registro de devolução
```

### Regras

- Slugs em PT-BR — conforme AGENTS.md.
- `<id>` é o `pk` numérico da `Requisicao`. Nunca expor `numero_publico` como segmento de URL (pode ser nulo em rascunho).
- Sem query params para navegação básica. `?next=<url>` apenas para preservar origem no link "← Voltar".
- Filtros e ordenação nas listas: query params (`?estado=`, `?ordem=`) — fase seguinte.
- App namespace: `requisicoes` em `urls.py` com `app_name = 'requisicoes'`.
- Root URL config inclui: `path('requisicoes/', include('apps.requisicoes.urls'))`.

### Reversão de URLs (Django)

```python
reverse('requisicoes:minhas')
reverse('requisicoes:autorizacoes')
reverse('requisicoes:atendimentos')
reverse('requisicoes:detalhe', args=[requisicao.pk])
reverse('requisicoes:atender', args=[requisicao.pk])
```
