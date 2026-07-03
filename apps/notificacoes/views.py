"""Views de notificações in-app."""

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.notificacoes.models import Notificacao
from apps.notificacoes.selectors import notificacoes_com_numero_publico
from apps.notificacoes.services import (
    marcar_notificacao_lida,
    marcar_todas_notificacoes_lidas,
)


def _htmx_redirect(request, url: str) -> HttpResponse:
    """PRG para HTMX: 204 com HX-Redirect; redirect HTTP para requisições normais."""
    if request.headers.get('HX-Request') == 'true':
        response = HttpResponse(status=204)
        response['HX-Redirect'] = url
        return response
    return redirect(url)


@login_required
@require_GET
def lista_notificacoes_view(request):
    notificacoes = notificacoes_com_numero_publico(request.user.pk)
    return render(
        request,
        'notificacoes/lista.html',
        {'notificacoes': notificacoes},
    )


@login_required
@require_POST
def marcar_lida_view(request, pk: int):
    notificacao = get_object_or_404(Notificacao, pk=pk, destinatario=request.user)
    marcar_notificacao_lida(ator_id=request.user.pk, notificacao_id=notificacao.pk)
    return _htmx_redirect(request, reverse('notificacoes:lista'))


@login_required
@require_POST
def marcar_todas_lidas_view(request):
    marcar_todas_notificacoes_lidas(ator_id=request.user.pk)
    return _htmx_redirect(request, reverse('notificacoes:lista'))
