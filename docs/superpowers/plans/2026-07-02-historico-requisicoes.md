# Histórico de Requisições — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar uma tela system-wide de histórico de requisições (`requisicoes:historico`), paginada, filtrável e ordenável, com 1 linha = 1 `Requisicao`, espelhando o padrão de `historico_movimentacoes_view` do app `estoque`.

**Architecture:** Nenhum model novo — `Requisicao` já tem os campos necessários. Camadas: `policies.py` (quem pode acessar) → `selectors.py` (RBAC de visibilidade + filtros) → `views.py` (FBV fina, contrato HTTP, paginação, HTMX) → templates (full page + partials). Segue ADR-0004/0011 (arquitetura em camadas, services/policies/selectors) e ADR-0010 (estratégia de testes por camada).

**Tech Stack:** Django (FBV), HTMX (filtros/ordenação/paginação sem reload), Tailwind CSS (classes utilitárias, sem CSS custom), pytest + pytest-django.

## Global Constraints

- Identificadores de domínio em PT-BR (funções, variáveis, templates); superfície de framework em inglês onde o Django exige.
- Sem model novo, sem migração manual criada nesta entrega — ambiente local é efêmero (`make setup` recria o schema a partir dos models).
- RBAC é fronteira de segurança nos **selectors**, nunca em view/template.
- Filtros nunca ampliam o universo definido pelo selector de visibilidade (sempre `AND` adicional).
- Sem ações em lote, sem exportação, sem filtro por `numero_publico` — fora de escopo (spec `docs/superpowers/specs/2026-07-02-historico-requisicoes-design.md`).
- Testes seguem ADR-0010: selectors com `values_list`/`pk`, policies em matriz pura (sem DB), views por contrato HTTP.
- Rodar suíte com: `uv run pytest -q -ra --tb=short --strict-markers --disable-warnings -n logical`.

---

### Task 1: Índices de performance em `Requisicao`

**Files:**
- Modify: `apps/requisicoes/models.py:88-91` (classe `Meta` de `Requisicao`)

**Interfaces:**
- Produces: nenhuma interface nova (índice não é comportamento observável em teste unitário); consumido implicitamente pelas queries dos Tasks 3-4.

- [ ] **Step 1: Adicionar índices ao `Meta` de `Requisicao`**

Em `apps/requisicoes/models.py`, na classe `Requisicao`, o `Meta` atual é:

```python
    class Meta:
        verbose_name = 'requisição'
        verbose_name_plural = 'requisições'
        ordering = ('-criado_em',)
```

Substitua por:

```python
    class Meta:
        verbose_name = 'requisição'
        verbose_name_plural = 'requisições'
        ordering = ('-criado_em',)
        indexes = [
            models.Index(
                fields=['estado', 'criado_em'],
                name='idx_requisicao_estado_data',
            ),
            models.Index(
                fields=['setor_beneficiario', 'criado_em'],
                name='idx_requisicao_setor_data',
            ),
        ]
```

Esses dois índices cobrem os filtros mais comuns da nova tela (`estado`, `setor_beneficiario`) combinados com a ordenação padrão (`criado_em`).

- [ ] **Step 2: Regenerar o schema local**

Ambiente é efêmero (AGENTS.md): apague migrations locais do app e recrie do zero.

Run: `make setup`
Expected: comando termina sem erro; `python manage.py showmigrations requisicoes` lista a migração inicial aplicada, incluindo os dois índices novos (confirmável com `python manage.py sqlmigrate requisicoes 0001` mostrando `CREATE INDEX idx_requisicao_estado_data` e `idx_requisicao_setor_data`).

- [ ] **Step 3: Commit**

```bash
git add apps/requisicoes/models.py
git commit -m "feat(requisicoes): indices para consulta de historico por estado/setor"
```

---

### Task 2: Policy `pode_consultar_historico_requisicoes`

**Files:**
- Modify: `apps/requisicoes/policies.py` (adicionar ao final do arquivo)
- Test: `apps/requisicoes/tests/test_policies.py` (adicionar ao final do arquivo)

**Interfaces:**
- Consumes: `PapelEfetivo` (dataclass já existente em `apps/accounts/papeis.py`, campos: `ativo`, `eh_superusuario`, `eh_almoxarifado`, `eh_chefe_de_almoxarifado`, `setores_em_escopo: tuple[int, ...]`, `setor_chefiado_ativo_id`, `pode_ser_beneficiario`, `ator_id`).
- Produces: `pode_consultar_historico_requisicoes(papel: PapelEfetivo) -> bool` e `exigir_pode_consultar_historico_requisicoes(papel: PapelEfetivo) -> None` (usados pelo Task 5).

- [ ] **Step 1: Escrever teste falho**

No topo de `apps/requisicoes/tests/test_policies.py` já existem imports de `pytest`, `PapelEfetivo`, `PermissaoNegada` e das funções de `apps.requisicoes.policies` — adicione aos imports existentes:

```python
from apps.requisicoes.policies import (
    exigir_pode_consultar_historico_requisicoes,
    pode_consultar_historico_requisicoes,
)
```

No final do arquivo, adicione:

```python
def _papel_historico(
    *,
    ativo: bool = True,
    eh_superusuario: bool = False,
    eh_almoxarifado: bool = False,
    eh_chefe_de_almoxarifado: bool = False,
    setores_em_escopo: tuple[int, ...] = (),
) -> PapelEfetivo:
    return PapelEfetivo(
        ativo=ativo,
        eh_superusuario=eh_superusuario,
        eh_almoxarifado=eh_almoxarifado,
        eh_chefe_de_almoxarifado=eh_chefe_de_almoxarifado,
        setores_em_escopo=setores_em_escopo,
        setor_chefiado_ativo_id=None,
        pode_ser_beneficiario=True,
        ator_id=1,
    )


HISTORICO_SUPERUSER = _papel_historico(eh_superusuario=True)
HISTORICO_CHEFE_ALMOX = _papel_historico(
    eh_almoxarifado=True, eh_chefe_de_almoxarifado=True
)
HISTORICO_AUX_ALMOX = _papel_historico(eh_almoxarifado=True)
HISTORICO_CHEFE_SETOR = _papel_historico(setores_em_escopo=(5,))
HISTORICO_SOLICITANTE = _papel_historico()
HISTORICO_INATIVO = _papel_historico(ativo=False)


class TestPodeConsultarHistoricoRequisicoes:
    def test_superuser_pode(self):
        assert pode_consultar_historico_requisicoes(HISTORICO_SUPERUSER) is True

    def test_chefe_almoxarifado_pode(self):
        assert pode_consultar_historico_requisicoes(HISTORICO_CHEFE_ALMOX) is True

    def test_aux_almoxarifado_pode(self):
        assert pode_consultar_historico_requisicoes(HISTORICO_AUX_ALMOX) is True

    def test_chefe_setor_nao_almox_pode(self):
        assert pode_consultar_historico_requisicoes(HISTORICO_CHEFE_SETOR) is True

    def test_solicitante_puro_nao_pode(self):
        assert pode_consultar_historico_requisicoes(HISTORICO_SOLICITANTE) is False

    def test_inativo_nao_pode(self):
        assert pode_consultar_historico_requisicoes(HISTORICO_INATIVO) is False


class TestExigirPodeConsultarHistoricoRequisicoes:
    def test_superuser_nao_lanca(self):
        exigir_pode_consultar_historico_requisicoes(HISTORICO_SUPERUSER)

    def test_solicitante_lanca(self):
        with pytest.raises(PermissaoNegada):
            exigir_pode_consultar_historico_requisicoes(HISTORICO_SOLICITANTE)
```

- [ ] **Step 2: Rodar teste e confirmar falha**

Run: `uv run pytest apps/requisicoes/tests/test_policies.py::TestPodeConsultarHistoricoRequisicoes -v`
Expected: FAIL com `ImportError: cannot import name 'pode_consultar_historico_requisicoes'`

- [ ] **Step 3: Implementar a policy**

No final de `apps/requisicoes/policies.py`, adicione:

```python
def pode_consultar_historico_requisicoes(papel: 'PapelEfetivo') -> bool:
    """Pode navegar o histórico system-wide de requisições.

    Espelha o universo de ``historico_requisicoes_visiveis_para``: superuser,
    almoxarifado (chefe/aux) ou chefe/aux de setor não-almox (setores_em_escopo
    não vazio). Solicitante puro e inativo: não — continuam usando
    ``requisicoes:minhas``.
    """
    if not papel.ativo:
        return False
    if papel.eh_superusuario:
        return True
    return papel.eh_almoxarifado or bool(papel.setores_em_escopo)


def exigir_pode_consultar_historico_requisicoes(papel: 'PapelEfetivo') -> None:
    if not pode_consultar_historico_requisicoes(papel):
        raise PermissaoNegada(
            'Você não tem permissão para consultar o histórico de requisições.',
            code='permissao_negada',
        )
```

Confirme que `PermissaoNegada` já está importado no topo do arquivo (é usado por outras funções `exigir_pode_*` existentes); se não estiver, adicione `from apps.core.exceptions import PermissaoNegada`.

- [ ] **Step 4: Rodar teste e confirmar sucesso**

Run: `uv run pytest apps/requisicoes/tests/test_policies.py::TestPodeConsultarHistoricoRequisicoes apps/requisicoes/tests/test_policies.py::TestExigirPodeConsultarHistoricoRequisicoes -v`
Expected: PASS (8 testes)

- [ ] **Step 5: Commit**

```bash
git add apps/requisicoes/policies.py apps/requisicoes/tests/test_policies.py
git commit -m "feat(requisicoes): policy pode_consultar_historico_requisicoes"
```

---

### Task 3: Selector de visibilidade `historico_requisicoes_visiveis_para`

**Files:**
- Modify: `apps/requisicoes/selectors.py` (adicionar ao final do arquivo)
- Test: `apps/requisicoes/tests/test_selectors.py` (adicionar ao final do arquivo)

**Interfaces:**
- Consumes: `User` (accounts), `papel_efetivo(ator)` (já importado em `selectors.py`).
- Produces: `historico_requisicoes_visiveis_para(ator_id: int) -> QuerySet[Requisicao]` (consumido pela view no Task 5 e por `filtrar_historico_requisicoes` no Task 4).

- [ ] **Step 1: Escrever testes falhos**

No final de `apps/requisicoes/tests/test_selectors.py`, adicione (o arquivo já importa `pytest`, `Requisicao`, `EstadoRequisicao` no topo):

```python
from apps.requisicoes.selectors import historico_requisicoes_visiveis_para


# ---------------------------------------------------------------------------
# historico_requisicoes_visiveis_para
# ---------------------------------------------------------------------------


@pytest.fixture
def req_historico_obras(db, solicitante, setor_obras):
    return Requisicao.objects.create(
        estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        numero_publico='REQ-2026-0010',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )


@pytest.fixture
def req_historico_ti(db, usuario_ti, setor_ti):
    return Requisicao.objects.create(
        estado=EstadoRequisicao.AUTORIZADA,
        numero_publico='REQ-2026-0011',
        criador=usuario_ti,
        beneficiario=usuario_ti,
        setor_beneficiario=setor_ti,
    )


@pytest.mark.django_db
def test_historico_superuser_ve_tudo(superuser, req_historico_obras, req_historico_ti):
    visiveis = historico_requisicoes_visiveis_para(superuser.pk)
    assert set(visiveis.values_list('pk', flat=True)) == {
        req_historico_obras.pk,
        req_historico_ti.pk,
    }


@pytest.mark.django_db
def test_historico_chefe_almox_ve_tudo(
    chefe_almoxarifado, req_historico_obras, req_historico_ti
):
    visiveis = historico_requisicoes_visiveis_para(chefe_almoxarifado.pk)
    assert set(visiveis.values_list('pk', flat=True)) == {
        req_historico_obras.pk,
        req_historico_ti.pk,
    }


@pytest.mark.django_db
def test_historico_aux_almox_ve_tudo(
    aux_almoxarifado, req_historico_obras, req_historico_ti
):
    visiveis = historico_requisicoes_visiveis_para(aux_almoxarifado.pk)
    assert set(visiveis.values_list('pk', flat=True)) == {
        req_historico_obras.pk,
        req_historico_ti.pk,
    }


@pytest.mark.django_db
def test_historico_chefe_setor_ve_so_proprio_setor(
    chefe_obras, req_historico_obras, req_historico_ti
):
    visiveis = historico_requisicoes_visiveis_para(chefe_obras.pk)
    pks = set(visiveis.values_list('pk', flat=True))
    assert req_historico_obras.pk in pks
    assert req_historico_ti.pk not in pks


@pytest.mark.django_db
def test_historico_solicitante_puro_vazio(solicitante, req_historico_obras):
    visiveis = historico_requisicoes_visiveis_para(solicitante.pk)
    assert visiveis.count() == 0


@pytest.mark.django_db
def test_historico_inativo_vazio(usuario_inativo, req_historico_obras):
    visiveis = historico_requisicoes_visiveis_para(usuario_inativo.pk)
    assert visiveis.count() == 0


@pytest.mark.django_db
def test_historico_ator_inexistente_vazio(req_historico_obras):
    visiveis = historico_requisicoes_visiveis_para(999999)
    assert visiveis.count() == 0
```

- [ ] **Step 2: Rodar testes e confirmar falha**

Run: `uv run pytest apps/requisicoes/tests/test_selectors.py -k historico -v`
Expected: FAIL com `ImportError: cannot import name 'historico_requisicoes_visiveis_para'`

- [ ] **Step 3: Implementar o selector**

No final de `apps/requisicoes/selectors.py`, adicione:

```python
def historico_requisicoes_visiveis_para(ator_id: int) -> QuerySet[Requisicao]:
    """Queryset system-wide de requisições visíveis ao ator (histórico).

    Mais restrito que ``requisicoes_visiveis_para`` (que inclui a visão
    "minhas requisições" de qualquer solicitante): aqui, só quem tem
    visibilidade de papel sobre requisições de outras pessoas enxerga algo.

    RBAC (fronteira de segurança — nunca na view/template):
    - superuser → tudo.
    - almoxarifado (chefe ou auxiliar) → tudo.
    - chefe/aux de setor não-almox → só requisições com ``setor_beneficiario``
      nos setores do ator.
    - qualquer outro papel (solicitante puro, sem chefia) ou usuário
      inativo/inexistente → vazio.
    """
    base_qs = Requisicao.objects.select_related(
        'criador', 'beneficiario', 'setor_beneficiario'
    ).order_by('-criado_em')

    try:
        ator = User.objects.get(pk=ator_id)
    except User.DoesNotExist:
        return base_qs.none()

    if not ator.is_active:
        return base_qs.none()

    if ator.is_superuser:
        return base_qs

    papel = papel_efetivo(ator)
    if papel.eh_almoxarifado:
        return base_qs

    setores = list(papel.setores_em_escopo)
    if setores:
        return base_qs.filter(setor_beneficiario_id__in=setores)

    return base_qs.none()
```

- [ ] **Step 4: Rodar testes e confirmar sucesso**

Run: `uv run pytest apps/requisicoes/tests/test_selectors.py -k historico -v`
Expected: PASS (7 testes)

- [ ] **Step 5: Commit**

```bash
git add apps/requisicoes/selectors.py apps/requisicoes/tests/test_selectors.py
git commit -m "feat(requisicoes): selector historico_requisicoes_visiveis_para"
```

---

### Task 4: Filtros e opções do histórico (`filtrar_historico_requisicoes`, `pode_filtrar_historico_por_setor`, `_setores_do_historico`)

**Files:**
- Modify: `apps/requisicoes/selectors.py` (adicionar ao final)
- Test: `apps/requisicoes/tests/test_selectors.py` (adicionar ao final)

**Interfaces:**
- Consumes: `historico_requisicoes_visiveis_para` (Task 3).
- Produces: `filtrar_historico_requisicoes(qs, *, texto, estados, data_ini, data_fim, setor) -> QuerySet[Requisicao]`, `pode_filtrar_historico_por_setor(ator_id: int) -> bool`, `_setores_do_historico(qs) -> QuerySet[Setor]` — todos consumidos pela view no Task 5.

- [ ] **Step 1: Escrever testes falhos**

No final de `apps/requisicoes/tests/test_selectors.py`, adicione (usa `date` do `datetime`; adicione `from datetime import date` ao topo do arquivo se ainda não existir):

```python
from apps.requisicoes.selectors import (
    filtrar_historico_requisicoes,
    pode_filtrar_historico_por_setor,
)


@pytest.mark.django_db
def test_filtrar_historico_por_texto_no_criador(
    superuser, req_historico_obras, req_historico_ti
):
    visiveis = historico_requisicoes_visiveis_para(superuser.pk)
    filtrado = filtrar_historico_requisicoes(
        visiveis,
        texto='solicitante',
        estados=[],
        data_ini=None,
        data_fim=None,
        setor=None,
    )
    assert set(filtrado.values_list('pk', flat=True)) == {req_historico_obras.pk}


@pytest.mark.django_db
def test_filtrar_historico_por_estado(
    superuser, req_historico_obras, req_historico_ti
):
    visiveis = historico_requisicoes_visiveis_para(superuser.pk)
    filtrado = filtrar_historico_requisicoes(
        visiveis,
        texto='',
        estados=[EstadoRequisicao.AUTORIZADA],
        data_ini=None,
        data_fim=None,
        setor=None,
    )
    assert set(filtrado.values_list('pk', flat=True)) == {req_historico_ti.pk}


@pytest.mark.django_db
def test_filtrar_historico_estado_invalido_e_no_op(
    superuser, req_historico_obras, req_historico_ti
):
    visiveis = historico_requisicoes_visiveis_para(superuser.pk)
    filtrado = filtrar_historico_requisicoes(
        visiveis,
        texto='',
        estados=['nao_existe'],
        data_ini=None,
        data_fim=None,
        setor=None,
    )
    assert filtrado.count() == 2


@pytest.mark.django_db
def test_filtrar_historico_por_periodo(superuser, req_historico_obras):
    hoje = req_historico_obras.criado_em.date()
    visiveis = historico_requisicoes_visiveis_para(superuser.pk)

    dentro = filtrar_historico_requisicoes(
        visiveis, texto='', estados=[], data_ini=hoje, data_fim=hoje, setor=None
    )
    assert req_historico_obras.pk in dentro.values_list('pk', flat=True)

    fora = filtrar_historico_requisicoes(
        visiveis,
        texto='',
        estados=[],
        data_ini=date(1999, 1, 1),
        data_fim=date(1999, 1, 2),
        setor=None,
    )
    assert fora.count() == 0


@pytest.mark.django_db
def test_filtrar_historico_por_setor_nao_vaza_outro_setor(
    chefe_almoxarifado, req_historico_obras, req_historico_ti, setor_ti
):
    # Mesmo forçando setor de terceiros, o filtro é AND sobre o qs recebido —
    # aqui o chamador (chefe_almoxarifado) já enxerga tudo, então o filtro de
    # setor apenas recorta; não amplia visibilidade de quem não tem escopo.
    visiveis = historico_requisicoes_visiveis_para(chefe_almoxarifado.pk)
    filtrado = filtrar_historico_requisicoes(
        visiveis,
        texto='',
        estados=[],
        data_ini=None,
        data_fim=None,
        setor=setor_ti.pk,
    )
    assert set(filtrado.values_list('pk', flat=True)) == {req_historico_ti.pk}


@pytest.mark.django_db
def test_pode_filtrar_historico_por_setor_almox_sim_chefe_setor_nao(
    chefe_almoxarifado, chefe_obras
):
    assert pode_filtrar_historico_por_setor(chefe_almoxarifado.pk) is True
    assert pode_filtrar_historico_por_setor(chefe_obras.pk) is False


@pytest.mark.django_db
def test_pode_filtrar_historico_por_setor_solicitante_nao(solicitante):
    assert pode_filtrar_historico_por_setor(solicitante.pk) is False
```

- [ ] **Step 2: Rodar testes e confirmar falha**

Run: `uv run pytest apps/requisicoes/tests/test_selectors.py -k "filtrar_historico or pode_filtrar_historico" -v`
Expected: FAIL com `ImportError: cannot import name 'filtrar_historico_requisicoes'`

- [ ] **Step 3: Implementar filtros e opções**

No final de `apps/requisicoes/selectors.py`, adicione:

```python
def filtrar_historico_requisicoes(
    qs: QuerySet[Requisicao],
    *,
    texto: str | None,
    estados: list[str],
    data_ini,
    data_fim,
    setor: int | None,
) -> QuerySet[Requisicao]:
    """Estreita o queryset de histórico já escopado por RBAC.

    Aplica filtros **sobre** o ``qs`` recebido (resultado de
    ``historico_requisicoes_visiveis_para``): nunca amplia o universo visível.

    - ``texto``: busca por ``nome`` OU ``matricula`` do criador OU do
      beneficiário (icontains); vazio/``None`` → no-op.
    - ``estados``: lista de ``EstadoRequisicao``; valores fora do enum são
      descartados; lista vazia → no-op.
    - ``data_ini`` / ``data_fim``: período **inclusivo** sobre o dia de
      ``criado_em``; ``None`` → no-op.
    - ``setor``: ``setor_beneficiario_id``; ``None`` → no-op.
    """
    if texto:
        qs = qs.filter(
            Q(criador__nome__icontains=texto)
            | Q(criador__matricula__icontains=texto)
            | Q(beneficiario__nome__icontains=texto)
            | Q(beneficiario__matricula__icontains=texto)
        )

    estados_validos = [e for e in estados if e in EstadoRequisicao.values]
    if estados_validos:
        qs = qs.filter(estado__in=estados_validos)

    if data_ini is not None:
        qs = qs.filter(criado_em__date__gte=data_ini)
    if data_fim is not None:
        qs = qs.filter(criado_em__date__lte=data_fim)

    if setor is not None:
        qs = qs.filter(setor_beneficiario_id=setor)

    return qs.distinct()


def pode_filtrar_historico_por_setor(ator_id: int) -> bool:
    """True se o ator pode filtrar o histórico por setor (só almoxarifado).

    Chefe/auxiliar de setor já está escopado ao(s) próprio(s) setor(es) pelo
    RBAC, então o filtro de setor não se aplica a ele. Superuser e
    almoxarifado veem todos os setores e podem recortar por setor.
    """
    try:
        ator = User.objects.get(pk=ator_id)
    except User.DoesNotExist:
        return False
    if not ator.is_active:
        return False
    return ator.is_superuser or _eh_almoxarifado(ator)


def _setores_do_historico(qs: QuerySet[Requisicao]):
    """Setores beneficiários distintos presentes no histórico visível
    (opções do filtro de setor, exibido apenas para almoxarifado)."""
    from apps.accounts.models import Setor

    ids = qs.values_list('setor_beneficiario_id', flat=True).distinct()
    return Setor.objects.filter(pk__in=ids).order_by('nome')
```

- [ ] **Step 4: Rodar testes e confirmar sucesso**

Run: `uv run pytest apps/requisicoes/tests/test_selectors.py -k "filtrar_historico or pode_filtrar_historico" -v`
Expected: PASS (7 testes)

- [ ] **Step 5: Commit**

```bash
git add apps/requisicoes/selectors.py apps/requisicoes/tests/test_selectors.py
git commit -m "feat(requisicoes): filtros de historico (texto/estado/periodo/setor)"
```

---

### Task 5: View + URL + template completo (contrato HTTP)

**Files:**
- Modify: `apps/requisicoes/views.py` (adicionar imports + view)
- Modify: `apps/requisicoes/urls.py`
- Create: `apps/requisicoes/templates/requisicoes/historico_requisicoes.html`
- Create: `apps/requisicoes/templates/requisicoes/partials/_tabela_historico_requisicoes.html`
- Create: `apps/requisicoes/templates/requisicoes/partials/_paginacao_historico.html`
- Test: `apps/requisicoes/tests/test_views.py` (adicionar ao final)

**Interfaces:**
- Consumes: `exigir_pode_consultar_historico_requisicoes`, `pode_consultar_historico_requisicoes` (Task 2); `historico_requisicoes_visiveis_para`, `filtrar_historico_requisicoes`, `pode_filtrar_historico_por_setor`, `_setores_do_historico` (Tasks 3-4); `EstadoRequisicao`, `Requisicao` (models); template `requisicoes/partials/_estado_badge.html` (já existente, espera `requisicao` no contexto).
- Produces: view `historico_requisicoes_view(request)`, URL name `requisicoes:historico`, templates prontos para o Task 6 adicionar o form de filtros.

- [ ] **Step 1: Escrever testes falhos (contrato de acesso e paginação)**

No final de `apps/requisicoes/tests/test_views.py`, adicione. O arquivo já importa `reverse`, `Decimal` etc. em vários pontos — use imports locais dentro dos testes que precisarem, seguindo o padrão já usado no arquivo:

```python
URL_HISTORICO_REQUISICOES = reverse('requisicoes:historico')


class TestHistoricoRequisicoesView:
    def test_chefe_almox_acessa(self, client, chefe_almoxarifado):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL_HISTORICO_REQUISICOES)
        assert response.status_code == 200

    def test_superuser_acessa(self, client, superuser):
        client.force_login(superuser)
        response = client.get(URL_HISTORICO_REQUISICOES)
        assert response.status_code == 200

    def test_chefe_setor_acessa(self, client, chefe_obras):
        client.force_login(chefe_obras)
        response = client.get(URL_HISTORICO_REQUISICOES)
        assert response.status_code == 200

    def test_solicitante_recebe_403(self, client, solicitante):
        client.force_login(solicitante)
        response = client.get(URL_HISTORICO_REQUISICOES)
        assert response.status_code == 403

    def test_anonimo_redirecionado_para_login(self, client):
        response = client.get(URL_HISTORICO_REQUISICOES)
        assert response.status_code == 302
        assert 'login' in response['Location']

    def test_contexto_tem_page_obj(self, client, superuser):
        client.force_login(superuser)
        response = client.get(URL_HISTORICO_REQUISICOES)
        assert 'page_obj' in response.context

    def test_view_alimenta_page_obj_com_selector_escopado(
        self, client, chefe_obras, req_historico_obras, req_historico_ti
    ):
        from apps.requisicoes.selectors import historico_requisicoes_visiveis_para

        client.force_login(chefe_obras)
        response = client.get(URL_HISTORICO_REQUISICOES)
        assert response.status_code == 200
        assert 'requisicoes/historico_requisicoes.html' in {
            t.name for t in response.templates
        }
        esperado = historico_requisicoes_visiveis_para(chefe_obras.pk).count()
        assert response.context['page_obj'].paginator.count == esperado

    def test_paginacao_server_side(self, client, superuser, setor_obras, solicitante):
        from apps.requisicoes.models import EstadoRequisicao, Requisicao

        for i in range(30):
            Requisicao.objects.create(
                estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
                numero_publico=f'REQ-2026-1{i:03d}',
                criador=solicitante,
                beneficiario=solicitante,
                setor_beneficiario=setor_obras,
            )
        client.force_login(superuser)
        page1 = client.get(URL_HISTORICO_REQUISICOES)
        assert len(page1.context['page_obj'].object_list) == 25
        assert page1.context['page_obj'].has_next() is True
        page2 = client.get(URL_HISTORICO_REQUISICOES, {'page': 2})
        assert page2.status_code == 200
        assert len(page2.context['page_obj'].object_list) >= 1

    def test_empty_state_quando_historico_vazio(self, client, chefe_almoxarifado):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL_HISTORICO_REQUISICOES)
        assert response.context['page_obj'].paginator.count == 0
        assert b'Nenhuma requisi' in response.content

    def test_requisicao_htmx_devolve_so_partial(self, client, superuser):
        client.force_login(superuser)
        response = client.get(URL_HISTORICO_REQUISICOES, HTTP_HX_REQUEST='true')
        assert response.status_code == 200
        nomes = {t.name for t in response.templates}
        assert 'requisicoes/partials/_tabela_historico_requisicoes.html' in nomes
        assert 'requisicoes/historico_requisicoes.html' not in nomes

    def test_requisicao_normal_devolve_template_completo(self, client, superuser):
        client.force_login(superuser)
        response = client.get(URL_HISTORICO_REQUISICOES)
        nomes = {t.name for t in response.templates}
        assert 'requisicoes/historico_requisicoes.html' in nomes

    def test_coluna_material_resume_item_unico(
        self, client, superuser, req_historico_obras, material_disponivel
    ):
        from apps.requisicoes.models import ItemRequisicao

        ItemRequisicao.objects.create(
            requisicao=req_historico_obras,
            material=material_disponivel,
            quantidade_solicitada=3,
        )
        client.force_login(superuser)
        response = client.get(URL_HISTORICO_REQUISICOES)
        assert material_disponivel.nome.encode() in response.content

    def test_coluna_material_resume_multiplos_itens(
        self,
        client,
        superuser,
        req_historico_obras,
        material_disponivel,
        material_disponivel_2,
    ):
        from apps.requisicoes.models import ItemRequisicao

        ItemRequisicao.objects.create(
            requisicao=req_historico_obras,
            material=material_disponivel,
            quantidade_solicitada=3,
        )
        ItemRequisicao.objects.create(
            requisicao=req_historico_obras,
            material=material_disponivel_2,
            quantidade_solicitada=1,
        )
        client.force_login(superuser)
        response = client.get(URL_HISTORICO_REQUISICOES)
        assert b'2 itens' in response.content
```

Os testes acima usam as fixtures `req_historico_obras`/`req_historico_ti`, definidas no Task 3 dentro de `test_selectors.py`. Para serem visíveis também em `test_views.py`, precisam morar em `conftest.py` (compartilhado entre arquivos de teste do app) — mova-as no próximo passo.

- [ ] **Step 1b: Mover fixtures compartilhadas para `conftest.py`**

Corte de `apps/requisicoes/tests/test_selectors.py` as fixtures `req_historico_obras` e `req_historico_ti` (adicionadas no Task 3) e cole em `apps/requisicoes/tests/conftest.py`, na seção de requisições (crie uma seção nova no final do arquivo):

```python
# ---------------------------------------------------------------------------
# Requisições para testes de histórico
# ---------------------------------------------------------------------------


@pytest.fixture
def req_historico_obras(db, solicitante, setor_obras):
    from apps.requisicoes.models import EstadoRequisicao, Requisicao

    return Requisicao.objects.create(
        estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        numero_publico='REQ-2026-0010',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )


@pytest.fixture
def req_historico_ti(db, usuario_ti, setor_ti):
    from apps.requisicoes.models import EstadoRequisicao, Requisicao

    return Requisicao.objects.create(
        estado=EstadoRequisicao.AUTORIZADA,
        numero_publico='REQ-2026-0011',
        criador=usuario_ti,
        beneficiario=usuario_ti,
        setor_beneficiario=setor_ti,
    )
```

`test_selectors.py` continua funcionando sem mudança (pytest resolve fixtures de `conftest.py` automaticamente); remova apenas as duas definições duplicadas de lá.

- [ ] **Step 2: Rodar testes e confirmar falha**

Run: `uv run pytest apps/requisicoes/tests/test_views.py::TestHistoricoRequisicoesView -v`
Expected: FAIL com `django.urls.exceptions.NoReverseMatch: Reverse for 'historico' not found`

- [ ] **Step 3: Adicionar imports e a view**

Em `apps/requisicoes/views.py`, adicione ao bloco de imports existente (perto de `from datetime import date` — adicione essa linha se não existir; o arquivo hoje não importa `date` nem `Paginator` nem `Count`):

```python
from datetime import date

from django.core.paginator import Paginator
from django.db.models import Count
```

Adicione aos imports de `apps.requisicoes.policies`:

```python
    exigir_pode_consultar_historico_requisicoes,
```

Adicione aos imports de `apps.requisicoes.selectors`:

```python
    filtrar_historico_requisicoes,
    historico_requisicoes_visiveis_para,
    pode_filtrar_historico_por_setor,
```

No final de `apps/requisicoes/views.py`, adicione:

```python
PAGINA_HISTORICO_REQUISICOES_TAMANHO = 25


def _parse_data_iso_historico(valor: str | None) -> date | None:
    """Converte 'YYYY-MM-DD' em date; entrada inválida/vazia → None (no-op)."""
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        return None


def _querystring_sem_page_historico(get_params) -> str:
    """Querystring atual sem o parâmetro `page`, para preservar filtros na
    paginação (links e swap HTMX)."""
    params = get_params.copy()
    params.pop('page', None)
    return params.urlencode()


def _setores_do_historico_para_filtro(visiveis):
    """Setores presentes no histórico visível (opções do filtro de setor)."""
    from apps.requisicoes.selectors import _setores_do_historico

    return _setores_do_historico(visiveis)


@login_required
@require_GET
def historico_requisicoes_view(request):
    """Histórico system-wide de requisições visível ao ator (RBAC no selector),
    filtrável e paginado. Espelha ``estoque.historico_movimentacoes_view``.

    Filtros vivem na querystring (recorte compartilhável). Em requisições HTMX
    devolve apenas o partial da tabela+paginação; caso contrário, a página
    completa. A view chama os selectors por ID (`request.user.pk`) e traduz a
    exceção de domínio em resposta HTTP, conforme ADR-0011/CONVENTIONS.md.
    """
    papel = papel_efetivo(request.user)
    try:
        exigir_pode_consultar_historico_requisicoes(papel)
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))

    texto = request.GET.get('texto', '').strip()
    estados_brutos = request.GET.getlist('estados')
    estados = [e for e in estados_brutos if e in EstadoRequisicao.values]
    data_ini = _parse_data_iso_historico(request.GET.get('data_ini'))
    data_fim = _parse_data_iso_historico(request.GET.get('data_fim'))
    ordem = 'asc' if request.GET.get('ordem') == 'asc' else 'desc'

    mostrar_filtro_setor = pode_filtrar_historico_por_setor(request.user.pk)
    setor = None
    if mostrar_filtro_setor:
        setor_bruto = request.GET.get('setor', '')
        if setor_bruto.isdigit():
            setor = int(setor_bruto)

    visiveis = historico_requisicoes_visiveis_para(request.user.pk)
    requisicoes = filtrar_historico_requisicoes(
        visiveis,
        texto=texto or None,
        estados=estados,
        data_ini=data_ini,
        data_fim=data_fim,
        setor=setor,
    )
    requisicoes = requisicoes.annotate(quantidade_itens=Count('itens')).prefetch_related(
        'itens__material'
    )
    requisicoes = requisicoes.order_by('criado_em' if ordem == 'asc' else '-criado_em')

    paginator = Paginator(requisicoes, PAGINA_HISTORICO_REQUISICOES_TAMANHO)
    page_obj = paginator.get_page(request.GET.get('page'))

    setores_disponiveis = []
    if mostrar_filtro_setor:
        setores_disponiveis = _setores_do_historico_para_filtro(visiveis)

    tem_filtro_ativo = bool(
        texto or estados or data_ini or data_fim or setor is not None
    )

    ordem_inversa = 'asc' if ordem == 'desc' else 'desc'
    params_ordenacao = request.GET.copy()
    params_ordenacao.pop('page', None)
    params_ordenacao['ordem'] = ordem_inversa
    url_ordenacao = '?' + params_ordenacao.urlencode()

    is_htmx = request.headers.get('HX-Request') == 'true'
    contexto = {
        'page_obj': page_obj,
        'is_htmx': is_htmx,
        'mostrar_filtro_setor': mostrar_filtro_setor,
        'setores_disponiveis': setores_disponiveis,
        'estados_opcoes': EstadoRequisicao.choices,
        'filtros': {
            'texto': texto,
            'estados': estados,
            'data_ini': request.GET.get('data_ini', ''),
            'data_fim': request.GET.get('data_fim', ''),
            'setor': setor,
        },
        'ordem': ordem,
        'aria_sort': 'ascending' if ordem == 'asc' else 'descending',
        'url_ordenacao': url_ordenacao,
        'tem_filtro_ativo': tem_filtro_ativo,
        'querystring_filtros': _querystring_sem_page_historico(request.GET),
    }

    if is_htmx:
        template = 'requisicoes/partials/_tabela_historico_requisicoes.html'
    else:
        template = 'requisicoes/historico_requisicoes.html'
    return render(request, template, contexto)
```

- [ ] **Step 4: Adicionar a URL**

Em `apps/requisicoes/urls.py`, adicione ao `urlpatterns` (antes de `path('itens/nova-linha/', ...)`, por exemplo):

```python
    path('historico/', views.historico_requisicoes_view, name='historico'),
```

- [ ] **Step 5: Criar template completo**

Create `apps/requisicoes/templates/requisicoes/historico_requisicoes.html`:

```django
{% extends "requisicoes/base.html" %}

{% block title %}Histórico de requisições — WMS-SAEP{% endblock %}

{% block topbar_leading %}
  <h1 class="app-bar__title">Histórico de requisições</h1>
{% endblock %}

{% block content %}
<div class="max-w-screen-xl mx-auto">

  <p class="mb-6 max-w-3xl text-sm text-slate-600">
    Requisições visíveis ao seu papel, mais recentes primeiro.
  </p>

  {# Wrapper estável do swap HTMX: alvo persistente (id + aria-live único). O partial entrega só o conteúdo interno. #}
  <div id="resultados-historico-requisicoes" aria-live="polite" aria-atomic="true">
    {% include 'requisicoes/partials/_tabela_historico_requisicoes.html' %}
  </div>

</div>
{% endblock %}
```

Create `apps/requisicoes/templates/requisicoes/partials/_tabela_historico_requisicoes.html`:

```django
{% comment %}
Conteúdo do bloco tabela+paginação do histórico de requisições — resposta do
swap HTMX. O wrapper #resultados-historico-requisicoes (id + aria-live) vive
na página completa e é o alvo persistente do swap; este partial entrega
apenas o conteúdo interno para evitar id duplicado / aria-live aninhado.
Contexto: page_obj, tem_filtro_ativo, ordem, aria_sort, url_ordenacao,
querystring_filtros.
{% endcomment %}
{% if page_obj.object_list %}

  {# Mobile: cards empilhados #}
  <div class="space-y-3 sm:hidden">
    {% for req in page_obj.object_list %}
      <article class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <h2 class="text-sm font-semibold text-slate-900">
              {% if req.numero_publico %}{{ req.numero_publico }}{% else %}Rascunho #{{ req.pk }}{% endif %}
            </h2>
            <p class="mt-1 text-xs text-slate-500">{{ req.criado_em|date:"d/m/Y H:i" }}</p>
          </div>
          <div class="shrink-0">
            {% include "requisicoes/partials/_estado_badge.html" with requisicao=req %}
          </div>
        </div>

        <dl class="mt-3 grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt class="text-xs font-medium uppercase tracking-wide text-slate-500">Solicitante</dt>
            <dd class="mt-0.5 text-slate-800">{{ req.criador.nome }}</dd>
          </div>
          <div>
            <dt class="text-xs font-medium uppercase tracking-wide text-slate-500">Beneficiário</dt>
            <dd class="mt-0.5 text-slate-800">{{ req.beneficiario.nome }}</dd>
          </div>
          <div>
            <dt class="text-xs font-medium uppercase tracking-wide text-slate-500">Setor</dt>
            <dd class="mt-0.5 text-slate-800">{{ req.setor_beneficiario.nome }}</dd>
          </div>
          <div>
            <dt class="text-xs font-medium uppercase tracking-wide text-slate-500">Material</dt>
            <dd class="mt-0.5 text-slate-800">
              {% if req.quantidade_itens == 1 %}{{ req.itens.all.0.material.nome }}{% else %}{{ req.quantidade_itens }} itens{% endif %}
            </dd>
          </div>
        </dl>

        <a
          href="{% url 'requisicoes:detalhe' pk=req.pk %}?next={{ request.path|urlencode }}"
          class="mt-4 inline-flex items-center rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1"
        >
          Ver detalhes
        </a>
      </article>
    {% endfor %}
  </div>

  {# Desktop: tabela densa #}
  <div class="hidden overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm sm:block">
    <table class="min-w-full divide-y divide-slate-200">
      <caption class="sr-only">
        Histórico de requisições, ordenado por data/hora em ordem
        {% if ordem == 'asc' %}crescente (mais antiga primeiro){% else %}decrescente (mais recente primeiro){% endif %}.
      </caption>
      <thead class="bg-slate-50">
        <tr>
          <th scope="col" aria-sort="{{ aria_sort }}" class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <a
              href="{{ url_ordenacao }}"
              hx-get="{{ url_ordenacao }}"
              hx-target="#resultados-historico-requisicoes"
              hx-push-url="true"
              class="-my-1 inline-flex items-center gap-1 rounded py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              aria-label="Ordenar por data/hora, {% if ordem == 'asc' %}atualmente crescente{% else %}atualmente decrescente{% endif %}"
            >
              Data/hora
              <span aria-hidden="true">{% if ordem == 'asc' %}↑{% else %}↓{% endif %}</span>
            </a>
          </th>
          <th scope="col" class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Número</th>
          <th scope="col" class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Solicitante</th>
          <th scope="col" class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Beneficiário</th>
          <th scope="col" class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Setor</th>
          <th scope="col" class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Material</th>
          <th scope="col" class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">Status</th>
          <th scope="col" class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">
            <span class="sr-only">Ações</span>
          </th>
        </tr>
      </thead>
      <tbody class="divide-y divide-slate-100 bg-white">
        {% for req in page_obj.object_list %}
          <tr class="hover:bg-slate-50">
            <td class="whitespace-nowrap px-4 py-3 text-sm text-slate-600">{{ req.criado_em|date:"d/m/Y H:i" }}</td>
            <td class="whitespace-nowrap px-4 py-3 text-sm font-medium text-slate-900">
              {% if req.numero_publico %}{{ req.numero_publico }}{% else %}<span class="text-slate-500">Rascunho #{{ req.pk }}</span>{% endif %}
            </td>
            <td class="whitespace-nowrap px-4 py-3 text-sm text-slate-700">{{ req.criador.nome }}</td>
            <td class="whitespace-nowrap px-4 py-3 text-sm text-slate-700">{{ req.beneficiario.nome }}</td>
            <td class="whitespace-nowrap px-4 py-3 text-sm text-slate-700">{{ req.setor_beneficiario.nome }}</td>
            <td class="max-w-xs truncate px-4 py-3 text-sm text-slate-700">
              {% if req.quantidade_itens == 1 %}{{ req.itens.all.0.material.nome }}{% else %}{{ req.quantidade_itens }} itens{% endif %}
            </td>
            <td class="whitespace-nowrap px-4 py-3 text-sm">
              {% include "requisicoes/partials/_estado_badge.html" with requisicao=req %}
            </td>
            <td class="whitespace-nowrap px-4 py-3 text-right text-sm">
              <a
                href="{% url 'requisicoes:detalhe' pk=req.pk %}?next={{ request.path|urlencode }}"
                class="inline-flex items-center rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1"
              >
                Ver
              </a>
            </td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  {% include 'requisicoes/partials/_paginacao_historico.html' with page_obj=page_obj querystring_filtros=querystring_filtros %}

{% else %}

  {# Empty state contextual: filtro sem resultado vs histórico visível vazio #}
  <div class="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
    <svg class="mx-auto mb-4 h-10 w-10 text-slate-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M13 3a9 9 0 1 0 9 9h-2a7 7 0 1 1-7-7v4l5-5-5-5v4z"/>
    </svg>
    {% if tem_filtro_ativo %}
      <h2 class="text-base font-medium text-slate-700">Nenhum resultado para este filtro</h2>
      <p class="mt-1 text-sm text-slate-500">Ajuste ou limpe os filtros para ver mais requisições.</p>
    {% else %}
      <h2 class="text-base font-medium text-slate-700">Nenhuma requisição encontrada</h2>
      <p class="mt-1 text-sm text-slate-500">Ainda não há requisições visíveis para o seu papel.</p>
    {% endif %}
  </div>

{% endif %}
```

Create `apps/requisicoes/templates/requisicoes/partials/_paginacao_historico.html`:

```django
{% comment %}
Paginação server-side reutilizável do histórico de requisições. Recebe
`page_obj` (Paginator page) e, opcionalmente, `querystring_filtros`
(querystring atual sem `page`) para preservar os filtros ativos ao navegar.
Alvos de toque min-h-11, focáveis.
{% endcomment %}
{% if page_obj.paginator.num_pages > 1 %}
  <nav
    class="mt-6 flex items-center justify-between gap-3"
    aria-label="Paginação do histórico de requisições"
  >
    <p class="text-sm text-slate-600">
      Página <span class="font-medium tabular-nums">{{ page_obj.number }}</span>
      de <span class="font-medium tabular-nums">{{ page_obj.paginator.num_pages }}</span>
      <span class="text-slate-400">·</span>
      <span class="tabular-nums">{{ page_obj.paginator.count }}</span> requisições
    </p>

    <div class="flex items-center gap-2">
      {% if page_obj.has_previous %}
        <a
          href="?{% if querystring_filtros %}{{ querystring_filtros }}&{% endif %}page={{ page_obj.previous_page_number }}"
          class="inline-flex min-h-11 items-center rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1"
        >
          Anterior
        </a>
      {% else %}
        <span
          class="inline-flex min-h-11 cursor-not-allowed items-center rounded-md border border-slate-100 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-300"
          aria-disabled="true"
        >
          Anterior
        </span>
      {% endif %}

      {% if page_obj.has_next %}
        <a
          href="?{% if querystring_filtros %}{{ querystring_filtros }}&{% endif %}page={{ page_obj.next_page_number }}"
          class="inline-flex min-h-11 items-center rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1"
        >
          Próxima
        </a>
      {% else %}
        <span
          class="inline-flex min-h-11 cursor-not-allowed items-center rounded-md border border-slate-100 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-300"
          aria-disabled="true"
        >
          Próxima
        </span>
      {% endif %}
    </div>
  </nav>
{% endif %}
```

- [ ] **Step 6: Rodar testes e confirmar sucesso**

Run: `uv run pytest apps/requisicoes/tests/test_views.py::TestHistoricoRequisicoesView -v`
Expected: PASS (13 testes)

Se `test_coluna_material_resume_item_unico`/`_multiplos_itens` falharem por causa de `Material` sem `nome` no template (checar se `Material` tem campo `nome` — já confirmado em `material_disponivel` fixture), revise apenas o template, não o selector.

- [ ] **Step 7: Rodar suíte completa do app para checar regressão**

Run: `uv run pytest apps/requisicoes -q -ra --tb=short --strict-markers --disable-warnings -n logical`
Expected: PASS, 0 failures

- [ ] **Step 8: Commit**

```bash
git add apps/requisicoes/views.py apps/requisicoes/urls.py apps/requisicoes/templates/requisicoes/historico_requisicoes.html apps/requisicoes/templates/requisicoes/partials/_tabela_historico_requisicoes.html apps/requisicoes/templates/requisicoes/partials/_paginacao_historico.html apps/requisicoes/tests/test_views.py apps/requisicoes/tests/test_selectors.py apps/requisicoes/tests/conftest.py
git commit -m "feat(requisicoes): view/url/template do historico de requisicoes"
```

---

### Task 6: Barra de filtros (texto, estado, período, setor) + testes de filtros/ordenação

**Files:**
- Modify: `apps/requisicoes/templates/requisicoes/historico_requisicoes.html`
- Test: `apps/requisicoes/tests/test_views.py` (adicionar ao final)

**Interfaces:**
- Consumes: contexto já produzido pela view no Task 5 (`filtros`, `estados_opcoes`, `mostrar_filtro_setor`, `setores_disponiveis`, `tem_filtro_ativo`, `ordem`).
- Produces: nenhuma interface nova — só UI sobre contrato já existente.

- [ ] **Step 1: Escrever testes falhos**

No final de `apps/requisicoes/tests/test_views.py`, adicione:

```python
class TestHistoricoRequisicoesFiltros:
    def test_filtro_texto_reduz_resultado(
        self, client, superuser, req_historico_obras, req_historico_ti
    ):
        client.force_login(superuser)
        com = client.get(URL_HISTORICO_REQUISICOES, {'texto': 'Solicitante'})
        sem = client.get(URL_HISTORICO_REQUISICOES, {'texto': 'inexistente'})
        assert com.context['page_obj'].paginator.count == 1
        assert sem.context['page_obj'].paginator.count == 0

    def test_filtro_estado_reduz_resultado(
        self, client, superuser, req_historico_obras, req_historico_ti
    ):
        client.force_login(superuser)
        response = client.get(
            URL_HISTORICO_REQUISICOES, {'estados': ['autorizada']}
        )
        pks = {r.pk for r in response.context['page_obj'].object_list}
        assert pks == {req_historico_ti.pk}

    def test_ordenacao_asc_inverte_cronologia(
        self, client, superuser, setor_obras, solicitante
    ):
        from apps.requisicoes.models import EstadoRequisicao, Requisicao

        for i in range(2):
            Requisicao.objects.create(
                estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
                numero_publico=f'REQ-2026-2{i:03d}',
                criador=solicitante,
                beneficiario=solicitante,
                setor_beneficiario=setor_obras,
            )
        client.force_login(superuser)
        desc = client.get(URL_HISTORICO_REQUISICOES).context['page_obj'].object_list
        asc = (
            client.get(URL_HISTORICO_REQUISICOES, {'ordem': 'asc'})
            .context['page_obj']
            .object_list
        )
        assert [r.pk for r in asc] == [r.pk for r in reversed(list(desc))]

    def test_filtro_setor_visivel_so_para_almox(
        self, client, chefe_almoxarifado, chefe_obras
    ):
        client.force_login(chefe_almoxarifado)
        assert (
            client.get(URL_HISTORICO_REQUISICOES).context['mostrar_filtro_setor']
            is True
        )
        client.force_login(chefe_obras)
        assert (
            client.get(URL_HISTORICO_REQUISICOES).context['mostrar_filtro_setor']
            is False
        )

    def test_chefe_setor_nao_filtra_por_setor_via_querystring(
        self, client, chefe_obras, req_historico_obras, req_historico_ti, setor_ti
    ):
        # Mesmo forçando ?setor=<outro> na URL, chefe de setor não vaza dado:
        # ele nunca vê req_historico_ti (fora do próprio setor) porque o
        # selector de visibilidade já o exclui do universo, e o filtro de
        # setor só é lido da querystring quando mostrar_filtro_setor é True.
        client.force_login(chefe_obras)
        response = client.get(URL_HISTORICO_REQUISICOES, {'setor': setor_ti.pk})
        assert response.status_code == 200
        pks = {r.pk for r in response.context['page_obj'].object_list}
        assert req_historico_ti.pk not in pks

    def test_querystring_invalida_nao_quebra(self, client, superuser):
        client.force_login(superuser)
        response = client.get(
            URL_HISTORICO_REQUISICOES,
            {
                'data_ini': 'abc',
                'data_fim': '2026-13-99',
                'setor': 'xyz',
                'ordem': 'lixo',
                'estados': 'nao_existe',
                'page': 'foo',
            },
        )
        assert response.status_code == 200

    def test_flag_tem_filtro_ativo(self, client, superuser):
        com = client.get(URL_HISTORICO_REQUISICOES, {'texto': 'x'})
        client.force_login(superuser)
        com = client.get(URL_HISTORICO_REQUISICOES, {'texto': 'x'})
        sem = client.get(URL_HISTORICO_REQUISICOES)
        assert com.context['tem_filtro_ativo'] is True
        assert sem.context['tem_filtro_ativo'] is False

    def test_empty_state_contextual_distingue_filtro_de_historico_vazio(
        self, client, superuser, req_historico_obras
    ):
        client.force_login(superuser)
        filtrado = client.get(
            URL_HISTORICO_REQUISICOES, {'texto': 'inexistente'}
        ).content
        assert 'Nenhum resultado para este filtro'.encode() in filtrado
        assert 'Nenhuma requisição encontrada'.encode() not in filtrado
```

- [ ] **Step 2: Rodar testes e confirmar quais falham**

Run: `uv run pytest apps/requisicoes/tests/test_views.py::TestHistoricoRequisicoesFiltros -v`
Expected: a maioria já PASSA (a view do Task 5 já implementa toda a lógica de filtro/ordenação/setor); só a UI de filtros está ausente — isso não quebra nenhum teste acima porque todos leem `response.context`, não HTML do form. Se todos passarem, siga para o Step 3 mesmo assim (a barra de filtros é exigência funcional da spec, não só de teste).

- [ ] **Step 3: Adicionar a barra de filtros ao template completo**

Em `apps/requisicoes/templates/requisicoes/historico_requisicoes.html`, substitua o bloco `{% block content %}` inteiro por:

```django
{% block content %}
<div class="max-w-screen-xl mx-auto">

  <p class="mb-6 max-w-3xl text-sm text-slate-600">
    Histórico de requisições visíveis ao seu papel. Filtre por solicitante/beneficiário,
    estado, período{% if mostrar_filtro_setor %} ou setor{% endif %}; o recorte fica na
    URL e pode ser compartilhado.
  </p>

  {% url 'requisicoes:historico' as url_historico %}

  {% comment %}
  Barra de filtros: disclosure nativo details/summary no mobile.
  sm:block! força visibilidade no desktop (Tailwind v4: importante como sufixo).
  {% endcomment %}
  <details class="mb-6" open>
    <summary
      class="sm:hidden mb-4 flex min-h-11 cursor-pointer list-none items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
    >
      Filtros
      <span aria-hidden="true" class="ml-2 text-slate-400">▼</span>
    </summary>
    <div>
  <form
    method="get"
    action="{{ url_historico }}"
    hx-get="{{ url_historico }}"
    hx-target="#resultados-historico-requisicoes"
    hx-push-url="true"
    class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
  >
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <div>
        <label for="filtro-texto" class="block text-xs font-medium uppercase tracking-wide text-slate-500">
          Solicitante ou beneficiário
        </label>
        <input
          type="search"
          id="filtro-texto"
          name="texto"
          value="{{ filtros.texto }}"
          placeholder="Nome ou matrícula"
          class="mt-1 block min-h-11 w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm placeholder:text-slate-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        >
      </div>

      <div>
        <label for="filtro-data-ini" class="block text-xs font-medium uppercase tracking-wide text-slate-500">
          De
        </label>
        <input
          type="date"
          id="filtro-data-ini"
          name="data_ini"
          value="{{ filtros.data_ini }}"
          class="mt-1 block min-h-11 w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        >
      </div>

      <div>
        <label for="filtro-data-fim" class="block text-xs font-medium uppercase tracking-wide text-slate-500">
          Até
        </label>
        <input
          type="date"
          id="filtro-data-fim"
          name="data_fim"
          value="{{ filtros.data_fim }}"
          class="mt-1 block min-h-11 w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        >
      </div>

      {% if mostrar_filtro_setor %}
        <div>
          <label for="filtro-setor" class="block text-xs font-medium uppercase tracking-wide text-slate-500">
            Setor
          </label>
          <select
            id="filtro-setor"
            name="setor"
            class="mt-1 block min-h-11 w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            <option value="">Todos os setores</option>
            {% for setor_opcao in setores_disponiveis %}
              <option value="{{ setor_opcao.pk }}" {% if filtros.setor == setor_opcao.pk %}selected{% endif %}>
                {{ setor_opcao.nome }}
              </option>
            {% endfor %}
          </select>
        </div>
      {% endif %}
    </div>

    {# Multi-seleção de estado #}
    <fieldset class="mt-4">
      <legend class="text-xs font-medium uppercase tracking-wide text-slate-500">Estado</legend>
      <div class="mt-2 flex flex-wrap gap-x-4 gap-y-2">
        {% for valor, rotulo in estados_opcoes %}
          <label class="inline-flex min-h-11 items-center gap-2 py-1 text-sm text-slate-700">
            <input
              type="checkbox"
              name="estados"
              value="{{ valor }}"
              {% if valor in filtros.estados %}checked{% endif %}
              class="h-5 w-5 rounded border-slate-300 text-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500"
            >
            {{ rotulo }}
          </label>
        {% endfor %}
      </div>
    </fieldset>

    {# Preserva ordenação corrente ao submeter os filtros #}
    {% if ordem == 'asc' %}<input type="hidden" name="ordem" value="asc">{% endif %}

    <div class="mt-4 flex flex-wrap items-center gap-2">
      <button
        type="submit"
        class="inline-flex min-h-11 items-center rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
      >
        Aplicar filtros
      </button>
      {% if tem_filtro_ativo %}
        <a
          href="{{ url_historico }}"
          hx-get="{{ url_historico }}"
          hx-target="#resultados-historico-requisicoes"
          hx-push-url="true"
          class="inline-flex min-h-11 items-center rounded-md border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1"
        >
          Limpar filtros
        </a>
      {% endif %}
    </div>
  </form>
    </div>
  </details>

  {# Wrapper estável do swap HTMX: alvo persistente (id + aria-live único). O partial entrega só o conteúdo interno. #}
  <div id="resultados-historico-requisicoes" aria-live="polite" aria-atomic="true">
    {% include 'requisicoes/partials/_tabela_historico_requisicoes.html' %}
  </div>

</div>
{% endblock %}
```

- [ ] **Step 4: Rodar testes e confirmar sucesso**

Run: `uv run pytest apps/requisicoes/tests/test_views.py::TestHistoricoRequisicoesFiltros apps/requisicoes/tests/test_views.py::TestHistoricoRequisicoesView -v`
Expected: PASS (todos)

- [ ] **Step 5: Commit**

```bash
git add apps/requisicoes/templates/requisicoes/historico_requisicoes.html apps/requisicoes/tests/test_views.py
git commit -m "feat(requisicoes): barra de filtros do historico de requisicoes"
```

---

### Task 7: Flag de nav (context processor) + link no menu

**Files:**
- Modify: `apps/requisicoes/context_processors.py`
- Modify: `apps/core/templates/core/_topbar_nav.html`
- Test: `apps/requisicoes/tests/test_views.py` (adicionar ao final)

**Interfaces:**
- Consumes: `pode_consultar_historico_requisicoes` (Task 2).
- Produces: variável de contexto global `pode_consultar_historico_requisicoes` (bool), disponível em todo template do projeto.

- [ ] **Step 1: Escrever teste falho**

No final de `apps/requisicoes/tests/test_views.py`, adicione:

```python
class TestNavHistoricoRequisicoes:
    def test_menu_mostra_link_para_almox(self, client, chefe_almoxarifado):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL_HISTORICO_REQUISICOES)
        assert URL_HISTORICO_REQUISICOES.encode() in response.content

    def test_menu_esconde_link_para_solicitante(self, client, solicitante):
        client.force_login(solicitante)
        response = client.get(reverse('requisicoes:minhas'))
        assert URL_HISTORICO_REQUISICOES.encode() not in response.content
```

- [ ] **Step 2: Rodar testes e confirmar falha**

Run: `uv run pytest apps/requisicoes/tests/test_views.py::TestNavHistoricoRequisicoes -v`
Expected: FAIL — `test_menu_mostra_link_para_almox` falha porque o link ainda não existe no nav (byte string ausente do HTML).

- [ ] **Step 3: Adicionar a flag ao context processor**

Em `apps/requisicoes/context_processors.py`, adicione ao import de `apps.requisicoes.policies`:

```python
    pode_consultar_historico_requisicoes,
```

No corpo de `flags_de_papel`, adicione a chave `'pode_consultar_historico_requisicoes': False` ao dicionário retornado para usuário não-autenticado, e `'pode_consultar_historico_requisicoes': pode_consultar_historico_requisicoes(papel)` ao dicionário retornado para usuário autenticado — nos mesmos moldes de `pode_consultar_movimentacoes_estoque` já presente nos dois blocos.

- [ ] **Step 4: Adicionar o link ao nav**

Em `apps/core/templates/core/_topbar_nav.html`, dentro da seção `<nav class="app-bar__menu-section" aria-label="Almoxarifado">`, logo após o bloco `{% if pode_consultar_movimentacoes_estoque %}...{% endif %}` (link "Movimentações"), adicione:

```django
  {% if pode_consultar_historico_requisicoes %}
    <a
      href="{% url 'requisicoes:historico' %}"
      class="app-bar__menu-item"
      {% if current == 'requisicoes:historico' %}aria-current="page"{% endif %}
    >
      <svg class="app-bar__menu-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M13 3a9 9 0 1 0 9 9h-2a7 7 0 1 1-7-7v4l5-5-5-5v4z"/>
      </svg>
      Histórico de requisições
    </a>
  {% endif %}
```

Atualize também a condição do `{% if %}` que envolve toda a seção "Almoxarifado" (linha que hoje é `{% if pode_ver_fila_atendimento or pode_consultar_saidas_excepcionais or pode_consultar_catalogo_estoque or pode_consultar_movimentacoes_estoque or pode_visualizar_preview_scpi or pode_consultar_historico_scpi %}`) para incluir `or pode_consultar_historico_requisicoes`.

- [ ] **Step 5: Rodar testes e confirmar sucesso**

Run: `uv run pytest apps/requisicoes/tests/test_views.py::TestNavHistoricoRequisicoes -v`
Expected: PASS (2 testes)

- [ ] **Step 6: Rodar suíte completa do projeto**

Run: `uv run pytest -q -ra --tb=short --strict-markers --disable-warnings -n logical`
Expected: PASS, 0 failures, 0 errors

- [ ] **Step 7: Formatação e lint**

Run: `uv run ruff format . && uv run ruff check . && uv run mypy apps`
Expected: `ruff format` sem alterações pendentes (ou aplica e você re-adiciona ao commit), `ruff check` sem erros, `mypy apps` sem erros novos introduzidos por este plano.

- [ ] **Step 8: Commit**

```bash
git add apps/requisicoes/context_processors.py apps/core/templates/core/_topbar_nav.html apps/requisicoes/tests/test_views.py
git commit -m "feat(requisicoes): link de historico no menu para almoxarifado/chefias"
```

---

## Self-Review (executado ao escrever este plano)

**Cobertura da spec** (`docs/superpowers/specs/2026-07-02-historico-requisicoes-design.md`):
- 1 linha = 1 Requisicao → Task 5/6 (templates).
- Sem model novo → confirmado (só índices no Task 1).
- RBAC espelhando movimentações → Tasks 2-3.
- Colunas (data, número, solicitante, beneficiário, setor, material, status, ação) → Task 5 template.
- Resumo de material (1 item vs N itens) → Task 5 testes + template.
- Filtros (texto, estado, período, setor condicional) → Tasks 4/6.
- Ordenação por criado_em asc/desc, padrão desc → Task 5 view + Task 6 teste.
- Paginação → Task 5.
- Fora de escopo (lote, export, filtro por número) → nenhuma task implementa, conforme decidido.
- Nav condicionado à policy → Task 7.

**Placeholder scan:** nenhum "TBD"/"depois" nos passos; todo código é completo e colável.

**Consistência de tipos/nomes:** `historico_requisicoes_visiveis_para`, `filtrar_historico_requisicoes`, `pode_filtrar_historico_por_setor`, `_setores_do_historico`, `pode_consultar_historico_requisicoes`, `exigir_pode_consultar_historico_requisicoes`, `historico_requisicoes_view`, URL name `requisicoes:historico` — usados de forma idêntica em todas as tasks que os referenciam (checado Tasks 2→5, 3→4→5, 4→5).
