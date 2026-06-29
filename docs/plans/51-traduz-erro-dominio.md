# Plano — Issue #51: traduz_erro_dominio + ErroPresentation

## Escopo

**O que muda:**
- Novo arquivo `apps/core/presentation.py` com `ErroPresentation` (dataclass frozen) e `traduz_erro_dominio()`.
- Views de `requisicoes` e `estoque` migradas ao tradutor.
- 6 drifts confirmados como acidentais (HITL 2026-06-29) corrigidos.

**O que NÃO muda:**
- `apps/core/exceptions.py` — sem alterações nas classes de exceção.
- Endpoints JSON (`buscar_materiais`, `buscar_materiais_saida_excepcional_view`) — opt-out documentado (retornam `JsonResponse` com `status` direto; `traduz_erro_dominio` não é chamado).
- Re-render HTMX de formulários (`nova_saida_excepcional_view`, `preview_importacao_scpi_view`) — opt-out documentado (resposta depende de contexto de UI intermediário; não usa messages + redirect).
- Formulários e model `clean()` — continuam usando `ValidationError` de Django.

---

## Arquivos tocados

| Arquivo | Tipo | O que muda |
|---|---|---|
| `apps/core/presentation.py` | **NOVO** | `ErroPresentation`, `traduz_erro_dominio` |
| `apps/core/tests/test_presentation.py` | **NOVO** | Testes unitários do tradutor (sem request) |
| `apps/requisicoes/views.py` | EDITAR | 4 drifts + migração ao tradutor |
| `apps/estoque/views.py` | EDITAR | 1 drift + migração ao tradutor |

Mapeamento com Serena: `get_symbols_overview` confirmou funções-alvo em ambas as views.

---

## Interface do tradutor

```python
# apps/core/presentation.py
from __future__ import annotations
from dataclasses import dataclass
from apps.core.exceptions import (
    ConflitoDominio, DadosInvalidos, ErroDominio, EstadoInvalido, PermissaoNegada,
)


@dataclass(frozen=True)
class ErroPresentation:
    status: int       # HTTP status para endpoints com código (JSON / PermissionDenied)
    severity: str     # nível de message: error / warning / success / info
    default_message: str


_MAPEAMENTO: dict[type[ErroDominio], ErroPresentation] = {
    PermissaoNegada:  ErroPresentation(status=403, severity='error',   default_message='Você não tem permissão para esta operação.'),
    DadosInvalidos:   ErroPresentation(status=422, severity='error',   default_message='Dados inválidos para a operação.'),
    EstadoInvalido:   ErroPresentation(status=409, severity='warning', default_message='Transição de estado inválida.'),
    ConflitoDominio:  ErroPresentation(status=409, severity='warning', default_message='Conflito de domínio.'),
}


def traduz_erro_dominio(exc: ErroDominio) -> ErroPresentation:
    """Traduz exceção de domínio em ErroPresentation (puro, sem Django/HTTP).

    status: usado apenas em endpoints que respondem com código (JSON / PermissionDenied).
    severity: usado no fluxo message+redirect (PRG/302) — status não se aplica aí.
    Divergências (JSON, re-render HTMX) devem sobrescrever explicitamente, nunca por acidente.
    """
    return _MAPEAMENTO.get(type(exc), ErroPresentation(status=500, severity='error', default_message=str(exc)))
```

**Padrão canônico nas views (PRG/message+redirect):**
```python
except PermissaoNegada as exc:
    raise PermissionDenied(str(exc))
except ErroDominio as exc:
    pres = traduz_erro_dominio(exc)
    getattr(messages, pres.severity)(request, str(exc))
    return redirect(...)
```

`PermissaoNegada` recebe bloco próprio porque precisa levantar `PermissionDenied` do Django (403), não `messages`. `status` de `traduz_erro_dominio` não é usado no fluxo PRG.

---

## Drifts confirmados (HITL 2026-06-29 — todos acidentais)

| # | View | Arquivo | Antes | Depois |
|---|---|---|---|---|
| 1 | `nova_requisicao` — outer catch | `requisicoes/views.py:315` | `except PermissaoNegada`: `messages.error` + redirect | `raise PermissionDenied(str(exc))` |
| 2 | `editar_rascunho_view` — inner catch | `requisicoes/views.py:434` | `(PermissaoNegada, DadosInvalidos, EstadoInvalido)` → error | Separar: `PermissaoNegada` → raise, `EstadoInvalido` → warning, `DadosInvalidos` → error |
| 3 | `copiar_requisicao_view` | `requisicoes/views.py:1078` | `(PermissaoNegada, DadosInvalidos, EstadoInvalido)` → error | Separar: `PermissaoNegada` → raise, `EstadoInvalido` → warning |
| 4 | `registrar_devolucao_view` | `requisicoes/views.py:1106` | `(ConflitoDominio, DadosInvalidos, EstadoInvalido)` → warning | `DadosInvalidos` → error; Conflito/Estado → warning |
| 5 | `estornar_requisicao_view` | `requisicoes/views.py:1130` | mesmo padrão | mesmo fix |
| 6 | `estornar_saida_excepcional_view` | `estoque/views.py:386` | `(DadosInvalidos, ConflitoDominio)` → error | `ConflitoDominio` → warning; `DadosInvalidos` → error |

---

## Opt-outs documentados (não mudam)

| View | Motivo | Comportamento |
|---|---|---|
| `buscar_materiais` (requisicoes) | Endpoint JSON | `PermissaoNegada` → `JsonResponse({'error': ...}, status=403)` — usa `pres.status` diretamente sem `traduz_erro_dominio`; comentário documenta opt-out |
| `buscar_materiais_saida_excepcional_view` | Endpoint JSON | idem |
| `nova_saida_excepcional_view` | Re-render HTMX | `DadosInvalidos/ConflitoDominio` → `_render_erro({'erro_geral': ...})` — estado UI intermediário; comentário documenta opt-out |
| `preview_importacao_scpi_view` | Re-render form | `DadosInvalidos` → `render(... {'erro_arquivo': ...})` — idem |

Os opt-outs receberão comentário `# opt-out: <razão>` no bloco except, tornando a divergência explícita.

---

## Estratégia de testes

**`apps/core/tests/test_presentation.py` (sem request, sem Django DB):**

| Cenário | Tipo |
|---|---|
| `traduz_erro_dominio(PermissaoNegada())` → status=403, severity='error' | happy path |
| `traduz_erro_dominio(DadosInvalidos('x'))` → status=422, severity='error' | happy path |
| `traduz_erro_dominio(EstadoInvalido('x'))` → status=409, severity='warning' | happy path |
| `traduz_erro_dominio(ConflitoDominio('x'))` → status=409, severity='warning' | happy path |
| `ErroPresentation` é imutável (tentar setar atributo → `FrozenInstanceError`) | invariante |
| Subtipo desconhecido de `ErroDominio` → fallback severity='error' | edge case |

Testes de integração das views (fixtures existentes) verificam indiretamente que os drifts foram corrigidos.

**`apps/requisicoes/tests/` e `apps/estoque/tests/` — testes de contrato dos opt-outs:**

| View | Cenário | Tipo |
|---|---|---|
| `buscar_materiais` | `PermissaoNegada` → `JsonResponse` com `status=403` (não `messages`) | opt-out contrato |
| `buscar_materiais_saida_excepcional_view` | idem | opt-out contrato |
| `nova_saida_excepcional_view` | `DadosInvalidos` → `render` com `{'erro_geral': ...}` (não redirect) | opt-out contrato |
| `preview_importacao_scpi_view` | `DadosInvalidos` → `render` com `{'erro_arquivo': ...}` (não redirect) | opt-out contrato |

Esses testes travam o comportamento atual de `JsonResponse`/`render` inline, impedindo que refatoração futura troque silenciosamente por `messages` + redirect.

---

## Invariantes

Da `docs/matriz-invariantes.md`:
- Fluxo PRG (message+redirect) não usa status HTTP — `traduz_erro_dominio.status` é **ignorado** nesses fluxos.
- `PermissaoNegada` em views HTMX/PRG → `raise PermissionDenied`, nunca `messages.error`.
- Endpoints JSON canônicos (futuros) podem usar `traduz_erro_dominio(exc).status`; `severity` não se aplica nesses fluxos. Opt-outs existentes (`buscar_materiais`, `buscar_materiais_saida_excepcional_view`) mantêm status local em `JsonResponse(..., status=...)` diretamente — `traduz_erro_dominio` não é chamado nessas views.

---

## Riscos

| Risco | Mitigação |
|---|---|
| Subtipo futuro de `ErroDominio` sem entrada no mapa | Fallback genérico (severity='error', status=500); sem log no tradutor (puro). Detecção: o teste `test_presentation.py` inclui um subtipo-sentinela que deve cair no fallback — falha no teste se o mapa for expandido sem teste correspondente. Observabilidade em produção fica na camada de view (logging de exceção inesperada), fora do escopo deste módulo. |
| Opt-out não documentado → silencioso | Checklist de revisão: todo `except` que diverge do padrão canônico deve ter comentário `# opt-out: <razão>` |
| Migração parcial deixa drifts remanescentes | Grep final por `messages.warning.*DadosInvalidos\|messages.error.*EstadoInvalido\|messages.error.*Conflito` antes do PR delivery |
