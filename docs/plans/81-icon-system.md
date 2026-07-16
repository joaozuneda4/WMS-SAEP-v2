# Plano — Issue #81: sistema de ícones `{% icon %}` com catálogo vendorizado

Épico: #68 (extração de componentes do design system, Fase 3).

## Escopo

### Dentro do escopo

- Template tag `{% icon name size=20 class="..." %}` em `apps/core/templatetags/core_tags.py`.
- Catálogo vendorizado: um SVG completo por arquivo em
  `apps/core/templates/components/icons/<nome>.svg`, sempre com `aria-hidden="true"`.
- Migração dos ícones repetidos ≥2× confirmados por grep no código atual (contagens do
  épico eram de uma auditoria anterior; recontadas aqui diretamente no código):

  | Nome no catálogo | Ocorrências atuais | Arquivos |
  |---|---|---|
  | `voltar` (back-arrow) | 6 | `copiar_confirmacao.html`, `rascunho_form.html` (×2), `atender_retirada.html`, `detalhe.html`, `nova_saida_excepcional.html` |
  | `lixeira` (variante modal de confirmação de exclusão) | 3 | `_modal_icon.html` (variant="danger"), `detalhe.html` (×2 — trigger mobile e desktop do mesmo modal) |
  | `remover` (variante de remover linha de item) | 2 | `_item_form_row.html`, `nova_saida_excepcional.html` |
  | `spinner` | 3 | `preview_importacao_scpi.html` (×3) |
  | `adicionar` (plus) | 2 | `rascunho_form.html`, `nova_saida_excepcional.html` |
  | `enviar` (send) | 2 | `detalhe.html`, `rascunho_form.html` |
  | `copiar` (copy) | 2 | `copiar_confirmacao.html`, `detalhe.html` |

- Testes unitários da tag em `apps/core/tests/test_icons.py`.

### Fora do escopo (decisões explícitas)

1. **`lixeira` vs `remover` são dois ícones distintos, não um só.** O épico rotula
   ambos como "lixeira ×4", mas são dois desenhos SVG visualmente diferentes (path
   diferente). Unificá-los sob um nome quebraria o critério de aceite "zero mudança
   visual". Cada um vira um arquivo próprio no catálogo.
2. **Contagem de `plus`**: o épico diz ×3; a recontagem via grep no código atual
   encontra 2 ocorrências reais (`rascunho_form.html`, `nova_saida_excepcional.html`).
   Tratado como ruído de auditoria antiga, não como mudança de escopo — migram-se as
   2 ocorrências reais.
3. **Ícones de navegação** (`ICONES`/`secoes_navegacao` em `core_tags.py`, usados por
   `_side_nav.html`/`_topbar_nav.html`, issue #80 já mesclada) **não migram nesta
   fatia**. Já não há duplicação de path SVG ali — cada ícone é definido uma vez no
   dict `ICONES` e reutilizado por chave; migrar para o novo catálogo não reduziria
   duplicação nenhuma e tocaria uma feature de nav recém-entregue sem necessidade.
4. **`components/icons/_check.html` e `_seta_circular.html`** (partials pré-existentes,
   só `<path>` sem `<svg>` wrapper, incluídos hoje via `icon_template` do
   `button.html` e `icone` do `empty_state.html`) **não migram**. Já são fonte única
   (sem duplicação) e usam mecanismo diferente (include de fragmento cru). Mexer
   neles arrisca regressão em #71/#76 sem ganho de deduplicação.
5. **SVGs de uso único** (ex.: ícone do `base_auth.html`, ícones de status internos
   de `_modal_body.html`/`_modal_icon.html` variant info/warning que não se repetem
   fora desse componente) permanecem inline, conforme a issue permite.
6. **Spinner de `autocomplete.html` não migra.** Descoberto durante a implementação
   (não pelo grep inicial, que só comparava os 40 primeiros caracteres do path):
   o spinner de `autocomplete.html` usa `d="M4 12a8 8 0 018-8v8z"`, geometricamente
   diferente do path usado nas 3 ocorrências de `preview_importacao_scpi.html`
   (`d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"`). São duas variantes visuais
   distintas, não uma duplicata — trocá-las pela mesma entrada do catálogo mudaria
   a forma renderizada de uma delas, violando "zero mudança visual". `autocomplete.html`
   fica com o SVG inline (uso único da sua variante); `spinner` no catálogo cobre só
   as 3 ocorrências de `preview_importacao_scpi.html`.

## Arquivos tocados

**Novos:**
- `apps/core/templates/components/icons/voltar.svg`
- `apps/core/templates/components/icons/lixeira.svg`
- `apps/core/templates/components/icons/remover.svg`
- `apps/core/templates/components/icons/spinner.svg`
- `apps/core/templates/components/icons/adicionar.svg`
- `apps/core/templates/components/icons/enviar.svg`
- `apps/core/templates/components/icons/copiar.svg`
- `apps/core/tests/test_icons.py`

**Modificados:**
- `apps/core/templatetags/core_tags.py` — nova tag `icon`.
- `apps/core/templates/components/_modal_icon.html` — variant danger usa `{% icon "lixeira" %}`.
- `apps/estoque/templates/estoque/preview_importacao_scpi.html` — 3 spinners; os 2 com
  `x-show="enviando"`/`x-show="confirmando"` passam a envolver a tag num
  `<span x-show="..." class="inline-flex">` — a diretiva Alpine sai do `<svg>` para o
  `<span>` pai. `class="inline-flex"` é obrigatório: um `<span>` puro é `display:
  inline` e herda métricas de baseline/line-height que podem deslocar o ícone alguns
  px verticalmente dentro do flex `gap-2` do `<button>`; `inline-flex` garante que o
  wrapper tenha o mesmo comportamento de caixa que o `<svg>` tinha como filho direto.
- `apps/estoque/templates/estoque/nova_saida_excepcional.html` — voltar, remover, adicionar.
- `apps/requisicoes/templates/requisicoes/partials/_item_form_row.html` — remover.
- `apps/requisicoes/templates/requisicoes/rascunho_form.html` — voltar ×2, adicionar, enviar.
- `apps/requisicoes/templates/requisicoes/atender_retirada.html` — voltar.
- `apps/requisicoes/templates/requisicoes/detalhe.html` — voltar, lixeira, copiar, enviar.
- `apps/requisicoes/templates/requisicoes/copiar_confirmacao.html` — voltar, copiar.

Nenhum arquivo de `services.py`, `policies.py`, `selectors.py` ou `models.py` é tocado.

## Design da tag

```python
ICONES_CATALOGO = frozenset({
    'voltar', 'lixeira', 'remover', 'spinner', 'adicionar', 'enviar', 'copiar',
})


@register.simple_tag
def icon(name: str, size: int = 20, **kwargs: str) -> str:
    if name not in ICONES_CATALOGO:
        raise ImproperlyConfigured(
            f"Ícone \"{name}\" não está no catálogo (components/icons/). "
            f'Nomes válidos: {sorted(ICONES_CATALOGO)}.'
        )
    css_class = kwargs.get('class', '')
    return mark_safe(
        render_to_string(
            f'components/icons/{name}.svg',
            {'size': size, 'class': css_class},
        )
    )
```

- `class` chega via `**kwargs` porque `class` é palavra reservada em Python — não dá
  para declarar como parâmetro nomeado, mas o Django simple_tag aceita perfeitamente
  `{% icon "x" class="h-4 w-4" %}` porque a chamada é feita com `**kwargs` internamente.
- `name` é validado contra `ICONES_CATALOGO` (allowlist fechada) **antes** de montar o
  path do template — barra qualquer `name` fora do catálogo, incluindo tentativas com
  separador de caminho (`../`, `/`), sem depender de `TemplateDoesNotExist` do loader.
- Contrato de `size`/`class` por ícone é explícito (não "cada arquivo usa o que
  precisar" implicitamente) — ver tabela abaixo. Ícone que não suporta um parâmetro
  simplesmente não referencia `{{ size }}`/`{{ class }}` no seu `.svg`; isso é
  contrato documentado, não efeito colateral silencioso.

  | ícone | usa `size` | usa `class` |
  |---|---|---|
  | `voltar` | sim — `width`/`height`, default 20 (viewBox fixo em 24) | não — nenhuma das 6 ocorrências originais tinha `class` |
  | `lixeira` | não — viewBox fixo em 20 | sim |
  | `remover` | não — viewBox fixo em 20 | sim |
  | `spinner` | não — viewBox fixo em 24 | sim |
  | `adicionar` | não — viewBox fixo em 20 | sim |
  | `enviar` | não — viewBox fixo em 20 | sim |
  | `copiar` | não — viewBox fixo em 20 | sim |

- Para os 6 ícones que usam `class`, o `.svg` sempre renderiza `class="{{ class }}"`
  sem guarda condicional — todo call site real desses ícones já passa `class` (é
  assim que o markup original sempre foi). `voltar` nunca referencia `{{ class }}`
  no arquivo, então passar `class=` para ele é um no-op documentado, não um bug.

## Estratégia de teste

`apps/core/tests/test_icons.py` (sem DB, mesmo padrão de `test_components.py`):

- **Caminho feliz**: renderizar cada um dos 7 ícones e comparar contra o markup
  original capturado (path `d=` exato, `viewBox`, `aria-hidden="true"`).
- **Parâmetro `class`**: passar `class="h-4 w-4 foo"` e conferir que aparece
  verbatim na saída.
- **Parâmetro `size`** (ícone `voltar`, único que usa `width`/`height`): `size=24`
  muda os atributos `width`/`height` sem alterar o `viewBox` (que é fixo em 24,
  grid nativo do ícone).
- **Erro de nome fora do catálogo**: `{% icon "nao-existe" %}` e
  `{% icon "../../etc/passwd" %}` levantam `ImproperlyConfigured` com mensagem
  citando o nome — validado pela allowlist antes de tocar o template loader.
- **Contrato por ícone**: para os 6 ícones que usam `class`, confirmar que o valor
  aparece verbatim; para `voltar`, confirmar que passar `class=` não gera efeito
  (não aparece no HTML, já que o arquivo não referencia a variável) — cobre o caso
  de parâmetro suportado vs. não suportado citado pelo review.
- **Spinner**: saída contém os dois elementos internos (`circle` + `path`) e
  repassa `animate-spin motion-reduce:animate-none` via `class`.

Verificação nas telas tocadas (não há screenshot-diff automatizado no repo — ADR-0010
não prevê isso):
- Suite completa não deve quebrar (nenhum teste existente hoje faz assert em path
  SVG cru — confirmado por grep antes de escrever este plano).
- Checagem manual via browser preview em pelo menos: `requisicoes/detalhe`,
  `requisicoes/rascunho_form` (nova requisição), `estoque/preview_importacao_scpi`.

## Invariantes

`docs/matriz-invariantes.md` não tem entradas sobre frontend/ícones/templates — é
focado em regras de domínio (transições de requisição, estoque). Nenhuma linha da
matriz se aplica a esta mudança, que é puramente de apresentação e não toca
`services`/`policies`/`selectors`.

## Riscos

- **Regressão visual no spinner com `x-show`**: mitigada movendo a diretiva para um
  `<span x-show="..." class="inline-flex">` — `inline-flex` explícito evita que o
  `<span>` (default `display: inline`) introduza deslocamento de baseline/line-height
  em relação ao `<svg>` que antes era filho direto do flex `gap-2`. Ainda precisa ser
  conferida manualmente no browser preview nos 3 call sites do spinner antes de
  fechar a implementação — verificação pendente, não concluída neste plano.
- **Divergência de contagem do épico** (`plus ×3` vs 2 reais): documentada acima,
  não é um risco de execução, só uma nota de rastreabilidade.
