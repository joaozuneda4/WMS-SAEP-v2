import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db.models import Count, Q, QuerySet

from apps.accounts.models import SetorClassificacao, User, VinculoAuxiliar
from apps.estoque.models import (
    MovimentacaoEstoque,
    SaidaExcepcional,
    TipoMovimentacaoEstoque,
)


def listar_saidas_excepcionais(ator_id: int) -> QuerySet:
    return (
        SaidaExcepcional.objects.select_related('registrado_por', 'estoque')
        .annotate(quantidade_itens=Count('itens'))
        .order_by('-criado_em')
    )


def buscar_materiais_saida_excepcional(q: str = '', limite: int = 20):
    """Retorna materiais elegíveis para saída excepcional (JSON autocomplete).

    Elegível = ativo, com saldo_fisico > 0 em qualquer estoque.
    """
    from django.db.models import Q

    from apps.estoque.models import Material

    qs = Material.objects.filter(ativo=True, saldos__saldo_fisico__gt=0).distinct()
    if q:
        qs = qs.filter(Q(codigo__icontains=q) | Q(nome__icontains=q))
    return qs.order_by('nome')[:limite]


def buscar_detalhe_saida_excepcional(saida_id: int) -> SaidaExcepcional | None:
    """Retorna SaidaExcepcional com itens e relações prefetchadas, ou None."""
    try:
        return (
            SaidaExcepcional.objects.select_related(
                'registrado_por', 'estoque', 'estornado_por'
            )
            .prefetch_related('itens__material')
            .get(pk=saida_id)
        )
    except SaidaExcepcional.DoesNotExist:
        return None


@dataclass
class LinhaPreviewSCPI:
    cadpro: str
    nome_material: str | None
    denominacao_scpi: str
    material_id: int | None
    saldo_wms: Decimal
    saldo_scpi: Decimal
    delta: Decimal
    status: str  # 'ok' | 'divergente' | 'novo'


def _normalizar_csv_scpi(conteudo_bytes: bytes) -> str:
    import re

    from apps.core.exceptions import DadosInvalidos

    try:
        texto = conteudo_bytes.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise DadosInvalidos(
            'Arquivo deve estar em UTF-8 (BOM opcional).',
            code='csv_codificacao_invalida',
        )

    cadpro_re = re.compile(r'^\d{3}\.\d{3}\.\d{3};')
    linhas_raw = texto.splitlines()

    registros: list[str] = []
    buffer: list[str] = []

    for linha in linhas_raw:
        linha = linha.rstrip('\r')
        if cadpro_re.match(linha) or (
            not registros and not buffer and linha.startswith('CADPRO')
        ):
            if buffer:
                registros.append(' '.join(buffer))
                buffer = []
            buffer.append(linha)
        else:
            if buffer:
                buffer.append(linha.strip())
            else:
                registros.append(linha)

    if buffer:
        registros.append(' '.join(buffer))

    return '\n'.join(registros)


def _parse_linhas_csv_scpi(conteudo: str) -> list[dict]:
    from apps.core.exceptions import DadosInvalidos

    reader = csv.DictReader(io.StringIO(conteudo), delimiter=';')
    if reader.fieldnames is None or 'CADPRO' not in reader.fieldnames:
        raise DadosInvalidos(
            'CSV inválido: coluna CADPRO não encontrada.',
            code='csv_coluna_ausente',
        )
    colunas_quantidade = [
        f for f in reader.fieldnames if 'QUAN3' in f.upper() or f.upper() == 'QT'
    ]
    if not colunas_quantidade:
        raise DadosInvalidos(
            'CSV inválido: coluna de quantidade não encontrada.',
            code='csv_coluna_ausente',
        )
    col_qtd = colunas_quantidade[0]
    _COLUNAS_NOME = ('DISC1', 'DENOMINACAO')
    col_den = next(
        (f for f in reader.fieldnames if f.upper() in _COLUNAS_NOME),
        None,
    )
    linhas = []
    for i, row in enumerate(reader, start=2):
        cadpro = (row.get('CADPRO') or '').strip()
        qtd_raw = (row.get(col_qtd) or '').strip().replace(',', '.')
        if not cadpro:
            continue
        try:
            quantidade = Decimal(qtd_raw)
        except (InvalidOperation, ValueError):
            raise DadosInvalidos(
                f'Quantidade inválida no produto {cadpro} (linha {i}): "{qtd_raw}".',
                code='csv_quantidade_invalida',
            )
        denominacao = (row.get(col_den) or '').strip() if col_den else ''
        linhas.append(
            {'cadpro': cadpro, 'quantidade': quantidade, 'denominacao': denominacao}
        )
    return linhas


def gerar_preview_importacao_scpi(
    *, conteudo_bytes: bytes, estoque_id: int
) -> list[LinhaPreviewSCPI]:
    """Gera pré-visualização read-only da importação SCPI.

    Compara CADPRO → Material.codigo contra saldo_fisico do estoque indicado.
    Não persiste nenhuma alteração.
    """
    from apps.estoque.models import Material, SaldoEstoque

    conteudo = _normalizar_csv_scpi(conteudo_bytes)
    linhas_raw = _parse_linhas_csv_scpi(conteudo)

    if not linhas_raw:
        return []

    cadpros = [row['cadpro'] for row in linhas_raw]
    materiais = {
        m.codigo: m
        for m in Material.objects.filter(codigo__in=cadpros).only(
            'id', 'codigo', 'nome'
        )
    }
    material_ids = [m.id for m in materiais.values()]
    saldos = {
        s.material_id: s
        for s in SaldoEstoque.objects.filter(
            material_id__in=material_ids, estoque_id=estoque_id
        ).only('material_id', 'saldo_fisico')
    }

    resultado: list[LinhaPreviewSCPI] = []
    for linha in linhas_raw:
        cadpro = linha['cadpro']
        saldo_scpi = linha['quantidade']
        denominacao = linha['denominacao']
        material = materiais.get(cadpro)

        if material is None:
            resultado.append(
                LinhaPreviewSCPI(
                    cadpro=cadpro,
                    nome_material=None,
                    denominacao_scpi=denominacao,
                    material_id=None,
                    saldo_wms=Decimal('0'),
                    saldo_scpi=saldo_scpi,
                    delta=saldo_scpi,
                    status='novo',
                )
            )
            continue

        saldo_obj = saldos.get(material.id)
        saldo_wms = saldo_obj.saldo_fisico if saldo_obj else Decimal('0')
        delta = saldo_scpi - saldo_wms
        status = 'ok' if delta == 0 else 'divergente'

        resultado.append(
            LinhaPreviewSCPI(
                cadpro=cadpro,
                nome_material=material.nome,
                denominacao_scpi=denominacao,
                material_id=material.id,
                saldo_wms=saldo_wms,
                saldo_scpi=saldo_scpi,
                delta=delta,
                status=status,
            )
        )

    return resultado


def listar_historico_importacoes_scpi():
    from apps.estoque.models import ImportacaoSCPI

    return ImportacaoSCPI.objects.select_related('importado_por', 'estoque').order_by(
        '-importado_em'
    )


def listar_materiais_com_saldo(*, busca: str = ''):
    from django.db.models import (
        BooleanField,
        Case,
        DecimalField,
        ExpressionWrapper,
        F,
        Q,
        When,
    )

    from apps.estoque.models import SaldoEstoque

    qs = (
        SaldoEstoque.objects.select_related('material', 'estoque')
        .annotate(
            saldo_disponivel_calculado=ExpressionWrapper(
                F('saldo_fisico') - F('saldo_reservado'),
                output_field=DecimalField(max_digits=12, decimal_places=3),
            ),
            divergente_calculado=Case(
                When(saldo_fisico__lt=F('saldo_reservado'), then=True),
                default=False,
                output_field=BooleanField(),
            ),
        )
        .order_by('material__nome')
    )

    if busca:
        qs = qs.filter(
            Q(material__codigo__icontains=busca) | Q(material__nome__icontains=busca)
        )

    return qs


TIPOS_MOVIMENTO_ENTREGA_LIQUIDA = [
    TipoMovimentacaoEstoque.CONSUMO,
    TipoMovimentacaoEstoque.DEVOLUCAO,
    TipoMovimentacaoEstoque.ESTORNO_REQUISICAO,
]


def entregue_liquida_por_item(*, requisicao_id: int, item_id: int) -> Decimal:
    """Calcula a quantidade entregue líquida de um item de requisição via ledger.

    Entregue líquida = −Σ delta_fisico para movimentações do tipo consumo,
    devolucao ou estorno_requisicao vinculadas à requisição e ao material do item.

    Leitura pura: não faz select_for_update. Quem muta deve travar a requisição
    antes de chamar (ADR-0005). Levanta DadosInvalidos se item_id não pertence
    à requisicao_id.
    """
    from django.db.models import Sum

    from apps.estoque.models import MovimentacaoEstoque
    from apps.requisicoes.models import ItemRequisicao

    try:
        item = ItemRequisicao.objects.get(pk=item_id, requisicao_id=requisicao_id)
    except ItemRequisicao.DoesNotExist as exc:
        from apps.core.exceptions import DadosInvalidos

        raise DadosInvalidos(
            'Item não pertence à requisição informada.',
            code='item_nao_pertence_requisicao',
        ) from exc

    resultado = MovimentacaoEstoque.objects.filter(
        requisicao_id=requisicao_id,
        material_id=item.material_id,
        tipo__in=TIPOS_MOVIMENTO_ENTREGA_LIQUIDA,
    ).aggregate(total=Sum('delta_fisico'))

    total_delta_fisico = resultado['total'] or Decimal('0')
    return -total_delta_fisico


def _eh_almoxarifado(ator: User) -> bool:
    """True se o ator é chefe ou auxiliar ativo de um setor ALMOXARIFADO ativo."""
    try:
        setor = ator.setor_chefiado
        if setor.ativo and setor.classificacao == SetorClassificacao.ALMOXARIFADO:
            return True
    except Exception:
        pass
    return VinculoAuxiliar.objects.filter(
        usuario=ator,
        ativo=True,
        setor__ativo=True,
        setor__classificacao=SetorClassificacao.ALMOXARIFADO,
    ).exists()


def _setores_visiveis_nao_almox(ator: User) -> list[int]:
    """IDs de setores não-almox ativos onde o ator é chefe OU auxiliar ativo.

    Cobre chefe e auxiliar (o helper análogo de requisicoes cobre só chefe).
    """
    setores: set[int] = set()
    try:
        setor = ator.setor_chefiado
        if setor.ativo and setor.classificacao != SetorClassificacao.ALMOXARIFADO:
            setores.add(setor.pk)
    except Exception:
        pass
    vinculos = (
        VinculoAuxiliar.objects.filter(usuario=ator, ativo=True, setor__ativo=True)
        .exclude(setor__classificacao=SetorClassificacao.ALMOXARIFADO)
        .values_list('setor_id', flat=True)
    )
    setores.update(vinculos)
    return list(setores)


def movimentacoes_visiveis_para(ator_id: int) -> QuerySet[MovimentacaoEstoque]:
    """Queryset do ledger visível ao ator, ordenado por -criado_em.

    RBAC (fronteira de segurança — nunca na view/template):
    - superuser → tudo.
    - almoxarifado (chefe ou auxiliar) → tudo, incluindo saídas excepcionais.
    - chefe/aux de setor não-almox → só movimentações com
      ``requisicao__setor_beneficiario`` nos setores do ator; saídas excepcionais
      ficam de fora por construção (têm ``requisicao`` nulo).
    - usuário inativo/inexistente → vazio.
    """
    base_qs = MovimentacaoEstoque.objects.select_related(
        'material',
        'estoque',
        'ator',
        'requisicao',
        'requisicao__setor_beneficiario',
        'saida_excepcional',
    ).order_by('-criado_em')

    try:
        ator = User.objects.get(pk=ator_id)
    except User.DoesNotExist:
        return base_qs.none()

    if not ator.is_active:
        return base_qs.none()

    if ator.is_superuser or _eh_almoxarifado(ator):
        return base_qs

    setores = _setores_visiveis_nao_almox(ator)
    if setores:
        return base_qs.filter(requisicao__setor_beneficiario_id__in=setores)

    return base_qs.none()


def filtrar_movimentacoes(
    qs: QuerySet[MovimentacaoEstoque],
    *,
    material: str | None,
    tipos: list[str],
    data_ini: date | None,
    data_fim: date | None,
    setor: int | None,
) -> QuerySet[MovimentacaoEstoque]:
    """Estreita o queryset de movimentações já escopado por RBAC.

    Aplica filtros **sobre** o ``qs`` recebido (resultado de
    ``movimentacoes_visiveis_para``), de forma que o filtro nunca amplia o
    universo visível — é sempre um ``AND`` adicional. Em particular, ``setor``
    aplicado sobre um qs já escopado a um setor não vaza dado de outro setor.

    - ``material``: busca por ``codigo`` OU ``nome`` (icontains); vazio → no-op.
    - ``tipos``: lista de ``TipoMovimentacaoEstoque``; valores fora do enum são
      descartados; lista vazia → no-op.
    - ``data_ini`` / ``data_fim``: período **inclusivo** sobre o dia de
      ``criado_em``; ``None`` → no-op.
    - ``setor``: ``requisicao__setor_beneficiario_id``; ``None`` → no-op.
    """
    if material:
        qs = qs.filter(
            Q(material__codigo__icontains=material)
            | Q(material__nome__icontains=material)
        )

    tipos_validos = [t for t in tipos if t in TipoMovimentacaoEstoque.values]
    if tipos_validos:
        qs = qs.filter(tipo__in=tipos_validos)

    if data_ini is not None:
        qs = qs.filter(criado_em__date__gte=data_ini)
    if data_fim is not None:
        qs = qs.filter(criado_em__date__lte=data_fim)

    if setor is not None:
        qs = qs.filter(requisicao__setor_beneficiario_id=setor)

    return qs


def pode_filtrar_movimentacoes_por_setor(ator_id: int) -> bool:
    """True se o ator pode filtrar o ledger por setor (somente almoxarifado).

    Chefe/auxiliar de setor já está escopado ao próprio setor pelo RBAC, então
    o filtro de setor não se aplica a ele. Superuser e almoxarifado veem todos
    os setores e podem recortar por setor beneficiário.
    """
    try:
        ator = User.objects.get(pk=ator_id)
    except User.DoesNotExist:
        return False
    if not ator.is_active:
        return False
    return ator.is_superuser or _eh_almoxarifado(ator)
