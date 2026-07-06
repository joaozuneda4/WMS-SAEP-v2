# Plano — #64: achados baixos da auditoria UI/UX (polimento de copy)

## Escopo

**B1 — Cópia duplicada entre card de gatilho e modal**

Nos blocos de ação de `apps/requisicoes/templates/requisicoes/detalhe.html`, o parágrafo
descritivo do card que abre o modal repete quase literalmente a `descricao` passada ao
`components/modal.html`. Blocos afetados:

| Bloco | Card (hoje) | Modal (hoje) |
|---|---|---|
| Autorizar (`confirmar-autorizar`) | "Reserva o saldo necessário para todos os itens sem alterar o saldo físico." | idêntico |
| Retornar (`confirmar-retornar`) | "Devolve a requisição ao criador para ajustes. Pode incluir observação opcional." | "A requisição volta a ser rascunho visível apenas ao criador." |
| Recusar (`confirmar-recusar`) | "Encerra a requisição sem reservar ou baixar estoque. Motivo obrigatório." | "A recusa encerra a requisição sem reservar ou baixar estoque." |
| Separar (`confirmar-separar`) | "A requisição passa a aparecer como pronta para o beneficiário retirar no almoxarifado." | idêntico |
| Estornar (`estornar-modal`) | "Reverte toda a entregue líquida atual ao saldo físico do estoque e encerra a requisição. A justificativa é obrigatória e fica registrada na timeline." | "O estorno reverte toda a entregue líquida ao saldo físico e encerra definitivamente a requisição. Esta operação é irreversível." |

Ajuste: reescrever o texto do **card** para orientar a ação (o que este bloco faz / quando
usar), e manter no **modal** o foco em confirmação/consequência (o que acontece ao confirmar,
irreversibilidade quando aplicável). Nenhuma mudança de rótulo de botão, heading `<h2>`/`<h3>`,
`id` de modal, `data-modal-trigger` ou URL — apenas o texto dos parágrafos descritivos.

Fora do escopo: bloco "Cancelar" (usa `cancelamento_copy` dinâmico, sem duplicação hoje) e
qualquer bloco não listado na tabela acima.

**B2 — Notificação sem `requisicao_id` quebra alinhamento da lista**

Em `apps/notificacoes/templates/notificacoes/lista.html:25-32`, a linha "Requisição {{ numero_publico_exibicao }}"
só renderiza `{% if notificacao.requisicao_id %}`. Quando `requisicao_id` é `None` (notificação
de sistema/exemplo, não é só seed), o `<li>` fica mais baixo que os demais, quebrando o
alinhamento vertical da lista.

Ajuste: manter o espaço reservado por essa linha mesmo sem `requisicao_id`, usando um `<span>`
vazio (mesmas classes de tipografia/altura da âncora atual) em vez de omitir o bloco inteiro.
Sem link, sem texto placeholder visível — apenas preserva a altura da linha.

## Arquivos tocados

- `apps/requisicoes/templates/requisicoes/detalhe.html` — 5 blocos de ação (parágrafos de card, linhas ~293-351, ~429-443, ~450)
- `apps/notificacoes/templates/notificacoes/lista.html` — item de lista (linhas ~24-32)

Nenhuma mudança em `views.py`, `models.py`, `selectors.py` ou `services.py` de nenhum dos dois apps.

## Estratégia de teste

- Nenhuma mudança de domínio/lógica — apenas copy e um `<span>` de preenchimento.
- Teste de regressão visual/estrutural via `pytest` existente:
  - `apps/requisicoes/tests/test_views.py` já cobre presença de labels de botão (`'Separar para retirada' in html`, etc.) — não dependem do texto descritivo alterado, seguem passando.
  - Adicionar em `apps/requisicoes/tests/test_views.py` uma asserção nova (não substituir as existentes) que verifique, no HTML retornado pela view de detalhe, que o parágrafo do card e a `descricao` do modal de pelo menos um bloco reescrito (ex.: `confirmar-retornar`) não são mais idênticos — cobre a regressão de duplicação de copy descrita em B1.
  - Adicionar um teste em `apps/notificacoes/tests/test_views.py` (ou `test_selectors.py`, o que já existir de fixture de notificação sem requisição) confirmando que o `<li>` de uma notificação com `requisicao_id=None` renderiza o `<span>` placeholder (sem quebrar) e que uma notificação com `requisicao_id` continua renderizando o link "Requisição {{ numero }}".
- Rodar suíte completa: `uv run pytest -q -ra --tb=short --strict-markers --disable-warnings -n logical` — sem regressão esperada.

## Invariantes

Nenhum invariante de `docs/design-acesso-rapido/matriz-invariantes.md` é tocado — mudança é
puramente de copy/apresentação, sem alterar transições de estado, cálculo de saldo, ou payload
de notificação.

## Riscos

- Baixo: mudança textual pura em modelos renderizados no servidor, sem JS/Alpine novo, sem
  migração, sem alteração de contrato OpenAPI (projeto não expõe API REST).
- Risco de teste frágil: se algum teste existente fizer assert em substring do parágrafo
  descritivo (não só do heading/botão), precisa ajuste — verificado acima, nenhum encontrado.
