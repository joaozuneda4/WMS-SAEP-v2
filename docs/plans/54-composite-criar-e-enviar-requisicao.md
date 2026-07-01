# Plano: #54 — Composto `criar_e_enviar_requisicao`; view larga transaction.atomic

## Escopo

**O que muda:**
- Novo service composto `criar_e_enviar_requisicao` em `apps/requisicoes/services/composites.py`, dono da fronteira transacional (`transaction.atomic`), orquestrando os atômicos existentes `criar_requisicao` + `enviar_para_autorizacao`.
- Reexport do novo composto em `apps/requisicoes/services/__init__.py`.
- A view `nova_requisicao` (`apps/requisicoes/views.py`) para de abrir `transaction.atomic` e de encadear os dois services manualmente; passa a apenas selecionar o caso de uso — dispatch trivial conforme `acao`: `criar_e_enviar_requisicao` quando `acao == 'enviar'`, `criar_requisicao` isolado em qualquer outro caso (preserva o fallback atual, onde `acao` malformado ou ausente cai em rascunho — `acao = request.POST.get('acao', 'rascunho')`).

**O que NÃO muda:**
- Nenhuma regra de domínio, policy ou transição de estado dentro de `criar_requisicao`/`enviar_para_autorizacao` — ambos permanecem intactos, já com seus próprios `@transaction.atomic`.
- Nenhuma interface pública dos atômicos existentes.
- Comportamento observável da view (mesmas mensagens, mesmos redirects, mesmos códigos de erro).

Referência: ADR-0004 (emenda 2026-06-26), issue #54. Depende de #48 (pacote `services/`), já fechada.

---

## Padrão estabelecido

`View → Composto → Atômicos → Domínio`.

- **Atômico**: uma transição de estado; dono de seu próprio `@transaction.atomic`; nunca chamado dentro de outro atômico sem que a fronteira externa já exista (aninhamento vira savepoint, não uma segunda transação real).
- **Composto**: mora em `composites.py`; orquestra 2+ atômicos; é quem decide a fronteira transacional de nível mais alto quando múltiplas transições precisam ser all-or-nothing.
- **View**: nunca abre `transaction.atomic` nem encadeia services manualmente; apenas seleciona qual atômico/composto chamar conforme a ação do usuário.

---

## Arquivos tocados

| Operação | Arquivo |
|----------|---------|
| Create | `apps/requisicoes/services/composites.py` |
| Edit | `apps/requisicoes/services/__init__.py` (reexport) |
| Edit | `apps/requisicoes/views.py` (`nova_requisicao`: remove `transaction.atomic` e encadeamento manual) |
| Create | `apps/requisicoes/tests/test_composites.py` |

Nenhum outro caller é afetado — `criar_requisicao` e `enviar_para_autorizacao` continuam exportados e usados isoladamente em outros pontos (ex. reenvio de rascunho já numerado, testes de setup).

---

## Assinatura do composto

```python
def criar_e_enviar_requisicao(
    *,
    ator_id: int,
    beneficiario_id: int,
    itens: list[ItemInput],
    observacao_geral: str = '',
) -> Requisicao:
```

Retorno paralelo a `criar_requisicao`: a própria `Requisicao` (já em `AGUARDANDO_AUTORIZACAO`, com `numero_publico` emitido). Levanta as mesmas exceções de domínio que os atômicos internos (`DadosInvalidos`, `PermissaoNegada`, `EstadoInvalido`) — nenhuma tradução ou encapsulamento adicional.

---

## Estratégia de testes

- **Caminho feliz (service, sem HTTP):** `criar_e_enviar_requisicao` cria rascunho + envia em uma chamada; resultado tem `numero_publico` emitido e `estado == AGUARDANDO_AUTORIZACAO`; timeline registra `CRIACAO` seguido de `ENVIO_AUTORIZACAO`.
- **All-or-nothing:** se `enviar_para_autorizacao` falhar internamente após `criar_requisicao` já ter sido aplicado (ex. `ator_id` sem permissão de envio sobre o próprio rascunho recém-criado, levantando `PermissaoNegada`), a exceção deve propagar e nenhum efeito deve persistir — nem `Requisicao`/`ItemRequisicao`, nem `SequenciaRequisicao` incrementada, nem `TimelineRequisicao` (nem o evento de `CRIACAO` sobrevive ao rollback).
- **Propagação de exceção de domínio:** erro de validação de item propaga `DadosInvalidos` sem encapsulamento.
- **Regressão da view:** suíte existente de `test_views.py` para `nova_requisicao` (rascunho e envio direto) deve passar sem alteração — comportamento observável idêntico.
- Sem teste de HTTP novo — a mudança na view é só dispatch; a suíte de views existente já cobre os dois fluxos (`acao=rascunho` e `acao=enviar`).

---

## Invariantes relevantes

- EST-06 (matriz de invariantes): operações críticas usam transação; o composto garante fronteira transacional única cobrindo criação + envio.
- Fronteira transacional única: a view não abre `transaction.atomic` nem sequencia services — apenas escolhe qual chamar.
- Atômicos não são alterados; aninhamento de `@transaction.atomic` sob o `with transaction.atomic()` do composto resolve-se via savepoint do Django, sem violar a regra de "um atômico = uma transição".

---

## Riscos

| Risco | Mitigação |
|-------|-----------|
| Import cruzado entre submódulos de capability | `composites.py` importa apenas de `ciclo_vida.py` (mesma regra do pacote); nenhum submódulo de capability importa de `composites.py` |
| Comportamento observável da view mudar (mensagens, redirect) | Dispatch mantém as duas branches de mensagem (`sucesso rascunho` vs `sucesso envio`) inalteradas, só troca a chamada de service |
| Reenvio de rascunho já numerado (fluxo separado, fora desta view) não usa o composto | Fora de escopo — issue restringe-se à view `nova_requisicao`; reenvio de rascunho continua chamando `enviar_para_autorizacao` isoladamente onde já ocorre hoje |
