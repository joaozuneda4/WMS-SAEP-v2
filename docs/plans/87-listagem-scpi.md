# Plano — Issue #87 (PR 3/3): `historico_importacoes_scpi.html` → padrão de listagem

Epic: #68. PR 1/3 (`apps/requisicoes`) e PR 2/3 (`apps/estoque` — históricos +
materiais) entregues em
[joaozuneda4/WMS-SAEP-v2#6](https://github.com/joaozuneda4/WMS-SAEP-v2/pull/6)
e [joaozuneda4/WMS-SAEP-v2#7](https://github.com/joaozuneda4/WMS-SAEP-v2/pull/7),
ambos CodeRabbit `SUCCESS`. Este plano cobre o PR 3/3, último da issue #87.

## Roadmap da issue #87

- ~~PR 1 — `apps/requisicoes`.~~ Entregue.
- ~~PR 2 — `apps/estoque` históricos + materiais.~~ Entregue.
- **PR 3 (este)** — `estoque/historico_importacoes_scpi.html`.

## Escopo (PR 3)

**Entra:**
- `apps/estoque/templates/estoque/historico_importacoes_scpi.html` — adota
  `components/table.html#th` nos 8 cabeçalhos; adiciona
  `<caption class="sr-only">`; corrige wrapper (`overflow-hidden` →
  `overflow-x-auto`, adiciona `shadow-sm`). Ver "Decisão de design" abaixo —
  **não** adota `#tabela_abertura` nem `#cards_abertura`/`#card_abertura`.
- `apps/estoque/tests/test_views.py` — adiciona teste de caption (mesmo
  padrão dos PRs 1 e 2).

**Não entra (conforme a issue, explícito):**
- Cards mobile — a issue registra isso como "possível melhoria futura", fora
  de escopo deste PR. A tela permanece tabela-única em todos os viewports,
  como já é hoje.
- Colunas/copy/ordem de campos.
- `selectors.py`, `policies.py`, `services.py`.
- Demais telas (PR 1 e 2, já entregues).

## Decisão de design — por que não usar `#tabela_abertura`

O fragmento `components/table.html#tabela_abertura` é
`hidden overflow-x-auto ... sm:block` — **escondido em mobile por design**,
porque em toda tela já migrada (#83, PR 1, PR 2) existe um `#cards_abertura`
irmão que assume a apresentação em telas estreitas. Nesta tela isso não
existe hoje e a issue explicitamente tira "cards mobile" do escopo. Se eu
usasse `#tabela_abertura` aqui, o resultado seria: **tabela invisível em
mobile, sem nada no lugar** — uma regressão ativa (hoje a tabela aparece em
todos os viewports, espremida mas visível). Isso violaria "Paridade visual"
do próprio critério de aceite da issue.

Em vez disso:
1. **Wrapper fica literal**, não usa `#tabela_abertura` — mantém visível em
   todos os viewports (comportamento atual preservado). Corrige 2 pontos
   reais do wrapper atual:
   - `overflow-hidden` → `overflow-x-auto`: a tabela tem 8 colunas; em
     viewport estreito hoje o conteúdo excedente é **cortado e inacessível**
     (sem scroll, sem card). Trocar para `overflow-x-auto` habilita rolagem
     horizontal — melhoria real de usabilidade, não só estética, e
     ortogonal à decisão de não usar `#tabela_abertura` (não depende do
     `hidden`/`sm:block`).
   - Adiciona `shadow-sm`, ausente hoje — consistência visual com as 6 telas
     já migradas (#83, PR 1, PR 2), todas usam a mesma sombra no wrapper de
     tabela.
   - **A classe do `<table>` em si (`w-full text-sm`) não muda.** Cogitei
     alinhar com o canônico (`min-w-full divide-y divide-slate-200`, sem
     `text-sm`), mas 5 das 8 colunas (Usuário, Data/Hora, Linhas, Novos,
     Divergentes) não declaram tamanho de fonte próprio — dependem do
     `text-sm` da tabela, exatamente o mesmo padrão do PR 2
     (`lista_materiais`). Lá a correção se justificava por eliminar uma cor
     errada (`slate-600`→`500`, drift real). Aqui `text-sm` no `<table>` não
     é "errado", só uma forma diferente e já correta de aplicar o mesmo
     tamanho — mudar só para bater com o canônico, dado que o wrapper já é
     uma exceção registrada (decisão 1), adicionaria risco sem ganho. Fica
     como está.
2. **Cabeçalhos usam `#th`** — isso é seguro independente da decisão acima:
   o fragmento `#th` não carrega nenhuma lógica de `hidden`/responsividade,
   só a `<th scope="col">` canônica. Adoção corrige um gap real de
   acessibilidade: os `<th>` atuais **não têm `scope="col"`** (classes vivem
   na `<tr>` pai, cada `<th>` só tem `class="px-4 py-3"`, sem `scope`). Os 5
   cabeçalhos textuais (Arquivo, Hash, Usuário, Data/Hora, Status) usam `#th`
   default (esquerda); os 3 numéricos (Linhas, Novos, Divergentes) usam
   `alinhamento="direita"`.
3. **`<caption class="sr-only">` substitui o `aria-label` do `<table>`**. O
   `<table aria-label="Histórico de importações SCPI">` atual dá nome
   acessível à tabela, mas diverge do contrato estabelecido
   (`docs/design-system.md` §8: "a tela chamadora fornece [a caption]").
   Manter os dois seria redundante (seletores de acessibilidade preferem
   `aria-label` sobre `<caption>` quando ambos presentes, tornando a caption
   nova muda). Ação: **remove o `aria-label`**, adiciona
   `<caption class="sr-only">Histórico de importações SCPI, mais recente
   primeiro.</caption>` — mesmo texto informativo, agora no canal canônico
   do projeto. Nenhum teste atual verifica esse `aria-label` (`grep` em
   `test_views.py` confirma zero ocorrência) — sem regressão de asserção.
4. **`cards_abertura`/`card_abertura` não entram** — não há apresentação
   mobile a compor. Registrado aqui, não como omissão: quando a melhoria
   futura de cards mobile for implementada (issue própria, fora deste
   escopo), ela deve então adotar `#tabela_abertura` completo (com `hidden
   ... sm:block`) + `#cards_abertura`/`#card_abertura`, revertendo a exceção
   1 acima.

## Arquivos tocados

| Arquivo | Mudança |
|---|---|
| `apps/estoque/templates/estoque/historico_importacoes_scpi.html` | `<th>` via `#th` (8 colunas); `<caption sr-only>` substitui `aria-label`; wrapper corrige `overflow-x-auto` + `shadow-sm` (literal, sem `#tabela_abertura`); `<table>`/`<td>` inalterados. |
| `apps/estoque/tests/test_views.py` | Teste novo de caption em `TestHistoricoImportacoesScpiView`. |

## Estratégia de testes (ADR-0010)

1. **Regressão de conteúdo** — suíte existente
   (`TestHistoricoImportacoesScpiView`, 8 testes: 200/403/302/405,
   `test_exibe_metadados_da_importacao`, `test_nao_expoe_csv_bruto`)
   permanece verde sem alteração de asserção — nenhuma delas verifica
   `aria-label` ou classes de `<th>`/wrapper.
2. **Teste novo obrigatório** — `test_tabela_tem_caption_sr_only` (mesmo
   padrão dos PRs 1/2: cardinalidade + texto, desacoplado de whitespace
   exato, conforme achado do CodeRabbit no PR 2):
   ```python
   def test_tabela_tem_caption_sr_only(
       self, client, superuser, estoque_principal
   ):
       from apps.estoque.models import ImportacaoSCPI, StatusImportacaoSCPI

       ImportacaoSCPI.objects.create(
           arquivo_nome='relatorio.csv',
           arquivo_hash='a' * 64,
           importado_por=superuser,
           estoque=estoque_principal,
           status=StatusImportacaoSCPI.CONCLUIDA,
       )
       client.force_login(superuser)
       resp = client.get(self.URL)
       conteudo = resp.content.decode()
       assert conteudo.count('<caption class="sr-only">') == 1
       assert 'Histórico de importações SCPI, mais recente primeiro.' in conteudo
   ```
3. **Teste novo obrigatório** — regressão de markup para a decisão central
   deste PR (wrapper não usa `#tabela_abertura`): sem ele, um futuro reuso
   descuidado do fragmento canônico reintroduziria `hidden`/`sm:block` e
   esconderia a tabela em mobile silenciosamente, sem quebrar nenhum teste
   existente.
   ```python
   def test_wrapper_nao_usa_chrome_hidden_em_mobile(
       self, client, superuser, estoque_principal
   ):
       from apps.estoque.models import ImportacaoSCPI, StatusImportacaoSCPI

       ImportacaoSCPI.objects.create(
           arquivo_nome='relatorio.csv',
           arquivo_hash='b' * 64,
           importado_por=superuser,
           estoque=estoque_principal,
           status=StatusImportacaoSCPI.CONCLUIDA,
       )
       client.force_login(superuser)
       resp = client.get(self.URL)
       conteudo = resp.content.decode()
       assert (
           '<div class="overflow-x-auto rounded-xl border border-slate-200 '
           'bg-white shadow-sm">' in conteudo
       )
       assert 'sm:block' not in conteudo
   ```
4. **Paridade visual** — mobile 375px + desktop, com e sem importações
   registradas. Foco em confirmar que a tabela **continua visível em
   mobile** (não escondida) — é o risco central desta decisão de design;
   complementa o teste de markup acima com verificação visual real.

## Invariantes relevantes (`docs/matriz-invariantes.md`)

- RBAC: `exigir_pode_consultar_historico_scpi` intocado — só
  template/markup muda.
- Sem HTMX nesta tela (confirmado: `historico_importacoes_scpi_view` não usa
  `is_htmx`/`paginar_com_filtros`) — nenhum contrato de swap a preservar.
- CSV bruto não exposto: `test_nao_expoe_csv_bruto` cobre isso e não é
  afetado por mudança de chrome.

## Riscos

- **Baixo.** Menor superfície de mudança dos 3 PRs (1 arquivo de template).
  Risco real único: regressão de visibilidade mobile se a decisão acima for
  ignorada e `#tabela_abertura` for usado por engano — mitigado por
  verificação visual explícita em 375px antes do PR final.
- Remoção do `aria-label` em favor de `<caption>`: risco de regressão de
  acessibilidade é baixo — `<caption>` é o mecanismo mais amplamente
  suportado para nome acessível de tabela (HTML padrão, não depende de
  ARIA), e é o contrato já usado nas outras 6 telas migradas.

## Guardrails

- Padrão de #83 é lei — a exceção desta tela (decisão de design acima) é
  registrada, não uma variante nova de chrome; segue o mesmo espírito das
  exceções documentadas nos PRs 1 e 2 (`<th>` literal quando o fragmento não
  serve, aqui: chrome de container literal quando não há par mobile).
- ARIA inegociável: `caption sr-only` novo, `scope="col"` em todos os `<th>`
  (ganho de acessibilidade desta migração).
- Tailwind v4 JIT + `npm run css:build` — `shadow-sm`/`overflow-x-auto` já
  devem estar compilados (classes usadas em outras telas); rodar para
  confirmar zero diff inesperado.
- Escopo fechado: 1 template + 1 arquivo de teste.
- Zero dependência nova.
- Branch: `refactor/listagem-scpi-historico`.
- Verde antes do PR final:
  `uv run pytest -q -ra --tb=short --strict-markers --disable-warnings -n logical`,
  `uv run ruff format .`, `uv run ruff format --check .`,
  `uv run ruff check .`, `uv run mypy apps`, `npm run css:build` (zero diff
  esperado em `app.css`).
- PT-BR em identificadores, comentários e copy.
