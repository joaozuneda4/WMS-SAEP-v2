# Plano — issue #80: configuração única de navegação (side nav + drawer)

Epic: #68 — Extração de componentes do design system (auditoria 2026-07)

## Escopo

**Muda:**
- `apps/core/templatetags/core_tags.py`: novo `simple_tag(takes_context=True)` `secoes_navegacao` que devolve a estrutura de navegação (seções → itens), filtrando itens pelas flags de permissão já presentes no contexto (lidas por nome, sem reimplementar policy).
- Estrutura de dados `NAVEGACAO` (lista de seções, cada uma com título, `aria_label` e itens `{url_name, rotulo, icone, flag, url_names_ativos?}`) e dict `ICONES` (nome → `d` do path SVG), ambos módulo-level em `core_tags.py`. Único lugar onde um item de nav é definido.
- `apps/core/templates/core/partials/_side_nav.html`: vira loop (~25 linhas) sobre `secoes_navegacao`, mantendo classes Tailwind, `role="list"`, espaçamento `mt-4`/`mt-6` entre seções.
- `apps/core/templates/core/_topbar_nav.html`: vira loop (~15 linhas) sobre `secoes_navegacao`, mantendo classes `app-bar__menu-*` e `aria-label` por seção.
- Unificação de capitalização: "Fila de autorizações" (sentence case) nos dois renderers — hoje diverge (drawer usa "Fila de Autorizações").

**Não muda:**
- `apps/requisicoes/context_processors.py` (`flags_de_papel`) — fonte das flags permanece a mesma, tag só lê `context.get(nome_da_flag)`.
- IA, ordem, rotas ou labels de conteúdo (exceto a unificação de capitalização acima, já prevista nos critérios de aceite).
- `apps/core/templates/base_auth.html` — continua incluindo os dois partials do mesmo jeito (`{% include "core/partials/_side_nav.html" %}` / `{% include "core/_topbar_nav.html" %}` dentro do `{% with current=... %}`).
- Nenhuma policy, service, selector ou model.
- Nenhuma dependência nova.

## Estrutura da tag

```python
NAVEGACAO = [
    {
        "titulo": "Requisições",
        "aria_label": "Requisições",
        "itens": [
            {"url_name": "requisicoes:nova_requisicao", "rotulo": "Nova requisição", "icone": "criar", "flag": None},
            {"url_name": "requisicoes:minhas", "rotulo": "Minhas requisições", "icone": "lista", "flag": None},
            {"url_name": "requisicoes:autorizacoes", "rotulo": "Fila de autorizações", "icone": "autorizacao", "flag": "pode_ver_fila_autorizacao"},
            {"url_name": "requisicoes:historico", "rotulo": "Histórico de requisições", "icone": "historico", "flag": "pode_consultar_historico_requisicoes"},
        ],
    },
    {
        "titulo": "Almoxarifado",
        "aria_label": "Almoxarifado",
        "itens": [
            {"url_name": "requisicoes:atendimentos", "rotulo": "Atendimento", "icone": "atendimento", "flag": "pode_ver_fila_atendimento"},
            {"url_name": "estoque:listar_saidas_excepcionais", "rotulo": "Saídas excepcionais", "icone": "saida", "flag": "pode_consultar_saidas_excepcionais"},
            {"url_name": "estoque:lista_materiais", "rotulo": "Catálogo de materiais", "icone": "catalogo", "flag": "pode_consultar_catalogo_estoque"},
            {"url_name": "estoque:historico_movimentacoes", "rotulo": "Movimentações", "icone": "movimentacao", "flag": "pode_consultar_movimentacoes_estoque"},
            {
                "url_name": "estoque:preview_importacao_scpi",
                "rotulo": "Importar SCPI",
                "icone": "importar",
                "flag": "pode_visualizar_preview_scpi",
                "url_names_ativos": [
                    "estoque:preview_importacao_scpi",
                    "requisicoes:confirmar_importacao_scpi",
                    "estoque:sucesso_importacao_scpi",
                ],
            },
            {"url_name": "estoque:historico_importacoes_scpi", "rotulo": "Histórico de importações SCPI", "icone": "historico", "flag": "pode_consultar_historico_scpi"},
        ],
    },
]
```

`secoes_navegacao(context)`:
- Para cada seção, filtra itens cujo `flag` é `None` ou `context.get(flag)` é truthy.
- Descarta seções sem itens visíveis (reproduz o `{% if pode_x or pode_y ... %}` que hoje envolve o bloco "Almoxarifado").
- Cada item devolvido carrega `icone_path` (lookup em `ICONES`) e `url_names_ativos` (o próprio `url_names_ativos` do item, ou `[url_name]` como default).
- Constrói dicts/listas **novos** a cada chamada (não muta `NAVEGACAO`/`ICONES` module-level nem retorna referências diretas aos itens originais) — evita vazamento de estado entre requisições/threads, já que os módulos Django são carregados uma vez por processo.
- Registrada com `{% simple_tag(takes_context=True) %}`, usada como `{% secoes_navegacao as secoes %}` — permite reaproveitar em ambos os partials sem duplicar a leitura de flags.

## Arquivos tocados

- `apps/core/templatetags/core_tags.py` — nova tag + `NAVEGACAO` + `ICONES` (edição).
- `apps/core/templates/core/partials/_side_nav.html` — reescrito como loop (edição).
- `apps/core/templates/core/_topbar_nav.html` — reescrito como loop (edição).
- `apps/core/tests/test_navegacao.py` — novo arquivo de teste (tag pura, sem DB) + testes de paridade side/topbar via `render_to_string`.
- Sem migrations, sem CSS novo (classes Tailwind reaproveitadas, nenhuma classe nova).

## Estratégia de testes

1. **Tag pura** (`apps/core/tests/test_navegacao.py`, sem DB):
   - `secoes_navegacao` com contexto sem nenhuma flag → só itens sem `flag` aparecem (2 na seção Requisições); seção Almoxarifado ausente.
   - Cada flag ligada individualmente → item correspondente aparece.
   - Item SCPI: `current` igual a qualquer um dos 3 `url_names_ativos` → tratado como ativo pelo template (verificado via `render_to_string` com contexto simulando `current`).
   - Todas as flags ligadas → todas as seções/itens presentes, na ordem original.
   - **Validação de configuração**: para todo item em `NAVEGACAO`, `item["icone"]` existe em `ICONES` e o valor é uma string de path SVG não vazia (typo em `icone` não pode passar silenciosamente).
   - **URLs resolvíveis**: com todas as flags habilitadas, `render_to_string` do resultado completo não lança `NoReverseMatch` — cobre todo `url_name` e todo `url_names_ativos` da estrutura contra as URLs reais do projeto.
   - **Não mutação**: chamar `secoes_navegacao` com dois contextos consecutivos (ex.: flags diferentes) e confirmar que os containers mutáveis retornados no primeiro contexto (lista de seções, lista de itens, lista `url_names_ativos`) mantêm identidade distinta da segunda chamada e não apontam para os mesmos objetos de `NAVEGACAO`/`ICONES` — sem vazamento de estado entre requisições. `icone_path` é `str` (imutável); validar só por igualdade de valor, não de identidade.
2. **Paridade via view (com DB)**, reaproveitando fixtures existentes (`solicitante`, `chefe_obras`, `chefe_almoxarifado`, `superuser`) em `apps/requisicoes/tests/test_views.py` ou teste novo dedicado:
   - Mesmo conjunto de rótulos visíveis simultaneamente no HTML da sidebar e do drawer, para cada papel.
   - `aria-current="page"` presente exatamente no item ativo (incluindo as 3 rotas do trio SCPI) em ambos os renderers.
   - Capitalização "Fila de autorizações" idêntica nos dois HTMLs.
3. Suíte completa (`uv run pytest ...`) deve permanecer verde. Verificado por grep (`rg "Fila de [Aa]utoriza"` em `apps/**/tests/`): nenhuma asserção existente depende da capitalização antiga "Fila de Autorizações" — `test_fila_autorizacao_chefe_renderiza_apenas_setor` e `test_fila_autorizacao_superuser_ve_todos_setores` (`apps/requisicoes/tests/test_views.py:1027,1048`) checam a string `'Fila de autorização'` (singular, título de página, não o item de nav), que não é afetada pela mudança de capitalização do item de nav plural. `TestNavHistoricoRequisicoes` e `test_side_nav_renderiza_links_para_autenticado` checam outros textos (`'Histórico de requisições'`, `'hidden lg:flex'`, `'Navegação principal'`), também não afetados. Nenhuma asserção existente precisa de ajuste; se a suíte revelar alguma dependência não mapeada aqui, ela será corrigida durante a fase de implementação e documentada no PR.

## Invariantes (docs/design-acesso-rapido/matriz-invariantes.md)

- Flags de permissão continuam controlando visibilidade de item de nav por papel — nenhuma flag nova, nenhuma policy nova; a tag só lê o contexto.
- `aria-current="page"` correto por rota, incluindo o trio SCPI.
- `role="list"` na sidebar e `aria-label` por seção no drawer preservados.

## Riscos

- **Nomes de flag como string**: erro de digitação em `flag` quebra silenciosamente a visibilidade de um item (vira sempre oculto, já que `context.get` com chave errada devolve `None`/falsy). Mitigado pelos testes de tag pura que cobrem as 8 flags uma a uma.
- **`{% url item.url_name %}` com nome inválido**: `NoReverseMatch` em runtime se algum `url_name` estiver errado — mitigado pelos mesmos testes (renderizam via view real, que já resolve todas as URLs).
- Nenhum risco de concorrência, contrato OpenAPI ou migração de estado — mudança é puramente de apresentação (templates + template tag), sem tocar `models`/`services`/`policies`.
