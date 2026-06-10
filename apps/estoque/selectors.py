import csv
import io
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.db.models import Count, QuerySet

from apps.estoque.models import SaidaExcepcional


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
