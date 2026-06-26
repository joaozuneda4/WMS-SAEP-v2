"""Seletores de leitura para requisições.

Concentram queries não-triviais: autocomplete de materiais elegíveis e
escopo de visibilidade de requisições por papel (ADR-0004).
Leituras triviais podem usar o ORM direto na view.
"""

from django.db.models import Count, F, OuterRef, Q, QuerySet, Subquery

from apps.accounts.models import User
from apps.accounts.papeis import papel_efetivo
from apps.estoque.models import Material
from apps.requisicoes.models import (
    EstadoRequisicao,
    EventoTimeline,
    Requisicao,
    TimelineRequisicao,
)


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
