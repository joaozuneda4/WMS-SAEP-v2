# Plano — Guard de estoque único no admin (#102)

## Escopo

Impedir, pela interface do admin, a criação de um segundo `Estoque` enquanto
vigorar a suposição de estoque único dos services (ADR-0017), e registrar o
item de go-live com a query de detecção.

**Muda:**

- `apps/estoque/admin.py` — `EstoqueAdmin.has_add_permission` passa a negar
  adição quando já existe qualquer `Estoque`.
- `apps/estoque/tests/test_admin.py` — novo arquivo; cobre o guard com 0 e com
  1 estoque.
- `docs/checklist-go-live.md` — novo arquivo; item "um único `Estoque` ativo" e
  a query de detecção de saldo ambíguo.
- `docs/adr/0017-estoque-unico-servicos-fase-atual.md` — §1 já diz "conferida
  por checklist de go-live" sem apontar para nada; ganha o link para o arquivo
  novo. Só ponteiro; a decisão registrada não muda.

**Não muda:**

- `apps/estoque/models.py` — nenhuma `UniqueConstraint`/`CheckConstraint` de
  estoque único. ADR-0017 decide explicitamente **não** cimentar a limitação de
  fase no banco. Sem mudança de schema → sem migration nova.
- Services de estoque (`reservar_saldos_para_autorizacao`,
  `liberar_reservas_para_cancelamento`,
  `consumir_e_liberar_reservas_para_atendimento`,
  `registrar_devolucao_estoque`, `estornar_requisicao_estoque`) e
  `separar_para_retirada` — continuam localizando saldo só por `material_id` e
  tratando multiplicidade como erro. A causa-raiz (roteamento
  requisição→estoque) é feature futura, fora do escopo do issue.
- `confirmar_importacao_scpi_view` (`apps/requisicoes/views.py:1103`) —
  `Estoque.objects.filter(ativo=True).first()` permanece como está. O guard só
  fecha o caminho do admin: estoques criados por shell, `seed_dev` ou migration
  antes/depois dele continuam existindo, e a janela de concorrência descrita em
  "Riscos" também. Com mais de um estoque ativo, o `.first()` segue escolhendo
  arbitrariamente (por `ordering = ('nome',)`) — é a query de detecção do
  checklist de go-live que cobre esse caso, não o guard.
- Criação por shell / `seed_dev` / migration — permanece responsabilidade do
  operador, conforme a seção "Consequências" da ADR-0017.
- Mensagens de erro dos services (`saldo_ambiguo`, `separacao_bloqueada`) — o
  issue pede prevenção, não melhoria de diagnóstico.

## Arquivos alterados

| Arquivo | Ação |
|---|---|
| `apps/estoque/admin.py` | Adiciona `has_add_permission` a `EstoqueAdmin` (símbolo `EstoqueAdmin`, hoje só atributos de listagem) |
| `apps/estoque/tests/test_admin.py` | Novo — testes do guard |
| `docs/checklist-go-live.md` | Novo — checklist de go-live com o item de estoque único + query de detecção |
| `docs/adr/0017-estoque-unico-servicos-fase-atual.md` | Link de §1 para `docs/checklist-go-live.md` |

## Implementação

`EstoqueAdmin.has_add_permission` compõe com a permissão padrão do Django em
vez de substituí-la:

```python
def has_add_permission(self, request):
    """Barra a criação de um segundo Estoque (ADR-0017)."""
    return super().has_add_permission(request) and not Estoque.objects.exists()
```

Três decisões que o código embute:

1. **`exists()` sem filtro de `ativo`.** A ADR fala em "um único `Estoque`
   ativo", mas os services filtram `SaldoEstoque` por `material_id` sem olhar
   `estoque.ativo`. Um segundo estoque criado inativo, com saldo para material
   já usado, quebraria a autorização exatamente igual. O guard cobre o caso
   real, não o literal da frase.
2. **Compõe com `super()`.** Retornar só `not Estoque.objects.exists()` daria
   permissão de adicionar a um staff sem `estoque.add_estoque` no cenário de
   banco vazio. `and` preserva a checagem padrão de permissão.
3. **Vale também para superusuário.** É o cenário do issue ("Superusuário cria
   um 2º `Estoque` pelo admin"). Django resolve
   `ModelAdmin.has_add_permission` sem atalho para superuser, então o guard
   pega. Ver "Invariantes" abaixo para o conflito aparente com PER-05.

`has_add_permission` de `ModelAdmin` tem assinatura `(self, request)` — a
variante com `obj` é de `InlineModelAdmin`. Confirmado na documentação da versão
fixada em `pyproject.toml` (`django>=6.0,<6.1`; resolvida em 6.0.5 no
`uv.lock`).

## Estratégia de testes

Arquivo novo `apps/estoque/tests/test_admin.py`. ADR-0010 não lista
`test_admin.py` na organização de arquivos por app porque nenhuma regra vivia
no admin até agora; a camada admin não é service, policy, selector nem view, e
misturar em `test_views.py` (hoje dedicado a `saidas_excepcionais`) esconderia
a falha. **Desvio consciente e aditivo da ADR-0010** — nenhum teste existente
muda de lugar.

Fixtures reaproveitadas de `apps/estoque/tests/conftest.py`: `estoque_principal`
e `superuser`. Requests via `RequestFactory` com `request.user` atribuído — o
guard não lê sessão nem middleware.

| # | Caso | Setup | Esperado |
|---|---|---|---|
| 1 | Banco sem estoque, superusuário | nenhum `Estoque` | `has_add_permission(request) is True` |
| 2 | Já existe um estoque, superusuário | `estoque_principal` | `has_add_permission(request) is False` |
| 3 | Já existe um estoque inativo | `Estoque(ativo=False)` | `False` — cobre a decisão 1 (guard não filtra por `ativo`) |
| 4 | Banco sem estoque, staff sem permissão de add | staff sem `estoque.add_estoque` | `False` — cobre a decisão 2 (composição com `super()`) |

Casos 1 e 2 são o critério de aceite literal do issue ("0 e 1 estoques"); 3 e 4
protegem as duas decisões de implementação que um refactor ingênuo desfaria.

Não coberto (fora da camada): que o admin renderize ou esconda o botão "Add" —
comportamento do próprio Django, ADR-0010 proíbe testar default de framework.

## Invariantes

| ID | Relação com esta mudança |
|---|---|
| PER-05 | "Superusuário tem permissões totais, incluindo administração." O guard **restringe** o superusuário nesta ação específica. Não é regressão: é a decisão registrada na ADR-0017 §1, e o cenário do issue é justamente o superusuário. A restrição é de interface — o superusuário continua podendo criar por shell, com a responsabilidade que a ADR lhe atribui. Registrar explicitamente no PR. |
| EST-02, EST-03, EST-04, EST-05 | Dependem de `SaldoEstoque` único por material. O guard protege a pré-condição desses invariantes; nenhum deles muda de definição. |
| LED-02 | Reconciliação por `(estoque, material)` já é escrita por par — não é afetada. |

Nenhuma linha da matriz precisa ser reescrita. A matriz descreve invariantes de
domínio; estoque único é limitação de fase documentada em ADR, não invariante
permanente — por isso vive no checklist de go-live e não em
`docs/matriz-invariantes.md`.

## Riscos

| Risco | Avaliação |
|---|---|
| Bloquear a criação do **primeiro** estoque em ambiente novo | Não ocorre: guard só nega com `Estoque.objects.exists()` verdadeiro. Caso 1 do teste cobre. |
| Ambiente de dev/seed que recria estoque | `seed_dev` e migrations não passam por `ModelAdmin`; ADR-0009 e o fluxo `make setup` seguem funcionando. Nenhuma mudança de schema → nada a resetar. |
| Query extra por request no admin | Um `EXISTS` na tela de changelist/add de `Estoque`. Tela de admin de baixa frequência. Irrelevante. |
| Contrato OpenAPI | Projeto é server-rendered sem camada REST. Não se aplica. |
| Concorrência | Duas criações simultâneas pelo admin poderiam passar as duas checagens. Aceito: ADR-0017 declara a proteção como não-hermética ("cobre o caminho acidental via interface"); a alternativa hermética é a constraint de banco que a ADR recusa. |
| Operador precisa trocar o estoque legítimo | Guard não é one-shot: é reavaliado a cada request, então volta a liberar a adição se a contagem chegar a zero. Este plano **não** prescreve o caminho da troca: apagar um `Estoque` com `SaldoEstoque`/`MovimentacaoEstoque` associados é operação destrutiva com dependências de FK, e não há service que a suporte. Trocar estoque exige runbook próprio (pré-condições, backup, migração de saldos e ledger) — fora do escopo do issue. Renomear o estoque existente resolve o caso comum sem apagar nada. |
| Máquina de estados / transições | Não tocada. |
