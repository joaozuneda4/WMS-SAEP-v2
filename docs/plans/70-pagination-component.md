# Plano — issue 70 components/pagination.html

## Épico

Issue 68 — Fase 1 (fundações, alto ROI/baixo risco).

## Escopo

**Faz:**
- Criar `apps/core/templates/components/pagination.html`, parametrizado com
  `page_obj` (obrigatório), `querystring_filtros` (opcional),
  `rotulo_itens` (substantivo plural do contador, ex. "requisições") e
  `aria_label` (ex. "Paginação do histórico de requisições").
- Migrar os 2 pontos de uso:
  - `apps/requisicoes/templates/requisicoes/partials/_tabela_historico_requisicoes.html:121`
  - `apps/estoque/templates/estoque/partials/_tabela_movimentacoes.html:97`
- Apagar `apps/requisicoes/templates/requisicoes/partials/_paginacao_historico.html`
  e `apps/estoque/templates/estoque/partials/_paginacao.html`.

**Não faz:**
- Não muda UX de paginação (sem números de página, sem tamanho de página).
- Não toca views (`historico_requisicoes_view`, `historico_movimentacoes_view` etc.).
- Não introduz dependência nova.
- Componente global não conhece domínio — substantivo e aria-label chegam só
  por parâmetro, nunca por `if` de domínio dentro do componente.

## Estado atual (confirmado por leitura)

Os dois partials são idênticos exceto:
- `aria-label`: "Paginação do histórico de requisições" vs "Paginação das movimentações"
- Substantivo do contador: "requisições" vs "movimentações"

Ambos usados uma única vez cada, via `{% include ... with page_obj=... querystring_filtros=... %}`.
Nenhum outro `{% include %}` referencia esses partials (confirmado via grep
`_paginacao` em `apps/`).

## Arquivos tocados

| Arquivo | Ação |
|---|---|
| `apps/core/templates/components/pagination.html` | criar |
| `apps/requisicoes/templates/requisicoes/partials/_tabela_historico_requisicoes.html` | editar linha 121 (include) |
| `apps/estoque/templates/estoque/partials/_tabela_movimentacoes.html` | editar linha 97 (include) |
| `apps/requisicoes/templates/requisicoes/partials/_paginacao_historico.html` | apagar |
| `apps/estoque/templates/estoque/partials/_paginacao.html` | apagar |
| testes de template/view relevantes (se existirem, cobrindo paginação) | verificar cobertura, adicionar se ausente |

## Novo include

```django
{% include 'components/pagination.html' with page_obj=page_obj querystring_filtros=querystring_filtros rotulo_itens='requisições' aria_label='Paginação do histórico de requisições' %}
```

```django
{% include 'components/pagination.html' with page_obj=page_obj querystring_filtros=querystring_filtros rotulo_itens='movimentações' aria_label='Paginação das movimentações' %}
```

Markup do componente reproduz byte a byte a estrutura atual (mesmas classes
Tailwind, mesmo `aria-disabled="true"`, mesmo `min-h-11`, mesmo padrão de
`href`), trocando apenas o texto do `aria-label` do `<nav>` e o substantivo
fixo do contador pelas variáveis `{{ aria_label }}` e `{{ rotulo_itens }}`.

## Estratégia de teste

- Teste de view/HTMX que já cobre histórico de requisições paginado: confirmar
  que o HTML segue trazendo "Página X de Y · N requisições" e `aria-label`
  correto após a migração.
- Idem para movimentações de estoque: "N movimentações" e aria-label correto.
- Caso não exista teste de asserção de conteúdo HTML de paginação hoje,
  adicionar teste leve (via `assertContains`) checando presença de
  `aria-label="Paginação do histórico de requisições"` /
  `aria-label="Paginação das movimentações"` e do rótulo correto, para as duas
  telas, com múltiplas páginas (`num_pages > 1`) e com filtros ativos
  (querystring preservada no `href`).
- Confirmar que quando `num_pages == 1` nada é renderizado (comportamento
  atual, `{% if page_obj.paginator.num_pages > 1 %}` preservado).

## Invariantes relevantes

- Nenhuma regra de domínio/RBAC envolvida — é puramente apresentação.
- Camadas (ADR-0004/0011): componente de `apps/core/templates/components/`
  não pode importar nem depender de nada de `apps/requisicoes` ou
  `apps/estoque`; parâmetros resolvem toda a variação.

## Riscos

- Baixo risco: puramente de template, sem mudança de view/service/model.
- Risco de drift de markup: mitigado reproduzindo classes Tailwind e atributos
  ARIA exatamente como no partial original (nenhuma classe nova, logo sem
  necessidade de `npm run css:build`).
- Risco de `{% include %}` órfão: mitigado por grep de verificação final por
  `_paginacao` no repo antes de finalizar.

## Verificação manual

- Paginar Histórico de requisições com filtros ativos, via HTMX e via URL
  direta — filtros preservados, swap HTMX funciona.
- Paginar Movimentações de estoque com filtros ativos, via HTMX e via URL
  direta — mesmo comportamento.
