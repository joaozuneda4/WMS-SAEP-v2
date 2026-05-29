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
