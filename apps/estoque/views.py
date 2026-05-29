from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.core.exceptions import PermissaoNegada
from apps.estoque.policies import (
    exigir_pode_consultar_saidas_excepcionais,
    pode_registrar_saida_excepcional,
)
from apps.estoque.selectors import listar_saidas_excepcionais


@login_required
@require_GET
def listar_saidas_excepcionais_view(request):
    try:
        exigir_pode_consultar_saidas_excepcionais(request.user)
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))

    saidas = listar_saidas_excepcionais(request.user.pk)
    return render(
        request,
        'estoque/lista_saidas_excepcionais.html',
        {
            'saidas': saidas,
            'pode_registrar': pode_registrar_saida_excepcional(request.user),
        },
    )
