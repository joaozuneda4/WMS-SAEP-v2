# ADR-0011 — Contrato de services, policies e exceções de domínio

## Status

Aceita

## Contexto

O projeto separa domínio de HTTP (views finas, ADR-0004), mas precisava de um contrato explícito para: como services são chamados, como policies declaram permissão, como erros são representados e como a máquina de estados é validada. Sem esse contrato, agentes e desenvolvedores produzem código inconsistente — views passando `request.user` direto, policies acopladas a Django, erros de transição representados como `ValidationError` de formulário.

## Decisão

### Assinatura de services públicos

Services públicos usam assinatura keyword-only e recebem IDs, não instâncias ORM:

```python
def autorizar_requisicao(
    *,
    ator_id: int,
    requisicao_id: int,
    ...,
) -> Requisicao:
    ...
```

O service é responsável por carregar o ator e as relações necessárias internamente (`select_related`, `prefetch_related`). A view passa `request.user.id`, nunca `request.user`.

**Por quê IDs e não instâncias?**
- Evita instâncias stale: o service recarrega do banco no momento da operação.
- Centraliza o carregamento com as relações corretas — a view não precisa saber quais `select_related` satisfazem a policy.
- Permite uso fora de HTTP (tasks, scripts, management commands) com a mesma interface.
- Keyword-only obrigatório porque services recebem múltiplos `int` — chamada posicional pode trocar `ator_id` e `requisicao_id` silenciosamente.

Policies recebem objetos carregados (não IDs) porque são chamadas internamente pelo service, que já carregou as entidades necessárias. Policies com objetos de tipos distintos podem usar argumentos posicionais.

### Valor de retorno

Services retornam a entidade principal alterada (`Requisicao`) sem garantia de relações carregadas:

```python
def autorizar_requisicao(*, ator_id, requisicao_id) -> Requisicao:
    ...
    return requisicao  # fresco, sem select_related garantido
```

Views usam o `pk` retornado para redirect ou chamam um selector para renderização. Services não retornam DTOs ricos nem são usados como selectors.

### Exceções de domínio

Todas em `apps/core/exceptions.py`. Services nunca importam exceções HTTP do Django.

```python
class ErroDominio(Exception):
    """Base para erros esperados de regra de negócio."""
    default_code = "erro_dominio"
    def __init__(self, message=None, *, code=None):
        self.message = message or self.__class__.__name__
        self.code = code or self.default_code
        super().__init__(self.message)

class PermissaoNegada(ErroDominio): ...   # ator não tem permissão
class EstadoInvalido(ErroDominio): ...    # transição de estado inválida
class DadosInvalidos(ErroDominio): ...   # dados corretos estruturalmente mas inválidos para o domínio
class ConflitoDominio(ErroDominio): ...  # conflito de estado, saldo, unicidade lógica ou concorrência
```

Views traduzem para HTTP explicitamente:
- `PermissaoNegada` → `django.core.exceptions.PermissionDenied` (403) ou redirect com mensagem
- `EstadoInvalido` / `DadosInvalidos` → redirect com `messages.error`
- `ConflitoDominio` → idem

`IntegrityError` não é o caminho normal para erro de domínio previsível. Se o service sabe qual regra será violada, lança a exceção de domínio adequada antes do `save()`. `IntegrityError` é última barreira para condições de corrida e conflitos impossíveis de evitar só com validação prévia — nesse caso, capturar e relançar como `ConflitoDominio`.

Forms Django podem continuar usando `django.core.exceptions.ValidationError` onde o framework espera (model `clean()`, form validation).

### Contrato de validação

Três camadas com responsabilidades distintas:

```
Form     → qualidade do input HTTP (tipo, obrigatoriedade, choices, queryset UX)
Service  → invariantes de domínio que devem ser verdadeiras no momento da operação
Banco    → constraints finais (CheckConstraint, UniqueConstraint)
```

O service valida **independente da origem da chamada**: `material.ativo`, `vínculo auxiliar ativo`, `saldo suficiente`, `escopo de FK`, `quantidade positiva`. Essas regras podem ser violadas entre `form.is_valid()` e a execução do service.

O service **não** faz parsing de input bruto (tipo, campo obrigatório, formato). Isso é responsabilidade do form.

Quando a mesma regra aparece no form e no service (ex: `quantidade > 0`), isso é aceitável: o form serve UX antecipada e o service garante a invariante de domínio.

### Contrato de policies

Duas funções por policy, PT-BR:

```python
# apps/<app>/policies.py

def pode_autorizar_requisicao(ator: User, requisicao: Requisicao) -> bool:
    """Retorna True se ator pode autorizar a requisição."""
    ...

def exigir_pode_autorizar_requisicao(ator: User, requisicao: Requisicao) -> None:
    """Lança PermissaoNegada se ator não pode autorizar."""
    if not pode_autorizar_requisicao(ator, requisicao):
        raise PermissaoNegada("Você não pode autorizar esta requisição.")
```

> **Substituído pela Emenda 2026-06-26.** A assinatura passou a
> `pode_x(papel: PapelEfetivo, recurso)`; o `ator: User` acima é histórico.
> Ver "Policies recebem `PapelEfetivo`".

Regras:
- `exigir_pode_*` sempre delega para `pode_*` — uma única fonte de verdade.
- Services chamam `exigir_pode_*` após carregar as entidades, antes de aplicar efeitos.
- Templates e views podem chamar `pode_*` para controle de renderização.
- `blocked_reason` não existe nesta fase — adicionar apenas quando uma tela específica precisar exibir motivo textual de ação indisponível.

Nomes em PT-BR seguem a convenção de domínio (AGENTS.md).

### Validação de transições

`apps/requisicoes/transitions.py` declara o grafo de estados com escopo estreito:

```python
@dataclass(frozen=True)
class TransicaoRequisicao:
    operacao: str
    estados_origem: tuple[str, ...]
    estado_destino: str
    evento_timeline: str

TRANSICOES: dict[str, TransicaoRequisicao] = { ... }

def verificar_transicao_valida(operacao: str, requisicao: Requisicao) -> TransicaoRequisicao:
    transicao = TRANSICOES[operacao]
    if requisicao.estado not in transicao.estados_origem:
        raise EstadoInvalido(
            f"Transição '{operacao}' inválida no estado '{requisicao.estado}'.",
            code="estado_origem_invalido",
        )
    return transicao
```

> **Substituído pela Emenda 2026-06-26.** O campo `operacao` passou a ser o enum
> `Operacao` (não `str`) e a tabela é keyed por `Operacao`. Ver "Transições
> keyed por operação".

Services chamam `verificar_transicao_valida` antes de aplicar qualquer efeito. A tabela não contém: policy, saldo, quantidade, lógica de parcial/total — isso fica nos services.

## Consequências

Views chamam services com `ator_id=request.user.id` — independente de qual service ou policy está por baixo. O código de view é uniforme e não vaza relações de domínio.

Services carregam o ator internamente → uma query a mais por transação. Custo aceito em troca de contrato limpo.

`apps/core/exceptions.py` é o único lugar de import de exceções de domínio em services. Views têm tradução explícita, facilitando auditoria de como cada erro vira HTTP.

A ausência de `blocked_reason` simplifica a implementação inicial. Quando uma tela precisar, a evolução natural é criar `PolicyDecision(allowed, reason, code)` e derivar `pode_*` dela.

## Trade-off

`ator_id` em vez de `ator: User` cria uma query extra por chamada de service. Essa é a escolha intencional: centralizar carregamento no domínio, evitar instâncias stale, e manter views ignorantes do grafo de relações necessário para cada operação. A performance é aceitável para o volume esperado do sistema.

Exceções de domínio próprias exigem tradução explícita em views, em vez de depender do middleware Django para `PermissionDenied`. Aceita-se esse custo em troca de domínio desacoplado de HTTP e testável sem request.

## Emenda — 2026-06-26 (revisão de arquitetura)

Três refinamentos ao contrato, derivados de uma sessão de deepening. Não revogam
o ADR; estreitam interfaces que estavam difusas no código.

### Policies recebem `PapelEfetivo`, nunca `User`

A derivação de papel (chefe/auxiliar de almoxarifado, escopo de setor,
elegibilidade de beneficiário) estava duplicada em quatro arquivos
(`requisicoes`/`estoque` × `policies`/`selectors`), com cláusulas `except`
divergentes. Passa a existir um único módulo `apps/accounts/papeis.py` com:

- `PapelEfetivo` — value object **frozen e sem ORM** (dado puro);
- `papel_efetivo(usuario) -> PapelEfetivo` — **único boundary de IO** (uma
  consulta de vínculos + `setor_chefiado`).

As policies passam a receber **exclusivamente** `PapelEfetivo` + o recurso
avaliado: `pode_x(papel: PapelEfetivo, recurso)`. Nenhuma policy executa IO nem
resolve identidade internamente. O chamador (view/service composto) resolve
`papel_efetivo` **uma vez** no início do caso de uso e reutiliza em todas as
checagens. `PapelEfetivo` é um **snapshot** (ver CONTEXT, "Papel efetivo"): não
se atualiza sozinho se vínculos mudarem no meio da transação. Isso substitui o
contrato anterior ("policies recebem objetos carregados") pela forma específica
`PapelEfetivo`.

### Transições keyed por operação (fonte única do grafo de estados)

A ilustração original deste ADR já mostrava `operacao → {estados_origem,
estado_destino, evento_timeline}`, mas `transitions.py` derivou para um mapa
`estado_origem → {destinos}`, deixando o conhecimento "operação → estado de
origem exigido" hardcoded em condicionais de view (shadow state machine de ~11
flags no detalhe da requisição). `transitions.py` volta a ser **keyed por
`Operacao`** (enum) com `estados_origem` (sempre conjunto), `estado_destino` e
`evento_timeline`. Consumidores únicos da mesma tabela:

- `verificar_transicao_valida(operacao, requisicao)` (services);
- `acoes_disponiveis(papel, requisicao) -> frozenset[Operacao]` — selector em
  `apps/requisicoes/selectors.py`, consumido por UI e services.

Separação estrita de níveis: a tabela responde "operação permitida **neste
estado**?"; a policy responde "**este papel** pode executá-la?". A tabela nunca
codifica autorização. Ordem de composição em `acoes_disponiveis`: primeiro o
estado (filtra Operações permitidas pela tabela de transições), depois o papel
(filtra pelas policies sobre o `PapelEfetivo`). As flags de apresentação viram
projeções (`Operacao.X in acoes`). Metadados de execução de uma operação (ex.:
`CancelamentoInfo` com
`requer_justificativa`/`libera_reserva`) viajam como **classificação de
domínio**, sem strings de apresentação.

### Mapeamento canônico exceção → HTTP

A tradução exceção de domínio → resposta HTTP estava replicada em ~50 blocos
`try/except` com drift (ex.: `PermissaoNegada` ora 403, ora mensagem; `JsonResponse`
vs redirect). Passa a existir um **tradutor puro**:

```python
@dataclass(frozen=True)
class ErroPresentation:
    status: int       # status HTTP quando o endpoint responde com código
    severity: str     # nível de message: error/warning/success/info
    default_message: str


def traduz_erro_dominio(exc: ErroDominio) -> ErroPresentation: ...
```

`ErroPresentation` é dataclass **imutável**, independente de
Django/HTMX/forms/templates (estes são superfície de framework, mantida em
inglês por AGENTS.md). A **view** materializa a resposta concreta (`messages` +
redirect / `JsonResponse` / `render` / `PermissionDenied`).

Mapeamento canônico (fonte única **por padrão**):

| Exceção | `severity` | `status` |
|---|---|---|
| `PermissaoNegada` | error | `403` |
| `DadosInvalidos` | error | `422` |
| `EstadoInvalido` | warning | `409` |
| `ConflitoDominio` | warning | `409` |

`severity` rege o fluxo padrão `message` + redirect (PRG, HTTP 302 — `status`
não se aplica aí). `status` é usado quando o endpoint responde com código
(`PermissionDenied`/403, endpoints `JsonResponse`). Divergências são permitidas
só por requisito de contrato do endpoint (JSON, re-render de form HTMX), como
**substituição explícita e documentada** — nunca acidente. Casos cuja resposta
depende de estado intermediário da UI (re-render de formulário) **não usam** o
tradutor.
