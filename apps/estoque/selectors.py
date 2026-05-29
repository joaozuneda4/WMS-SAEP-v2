from django.db.models import Count, QuerySet

from apps.estoque.models import SaidaExcepcional


def listar_saidas_excepcionais(ator_id: int) -> QuerySet:
    return (
        SaidaExcepcional.objects.select_related('registrado_por', 'estoque')
        .annotate(quantidade_itens=Count('itens'))
        .order_by('-criado_em')
    )
