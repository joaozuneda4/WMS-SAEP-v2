"""Views da camada compartilhada de UI. Sem regra de domínio."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse

from apps.requisicoes.policies import (
    pode_ver_fila_atendimento,
    pode_ver_fila_autorizacao,
)


@login_required
def home(request):
    """Dispatcher pós-login — redireciona por papel efetivo do usuário."""
    user = request.user
    if user.is_superuser:
        return redirect('/admin/')
    if pode_ver_fila_atendimento(user):
        return redirect(reverse('requisicoes:atendimentos'))
    if pode_ver_fila_autorizacao(user):
        return redirect(reverse('requisicoes:autorizacoes'))
    return redirect(reverse('requisicoes:minhas'))
