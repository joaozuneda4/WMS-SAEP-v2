# ADR-0004 — Arquitetura em camadas dos apps de domínio

## Status

Aceita

## Contexto

Os apps de domínio (`accounts`, `estoque`, `requisicoes`) concentram regras sensíveis: máquina de estados, autorização contextual, mutação transacional de estoque. Sem uma divisão de responsabilidades explícita, regra de domínio vaza para views e models de forma inconsistente, e cada novo agente ou desenvolvedor inventa a própria organização.

ADR-0001 já posiciona policies no app dono do caso de uso. ADR-0002 e ADR-0003 pressupõem services transacionais. `docs/estado-transicoes-requisicao.md` exige transições declarativas aplicadas por uma função única.

## Decisão

Cada app de domínio adota um layout interno padrão:

- `models.py` — schema, constraints, choices e properties simples. Não orquestra casos de uso.
- `transitions.py` (em `requisicoes`) — tabela declarativa da máquina de estados.
- `services.py` — comandos de domínio. Único ponto de mutação de domínio. Abrem `transaction.atomic` quando aplicável, chamam policies, aplicam transições, registram timeline e disparam notificações apenas via `transaction.on_commit`.
- `policies.py` — autorização contextual. Chamadas tanto por views quanto por services.
- `selectors.py` — leituras não triviais, filas e escopos de visibilidade.
- `forms.py` — validação de input.
- `views.py` — finas; sem regra de domínio; orquestram input → policy → service/selector → render.
- `urls.py`, `admin.py`, `tests/`.

`services.py`, `policies.py` e `selectors.py` começam como arquivo único por app; são promovidos a pacote apenas quando o volume justificar.

Notificações nunca são pré-condição de uma transição de domínio e são disparadas só após o commit.

## Consequências

View nunca contém regra de domínio nem decisão de autorização própria.

Toda mutação de estado de domínio passa por um service.

A mesma policy é chamada por view e por service (PER-08); checagem de view não substitui policy.

Leitura com escopo de visibilidade vai para selector, não se espalha em views.

Models não importam services nem disparam casos de uso em `save()`.

Notificação que falhe não desfaz a transição.

A regra operacional detalhada para agentes fica em `docs/CONVENTIONS.md`.

## Trade-off

Mais arquivos e indireção por app do que um Django de "views gordas + models". Aceita-se em troca de fronteiras testáveis, autorização única e um codebase navegável por agentes de IA.

## Emenda — 2026-06-26 (revisão de arquitetura)

Três refinamentos ao layout, derivados de uma sessão de deepening, em pontos onde
casos de uso compostos vazavam para as views.

### Service atômico vs. service composto; dono único da transação

- **Service atômico** — executa **uma** operação de domínio (no sentido de
  **Operação** do glossário: transição origem→destino + evento de timeline; é o
  mesmo conceito de "operação" usado em ADR-0011 e em `transitions.py`).
- **Service composto** — orquestra **vários** services atômicos e é o **dono da
  `transaction.atomic`**. É **orquestrador sem lógica de domínio própria**: não
  duplica lógica, apenas coordena e ordena a execução, sem mutar estado
  diretamente.

A view **seleciona** qual caso de uso executar; nunca abre transação nem
sequencia operações de domínio. Caso concreto: `nova_requisicao` abria
`transaction.atomic` e encadeava `criar_requisicao` → `enviar_para_autorizacao`
na própria view. Passa a existir `criar_e_enviar_requisicao(...)` (composto,
dono da transação, retorno paralelo a `criar_requisicao`). Hierarquia:

```text
View → Service composto → Services atômicos → Domínio
```

A fronteira transacional é única — o composto abre, os atômicos não reabrem.
Generaliza para futuras composições (cancelar + liberar reserva, atender +
movimentar estoque).

### `services.py` promovido a pacote por capability de domínio

A promoção a pacote (já prevista no ADR) organiza por **capability de domínio**,
não por tipo técnico. Proibido `helpers.py`/`utils.py`/`commands.py`/`queries.py`;
permitido `ciclo_vida.py`, `cancelamento.py`, `atendimento.py`, `copia.py` e um
`composites.py` próprio para os services compostos. A API pública permanece
estável via reexport em `services/__init__.py` — reorganização interna sem
impacto em chamadores. Cada submódulo é uma capability relativamente
independente; coordenação entre capabilities mora nos compostos, evitando
imports cruzados entre submódulos.

A mutação de domínio continua concentrada nos services **atômicos** — a regra
de "único ponto de mutação" do `CONVENTIONS.md` permanece intacta. O service
composto não é um segundo ponto de mutação independente: é só a fronteira
transacional que coordena os atômicos.

### Forms/formsets entregam value objects tipados, não dicts

Quando a transformação depende **apenas** dos dados submetidos, ela é
responsabilidade do form/formset, que entrega **value objects tipados** (estilo
`linhas_validas()` → `LinhaAtendimento`), nunca dicts anônimos nem comandos. O
form **não** chama o service nem conhece seu comando. Transformações que exigem
consulta ou regra de negócio ficam fora do form. Isso tira das views o shaping
manual de payload de domínio.

Limite com as exceções de domínio: a validação de **qualidade de input**
continua no form (Django `ValidationError`, ADR-0011); **invariantes de
domínio** permanecem no service, que lança as exceções de
`apps.core.exceptions` (ex.: `DadosInvalidos`), traduzidas na view por
`traduz_erro_dominio` (ADR-0011). O VO entregue pelo form carrega input válido —
não encapsula erro de domínio em dict genérico.
