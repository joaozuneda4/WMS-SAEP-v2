"""Views da camada compartilhada de UI. Sem regra de domínio."""

from django.shortcuts import render

from apps.requisicoes.policies import pode_ser_beneficiario


def home(request):
    can_view_requisicoes = request.user.is_authenticated
    can_create_requisicao = False
    if request.user.is_authenticated:
        can_create_requisicao = pode_ser_beneficiario(request.user)

    return render(
        request,
        'core/home.html',
        {
            'can_view_requisicoes': can_view_requisicoes,
            'can_create_requisicao': can_create_requisicao,
        },
    )
