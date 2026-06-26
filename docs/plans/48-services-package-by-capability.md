# Plano: #48 — Promover services.py a pacote services/ por capability

## Escopo

**O que muda:** `apps/requisicoes/services.py` (~1403 linhas) é promovido a
`apps/requisicoes/services/` com submódulos por capability de domínio.

**O que NÃO muda:**
- Nenhuma lógica de domínio, validação ou efeito colateral
- Nenhum caller (views, tests, outros apps) — `from apps.requisicoes.services import X` continua funcionando via reexport em `__init__.py`
- Nenhuma interface pública (assinaturas, nomes, comportamento)

Referência: ADR-0004 (emenda 2026-06-26), issue #48.

---

## Capability map

| Submódulo | Símbolos |
|-----------|----------|
| `ciclo_vida.py` | `ItemInput`, `_notificar_pos_commit`, `_validar_itens`, `criar_requisicao`, `editar_rascunho`, `enviar_para_autorizacao`, `retornar_para_rascunho`, `recusar_requisicao`, `autorizar_requisicao`, `estornar_requisicao` |
| `cancelamento.py` | `_descartar_rascunho_impl`, `descartar_rascunho`, `cancelar_ou_descartar_requisicao`, `_cancelar_requisicao_impl`, `cancelar_requisicao` |
| `atendimento.py` | `ItemAtendimentoEntrada`, `separar_para_retirada`, `registrar_atendimento`, `registrar_devolucao` |
| `copia.py` | `copiar_requisicao` |
| `__init__.py` | reexporta toda a API pública listada abaixo |

**Por que `cancelar_ou_descartar_requisicao` fica em `cancelamento.py`:**
Ela coordena apenas dentro do domínio de cancelamento (dispatch para `_descartar_rascunho_impl` ou
`_cancelar_requisicao_impl`), sem depender de nenhuma outra capability. `composites.py` não é
criado neste refactor — arquivos nascem com conteúdo; será adicionado quando existir coordenação
genuinamente cross-capability.

**Por que `_validar_itens` fica em `ciclo_vida.py` e não em `atendimento.py`:**
`_validar_itens` é helper de `criar_requisicao` e `editar_rascunho`. Atendimento usa
`ItemAtendimentoEntrada` separado.

---

## API pública reexportada em `__init__.py`

```python
from apps.requisicoes.services.ciclo_vida import (
    ItemInput,
    criar_requisicao,
    editar_rascunho,
    enviar_para_autorizacao,
    retornar_para_rascunho,
    recusar_requisicao,
    autorizar_requisicao,
    estornar_requisicao,
)
from apps.requisicoes.services.cancelamento import (
    descartar_rascunho,
    cancelar_ou_descartar_requisicao,
    cancelar_requisicao,
)
from apps.requisicoes.services.atendimento import (
    ItemAtendimentoEntrada,
    separar_para_retirada,
    registrar_atendimento,
    registrar_devolucao,
)
from apps.requisicoes.services.copia import (
    copiar_requisicao,
)

__all__ = [
    "ItemInput",
    "criar_requisicao",
    "editar_rascunho",
    "enviar_para_autorizacao",
    "retornar_para_rascunho",
    "recusar_requisicao",
    "autorizar_requisicao",
    "estornar_requisicao",
    "descartar_rascunho",
    "cancelar_ou_descartar_requisicao",
    "cancelar_requisicao",
    "ItemAtendimentoEntrada",
    "separar_para_retirada",
    "registrar_atendimento",
    "registrar_devolucao",
    "copiar_requisicao",
]
```

---

## Arquivos tocados

| Operação | Arquivo |
|----------|---------|
| Delete | `apps/requisicoes/services.py` |
| Create | `apps/requisicoes/services/__init__.py` |
| Create | `apps/requisicoes/services/ciclo_vida.py` |
| Create | `apps/requisicoes/services/cancelamento.py` |
| Create | `apps/requisicoes/services/atendimento.py` |
| Create | `apps/requisicoes/services/copia.py` |

Nenhum caller alterado.

---

## Estratégia de testes

- **Happy path:** suite existente em `test_services.py` + `test_views.py` cobre todos os services públicos; deve passar sem alteração após refactor
- **Estado inválido:** já coberto pela suite existente
- **Permissão negada:** já coberto pela suite existente
- Nenhum novo teste necessário — movimento puro sem mudança de comportamento

---

## Invariantes relevantes

- Não há alteração de schema, transições de estado ou política de autorização
- `__init__.py` reexporta nomes idênticos — imports existentes não precisam mudar
- Imports cruzados entre submódulos proibidos: cada submódulo importa somente de camadas externas (`apps.*`, stdlib, Django)

---

## Riscos

| Risco | Mitigação |
|-------|-----------|
| Import circular entre submódulos | `cancelar_ou_descartar_requisicao` fica em `cancelamento.py` (sem cross-import) |
| Símbolo privado vazando API pública | `_notificar_pos_commit`, `_validar_itens`, `_descartar_rascunho_impl`, `_cancelar_requisicao_impl` **não** entram em `__init__.py` |
| `logger = logging.getLogger(__name__)` com `__name__` diferente | Cada submódulo declara seu próprio logger; nomes diferentes são aceitáveis |
| Mypy reclamando de imports | `__init__.py` usa imports explícitos (não `*`), type-safe |
