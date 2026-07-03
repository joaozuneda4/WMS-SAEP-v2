"""Seletores de leitura para requisições.

Concentram queries não-triviais: autocomplete de materiais elegíveis e
escopo de visibilidade de requisições por papel (ADR-0004).
Leituras triviais podem usar o ORM direto na view.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from django.db.models import Count, F, OuterRef, Q, QuerySet, Subquery

from apps.accounts.models import User
from apps.accounts.papeis import papel_efetivo
from apps.estoque.models import Material
from apps.requisicoes import policies
from apps.requisicoes.models import (
    EstadoRequisicao,
    EventoTimeline,
    Operacao,
    Requisicao,
    TimelineRequisicao,
)
from apps.requisicoes.transitions import TRANSICOES

if TYPE_CHECKING:
    from apps.accounts.papeis import PapelEfetivo

_POLICY_POR_OPERACAO: dict[Operacao, Callable[['PapelEfetivo', Requisicao], bool]] = {
    Operacao.EDITAR_RASCUNHO: policies.pode_editar_rascunho,
    Operacao.ENVIAR_PARA_AUTORIZACAO: policies.pode_enviar_rascunho,
    Operacao.RETORNAR_PARA_RASCUNHO: policies.pode_retornar_para_rascunho,
    Operacao.RECUSAR: policies.pode_recusar_requisicao,
    Operacao.AUTORIZAR: policies.pode_autorizar_requisicao,
    Operacao.CANCELAR: policies.pode_cancelar_requisicao,
    Operacao.SEPARAR_PARA_RETIRADA: policies.pode_separar_para_retirada,
    Operacao.REGISTRAR_ATENDIMENTO: policies.pode_atender_retirada,
    Operacao.REGISTRAR_DEVOLUCAO: policies.pode_registrar_devolucao,
    Operacao.ESTORNAR: policies.pode_estornar_requisicao,
}


def acoes_disponiveis(
    papel: 'PapelEfetivo', requisicao: Requisicao
) -> frozenset[Operacao]:
    """Capacidades (Operacao) que o papel pode executar sobre requisicao no estado atual.

    Deriva de TRANSICOES (a operação é permitida neste estado?) e das policies
    (este papel pode executá-la?), nesta ordem — a tabela nunca codifica
    autorização (ADR-0011, emenda 2026-06-26). UI e consultas de apresentação
    consomem esta projeção, sem duplicar o grafo de estados; enforcement
    continua nos services via exigir_pode_*.
    """
    acoes = set()
    for operacao, transicao in TRANSICOES.items():
        if requisicao.estado not in transicao.estados_origem:
            continue
        if _POLICY_POR_OPERACAO[operacao](papel, requisicao):
            acoes.add(operacao)
    return frozenset(acoes)


def materiais_para_requisicao(q: str = '', limite: int = 20) -> QuerySet:
    """Retorna materiais elegíveis para inclusão em nova requisição.

    Elegível = ativo, com ao menos um SaldoEstoque com saldo_disponivel > 0
    (saldo_fisico > saldo_reservado implica ausência de divergência crítica).
    Busca por código ou nome (case-insensitive, substring).
    """
    qs = (
        Material.objects.filter(ativo=True)
        .filter(saldos__saldo_fisico__gt=F('saldos__saldo_reservado'))
        .exclude(saldos__saldo_fisico__lt=F('saldos__saldo_reservado'))
        .distinct()
    )
    if q:
        qs = qs.filter(Q(codigo__icontains=q) | Q(nome__icontains=q))
    return qs.order_by('nome')[:limite]


def _eh_almoxarifado(ator: User) -> bool:
    """True se o ator tem papel ativo de chefe ou auxiliar de almoxarifado."""
    return papel_efetivo(ator).eh_almoxarifado


def requisicoes_visiveis_para(ator_id: int) -> QuerySet[Requisicao]:
    """Queryset das requisições visíveis pelo ator (matriz §5).

    Regras:
    - Criador sempre vê (inclui rascunhos próprios).
    - Beneficiário vê fora de rascunho.
    - Chefe de setor não-almox vê requisições do setor (exceto rascunhos de terceiros).
    - Almoxarifado (chefe ou aux) vê todas (exceto rascunhos de terceiros).
    - Superusuário vê todas.
    - Usuário inativo: queryset vazio.
    """
    base_qs = Requisicao.objects.select_related(
        'criador', 'beneficiario', 'setor_beneficiario'
    )
    try:
        ator = User.objects.get(pk=ator_id)
    except User.DoesNotExist:
        return base_qs.none()

    if not ator.is_active:
        return base_qs.none()

    if ator.is_superuser:
        return base_qs.all()

    nao_rascunho = ~Q(estado=EstadoRequisicao.RASCUNHO)
    filtro = Q(criador_id=ator.pk) | (Q(beneficiario_id=ator.pk) & nao_rascunho)

    papel = papel_efetivo(ator)
    if papel.setor_chefiado_ativo_id is not None and not papel.eh_chefe_de_almoxarifado:
        filtro |= Q(setor_beneficiario_id=papel.setor_chefiado_ativo_id) & nao_rascunho

    if papel.eh_almoxarifado:
        filtro |= nao_rascunho

    return base_qs.filter(filtro).distinct()


def minhas_requisicoes(ator_id: int) -> QuerySet[Requisicao]:
    """Subconjunto de ``requisicoes_visiveis_para`` filtrado pelo próprio ator.

    Inclui requisições onde o ator é criador OU beneficiário (fora de rascunho).
    Exclui rascunhos de terceiros mesmo se ator for beneficiário.
    Ordenado por ``-criado_em``.
    """
    visiveis = requisicoes_visiveis_para(ator_id)
    nao_rascunho = ~Q(estado=EstadoRequisicao.RASCUNHO)
    return visiveis.filter(
        Q(criador_id=ator_id) | (Q(beneficiario_id=ator_id) & nao_rascunho)
    ).order_by('-criado_em')


def fila_autorizacao(ator_id: int) -> QuerySet[Requisicao]:
    """Fila de requisições aguardando autorização para chefias autorizadoras."""
    enviada_em_sq = Subquery(
        TimelineRequisicao.objects.filter(
            requisicao=OuterRef('pk'),
            evento=EventoTimeline.ENVIO_AUTORIZACAO,
        )
        .order_by('-criado_em')
        .values('criado_em')[:1]
    )
    base_qs = (
        Requisicao.objects.select_related(
            'criador', 'beneficiario', 'setor_beneficiario'
        )
        .filter(estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO)
        .annotate(quantidade_itens=Count('itens'), enviada_em=enviada_em_sq)
        .order_by('atualizado_em', 'criado_em', 'id')
    )
    try:
        ator = User.objects.get(pk=ator_id)
    except User.DoesNotExist:
        return base_qs.none()

    if not ator.is_active:
        return base_qs.none()

    if ator.is_superuser:
        return base_qs

    try:
        setor_chefiado = ator.setor_chefiado
    except Exception:
        return base_qs.none()

    if not setor_chefiado.ativo:
        return base_qs.none()

    return base_qs.filter(setor_beneficiario_id=setor_chefiado.pk)


def fila_atendimento(ator_id: int) -> QuerySet[Requisicao]:
    """Fila de requisições prontas para separação/retirada pelo almoxarifado."""
    autorizada_em_sq = Subquery(
        TimelineRequisicao.objects.filter(
            requisicao=OuterRef('pk'),
            evento=EventoTimeline.AUTORIZACAO_TOTAL,
        )
        .order_by('-criado_em')
        .values('criado_em')[:1]
    )
    base_qs = (
        Requisicao.objects.select_related(
            'criador', 'beneficiario', 'setor_beneficiario'
        )
        .filter(
            estado__in=[
                EstadoRequisicao.AUTORIZADA,
                EstadoRequisicao.PRONTA_PARA_RETIRADA,
            ]
        )
        .annotate(quantidade_itens=Count('itens'), autorizada_em=autorizada_em_sq)
        .order_by('atualizado_em', 'criado_em', 'id')
    )
    try:
        ator = User.objects.get(pk=ator_id)
    except User.DoesNotExist:
        return base_qs.none()

    if not ator.is_active:
        return base_qs.none()

    if ator.is_superuser:
        return base_qs

    if _eh_almoxarifado(ator):
        return base_qs

    return base_qs.none()


def material_eh_elegivel(material: Material) -> bool:
    """True se o material pode entrar em nova requisição agora.

    Revalida no submit: ativo, sem divergência e saldo disponível > 0.
    """
    if not material.ativo:
        return False
    if material.saldos.filter(saldo_fisico__lt=F('saldo_reservado')).exists():
        return False
    return material.saldos.filter(saldo_fisico__gt=F('saldo_reservado')).exists()


def saldos_por_materiais(material_ids: list[int]) -> dict[int, dict]:
    """Retorna dict {material_id: {elegivel, saldo_disponivel, motivo}} para exibição.

    Usado para sinalizar itens inelegíveis no form de edição de rascunho copiado.
    """
    from apps.estoque.models import Material

    materiais = Material.objects.filter(pk__in=material_ids).prefetch_related('saldos')
    resultado: dict[int, dict] = {}
    for material in materiais:
        saldos = list(material.saldos.all())
        tem_divergencia = any(s.saldo_fisico < s.saldo_reservado for s in saldos)
        saldo_disponivel = sum(
            (s.saldo_fisico - s.saldo_reservado for s in saldos), start=0
        )
        if not material.ativo:
            motivo = 'Material inativo'
            elegivel = False
        elif tem_divergencia:
            motivo = 'Divergência crítica de estoque'
            elegivel = False
        elif saldo_disponivel <= 0:
            motivo = 'Sem saldo disponível'
            elegivel = False
        else:
            motivo = ''
            elegivel = True
        resultado[material.pk] = {
            'elegivel': elegivel,
            'saldo_disponivel': saldo_disponivel,
            'motivo': motivo,
        }
    return resultado


def historico_requisicoes_visiveis_para(ator_id: int) -> QuerySet[Requisicao]:
    """Queryset system-wide de requisições visíveis ao ator (histórico).

    Mais restrito que ``requisicoes_visiveis_para`` (que inclui a visão
    "minhas requisições" de qualquer solicitante): aqui, só quem tem
    visibilidade de papel sobre requisições de outras pessoas enxerga algo.

    RBAC (fronteira de segurança — nunca na view/template):
    - superuser → tudo, incluindo rascunhos (de qualquer um).
    - almoxarifado (chefe ou auxiliar) → tudo, exceto rascunhos — inclusive
      o próprio: histórico não é "minhas requisições", rascunho não enviado
      não aparece aqui mesmo para quem o criou.
    - chefe/aux de setor não-almox → requisições com ``setor_beneficiario``
      nos setores do ator, exceto rascunhos (mesma regra: inclusive o
      próprio rascunho).
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

    nao_rascunho = ~Q(estado=EstadoRequisicao.RASCUNHO)

    papel = papel_efetivo(ator)
    if papel.eh_almoxarifado:
        return base_qs.filter(nao_rascunho)

    setores = list(papel.setores_em_escopo)
    if setores:
        return base_qs.filter(setor_beneficiario_id__in=setores).filter(nao_rascunho)

    return base_qs.none()


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


def setores_do_historico(qs: QuerySet[Requisicao]) -> QuerySet:
    """Setores beneficiários distintos presentes no histórico visível
    (opções do filtro de setor, exibido apenas para almoxarifado)."""
    from apps.accounts.models import Setor

    ids = qs.values_list('setor_beneficiario_id', flat=True).distinct()
    return Setor.objects.filter(pk__in=ids).order_by('nome')
