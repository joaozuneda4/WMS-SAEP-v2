# Plano — #76 `components/button.html` + adoção nas listagens

## Escopo

**Entra:**
- Novo `apps/core/templates/components/button.html`, componente global sem semântica de domínio.
- Adoção nas 5 telas de listagem citadas na issue:
  - `apps/requisicoes/templates/requisicoes/fila_atendimento.html` (2 botões "Atender": card mobile + linha de tabela)
  - `apps/requisicoes/templates/requisicoes/fila_autorizacao.html` (2 botões "Analisar")
  - `apps/estoque/templates/estoque/lista_saidas_excepcionais.html` (2 "Ver detalhe" + CTA "Nova saída excepcional")
  - `apps/requisicoes/templates/requisicoes/partials/_tabela_historico_requisicoes.html` (2 "Ver detalhes"/"Ver")
  - `apps/requisicoes/templates/requisicoes/lista_minhas.html` (2 "Ver detalhes"/"Ver" — correção de drift a11y)
- Ajuste pontual em `apps/core/templates/components/empty_state.html`: o branch do CTA primário (`cta_secundario` falso) passa a delegar para `components/button.html` com `variant="primary"`, porque é o único lugar onde a CTA "Nova saída excepcional" é de fato renderizada — sem esse ajuste a adoção da issue em `lista_saidas_excepcionais.html` fica incompleta. **Requisito é paridade funcional/visual, não byte-a-byte**: o CTA atual usa `focus-visible:ring-offset-2` e não tem `justify-center`; as invariantes do componente (issue #76) mandam `ring-offset-1` + `justify-center` para todos os variants. A migração normaliza o CTA para essas invariantes — mesmo espírito da correção de drift já declarada para `lista_minhas.html` (ring offset menor, ainda visível e com contraste AA; `justify-center` é no-op visual em botão de largura única). Teste existente `test_minhas_vazia_exibe_empty_state_com_cta_canonico` cobre `min-h-11`/`focus-visible:ring-blue-500` hoje; ganha asserções novas nesta issue (`justify-center` presente, `ring-offset-1` presente/`ring-offset-2` ausente — ver seção Estratégia de testes) para provar que a normalização aconteceu de fato, não só na documentação.

**Não entra (fora de escopo, conforme issue):**
- `requisicoes/detalhe.html`, formulários, modais.
- Parâmetro `loading`: **não faz parte do contrato desta fatia** — não está entre os 15 parâmetros listados abaixo, não é implementado, não é testado. É recurso futuro (depende de `form-submit.js`, issue #73), citado aqui só para registrar que foi considerado e descartado nesta fatia — não há contradição: `loading` simplesmente não existe no componente entregue por esta issue.
- Qualquer mudança de comportamento em services/policies/selectors.

**Inventário de consumidores de `empty_state.html` afetados pela normalização de invariantes do CTA primário** (7 templates usam o componente; só 2 usam o branch do CTA primário — `cta_secundario` ausente/falso — que muda de classe):

| Template | Branch usado | Afetado pela normalização? |
|---|---|---|
| `lista_minhas.html` | CTA primário (`cta_url`+`cta_label`) | Sim — dentro do escopo desta issue, testado em `test_minhas_vazia_exibe_empty_state_com_cta_canonico` |
| `estoque/lista_saidas_excepcionais.html` | CTA primário (`cta_url`+`cta_label`) | Sim — dentro do escopo desta issue, testado em `test_empty_state_cta_delega_para_componente_button` |
| `estoque/lista_materiais.html` | CTA secundário (`cta_secundario=True`, variant `link`) | Não — branch diferente, classes inalteradas |
| `estoque/partials/_tabela_movimentacoes.html` | Sem CTA (`cta_url` ausente) | Não — bloco de CTA nem renderiza |
| `fila_atendimento.html` | Sem CTA | Não |
| `fila_autorizacao.html` | Sem CTA | Não |
| `_tabela_historico_requisicoes.html` | Sem CTA | Não |

Conclusão: os únicos 2 consumidores afetados pela mudança de classes já estão cobertos por teste de regressão nesta própria issue — não há consumidor fora de escopo impactado.

## Parâmetros do componente

Baseado na spec da issue (mais específica que o inventário genérico de `docs/design-system.md` §1). **Divergência intencional registrada**: `danger-outline` não existe em `docs/design-system.md` §1 nem em `.design/TASKS.md` — a issue #76 pede essa variante explicitamente ("variante real usada nas ações destrutivas do detalhe"), então o corpo da issue é a fonte de verdade para esta fatia. Atualizar `docs/design-system.md`/`.design/TASKS.md` fica fora do escopo fechado desta issue (componente + 5 templates); registrado aqui para não ser tratado como esquecimento.

```text
variant           default=primary (primary, secondary, danger, danger-outline, ghost, link)
size              default=md (sm, md)
type              default=button (button, submit) — só relevante quando href ausente
label             obrigatório
href              opcional — presente renderiza <a>, ausente renderiza <button>
disabled          opcional (boolean) — só <button>
icon_template     opcional — caminho de partial incluído antes do label
full_width_mobile opcional (boolean) — aplica w-full sm:w-auto
aria_label        opcional — sobrescreve accessible name (necessário p/ "Atender requisição REQ-2026-001")
class             opcional — passthrough para ajuste de layout do chamador
hx_get/hx_post/hx_target/hx_swap  opcionais — passthrough HTMX literal, renderizados com hífen (`hx_get`→`hx-get`, `hx_post`→`hx-post`, `hx_target`→`hx-target`, `hx_swap`→`hx-swap`; nome com underscore é só o parâmetro do template, HTMX exige o atributo HTML com hífen) (sem uso nesta fatia; nenhum dos 5 templates-alvo usa HTMX no botão. Contrato PRG/`HX-Redirect` de `docs/CONVENTIONS.md` é responsabilidade da view consumidora quando esses parâmetros forem adotados — fora do escopo desta issue)
data_modal_trigger opcional — passthrough para abertura de modal via Alpine
```

15 parâmetros nominais (`variant`, `size`, `type`, `label`, `href`, `disabled`, `icon_template`, `full_width_mobile`, `aria_label`, `class`, `hx_get`, `hx_post`, `hx_target`, `hx_swap`, `data_modal_trigger`), acima do guia de "~10" da issue. Não há decisão errada de abstração aqui — os itens acima (exceto `hx_*`/`icon_template`/`data_modal_trigger`, sem uso nesta fatia) são requisitos explícitos do corpo da issue #76, não inferência própria. Registrar isso no PR conforme pedido no critério de aceite ("se precisar de mais, parar e registrar no PR").

### Classes literais por variant × size

Tabela de referência para implementação e testes (todas as classes abaixo se somam às invariantes comuns da seção seguinte):

| variant | classes de cor/estado |
|---|---|
| primary | `bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800 focus-visible:ring-blue-500` |
| secondary | `bg-white text-slate-700 border border-slate-300 hover:bg-slate-50 hover:text-slate-900 focus-visible:ring-blue-500` |
| danger | `bg-red-600 text-white hover:bg-red-700 active:bg-red-800 focus-visible:ring-red-500` |
| danger-outline | `bg-white text-red-700 border border-red-300 hover:bg-red-50 focus-visible:ring-red-500` |
| ghost | `bg-transparent text-slate-700 hover:bg-slate-100 focus-visible:ring-blue-500` |
| link | `bg-transparent text-blue-700 hover:underline focus-visible:ring-blue-500 min-h-0` (link não força `min-h-11`/`justify-center` — não é um alvo de toque no sentido dos demais variants, segue o padrão já usado em `empty_state.html` para `cta_secundario`) |

| size | classes de padding/tipografia |
|---|---|
| sm | `px-3 py-2 text-xs` |
| md (default) | `px-3 py-2 text-sm` |

`full_width_mobile=True` soma `w-full sm:w-auto` à classe final.

## Estrutura de implementação

Seguir o padrão já estabelecido em `components/badge.html`: cadeia de `{% if %}/{% elif %}` com classes Tailwind sempre literais (nunca `bg-{{ variant }}-600`), para respeitar o JIT do Tailwind v4. Como `button.html` tem dois eixos independentes (variant × size) em vez de um único eixo (badge só tem `variant`), a composição usa fragmentos literais por eixo (variant decide cor/estado/ring; size decide padding/tipografia), concatenados no mesmo atributo `class` — cada fragmento continua sendo uma string literal completa dentro do arquivo-fonte, então o scanner textual do Tailwind ainda encontra os tokens.

Tag: `{% if href %}<a href="{{ href }}" ...>{% else %}<button type="{{ type|default:'button' }}" ...>{% endif %}`.

Invariantes (issue): `inline-flex items-center justify-center min-h-11 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1` + ring da cor do variant; `disabled:cursor-not-allowed disabled:opacity-60` no branch `<button>`.

## Correção de drift declarada

`lista_minhas.html:62,107` hoje usa `py-1.5` sem `min-h-11` e `focus:` em vez de `focus-visible:`. Ao migrar para `components/button.html` com `variant="secondary"` `size="sm"` (linha de tabela) / `size="md"` (card mobile), o botão ganha automaticamente `min-h-11` e `focus-visible:ring-2`. Mudança visualmente perceptível e intencional — não é regressão.

Demais 4 telas já usam `min-h-11`/`focus-visible:` — adoção deve ser visualmente idêntica (paridade de classes finais).

## Estratégia de testes

Duas camadas de teste:

**1. Testes diretos do componente** (novo `apps/core/tests/test_components.py`, via `django.template.loader.render_to_string("components/button.html", {...})`), cobrindo matriz mínima:
- Ramo `<a>` (com `href`) vs ramo `<button>` (sem `href`): tag renderizada correta em cada caso.
- `type="submit"` vs default `"button"` no ramo `<button>`.
- `disabled=True` aplica o atributo booleano `disabled` na tag `<button>` (asserção sobre a tag de abertura, não apenas as classes `disabled:*` — que aparecem sempre, disabled ou não) + `disabled:cursor-not-allowed disabled:opacity-60`. `disabled=False`/ausente não aplica o atributo.
- Cada `variant` (primary, secondary, danger, danger-outline, ghost, link) produz as classes de cor esperadas.
- Cada `size` (sm, md) produz padding/tipografia esperados.
- `full_width_mobile=True` aplica `w-full sm:w-auto`; ausente/False não aplica.
- `aria_label` sobrescreve o texto acessível (`aria-label` no HTML) mantendo `label` como texto visível.
- `hx_get`/`hx_post`/`hx_target`/`hx_swap` passthrough renderizam como os atributos HTML `hx-get`/`hx-post`/`hx-target`/`hx-swap` (hífen, não underscore — exigência do HTMX) quando fornecidos; ausentes por padrão. Teste asserta o nome exato do atributo HTML gerado, não o nome do parâmetro do template.
- `icon_template` incluído antes do `label` quando fornecido; ausente por padrão (nenhum ícone renderizado).
- `class` passthrough é mesclado (append) às classes do componente, nunca substitui as invariantes/variant/size.
- `data_modal_trigger` renderiza literalmente como `data-modal-trigger="{{ data_modal_trigger }}"` quando fornecido.
- `label` é obrigatório por contrato, mas **não é validado em tempo de renderização** — Django não oferece validação nativa de parâmetros obrigatórios em `{% include %}`. Regra explícita (resolve a ambiguidade "obrigatório" vs. comportamento real): omitir `label` é responsabilidade do chamador, não do componente; o componente não substitui por um fallback textual (não inventa "Botão" ou texto genérico). Dois testes cobrem isso: (1) cenário real — botão só-com-ícone (`icon_template` + `label=""`) usa `aria_label` como nome acessível, prova que o padrão suportado para "sem texto visível" é `icon_template`+`aria_label`, não omitir tudo; (2) cenário de uso inválido — contexto totalmente vazio (sem `label` nem `aria_label`) não produz `aria-label` nem mascara com texto genérico, documentando que esse caminho é responsabilidade do chamador. Todo consumidor desta issue (5 templates) sempre passa `label` ou `aria_label`; nenhum uso real depende do caminho (2).
- Invariantes comuns (`inline-flex items-center justify-center min-h-11 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1`) presentes em qualquer combinação, exceto o variant `link` (ver tabela de classes acima).

**2. Testes de integração nos consumidores** (camada view, ADR-0010), estendendo `apps/requisicoes/tests/test_views.py` e `apps/estoque/tests/test_views.py` — mesmo padrão já usado em `test_minhas_vazia_exibe_empty_state_com_cta_canonico` (regex sobre a tag renderizada, checando `href`, classes, `aria-label`):
- `lista_minhas`: card mobile e linha de tabela do botão "Ver detalhes"/"Ver" contêm `min-h-11` e `focus-visible:ring-blue-500` (prova da correção de drift) e preservam o `aria-label` composto existente — testado para requisição com `numero_publico` e para rascunho sem `numero_publico` (fallback por `pk`, caminho que exercita a conversão de tipo `int → str` no `aria_label`).
- `fila_atendimento`: botão "Atender" preserva `aria-label="Atender requisição {numero_publico}"` após migração.
- `fila_autorizacao`: botão "Analisar" preserva `aria-label="Analisar requisição {numero_publico}"` após migração.
- `lista_saidas_excepcionais`: botão "Ver detalhe" preserva `aria-label` composto — testado com `numero_publico` e com fallback por `pk` (mesma razão do fallback de `lista_minhas`); CTA "Nova saída excepcional" do empty state tem `min-h-11`/`justify-center`/`focus-visible:ring-offset-1` (sem `ring-offset-2`) após `empty_state.html` passar a delegar para `button.html`. `test_minhas_vazia_exibe_empty_state_com_cta_canonico` ganha as mesmas asserções para o consumidor `lista_minhas` — prova de que a normalização de invariantes descrita na seção Escopo realmente aconteceu (não só documentada) nos 2 consumidores afetados (ver inventário na seção Escopo).
- `_tabela_historico_requisicoes` (via view de histórico): botão "Ver detalhes"/"Ver" com `href` completo (incluindo `?next=` urlencoded) e classes esperadas.

Não há caso de erro/exceção de domínio a testar — componente é puramente de apresentação, sem `if` de domínio.

## Invariantes de domínio preservadas

Nenhuma — esta issue não toca `services`, `policies`, `selectors` ou regras de transição de estado. Apenas apresentação.

## Riscos

- Regressão visual sutil se `size`/`variant` mapeados incorretamente para as classes de padding/tipografia atuais (mobile usa `text-sm px-3 py-2`, desktop tabela usa `text-xs px-3 py-2`) — mitigado por verificação manual no browser (375px e desktop) antes de fechar, conforme critério de aceite.
- `empty_state.html` é usado por outras 6+ telas fora do escopo desta issue — a migração do branch do CTA primário troca `focus-visible:ring-offset-2` por `ring-offset-1` e adiciona `justify-center` (paridade funcional, não byte-a-byte — ver seção Escopo). `test_minhas_vazia_exibe_empty_state_com_cta_canonico` ganha novas asserções para essa mudança (ver seção Estratégia de testes) — não fica só documentada.
