"""Views de requisições — finas por definição (ADR-0004).

Fluxo: ler input → chamar service com IDs → traduzir exceção → renderizar/redirect.
Nenhuma regra de domínio, query de escopo ou decisão de autorização própria.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.forms import BooleanField
from django.forms.formsets import DELETION_FIELD_NAME
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods

from apps.core.exceptions import DadosInvalidos, EstadoInvalido, PermissaoNegada
from apps.estoque.models import SaldoEstoque
from apps.requisicoes.forms import (
    ItemRequisicaoFormSet,
    RequisicaoCriacaoForm,
    RequisicaoForm,
)
from apps.requisicoes.models import Requisicao
from apps.requisicoes.policies import (
    exigir_pode_editar_rascunho,
    exigir_pode_ver_fila_autorizacao,
    pode_editar_rascunho,
    pode_enviar_rascunho,
    pode_recusar_requisicao,
    pode_retornar_para_rascunho,
    pode_ver_fila_autorizacao,
    resolver_escopo_criacao_requisicao,
)
from apps.requisicoes.selectors import (
    fila_autorizacao,
    materiais_para_requisicao,
    minhas_requisicoes,
    requisicoes_visiveis_para,
)
from apps.requisicoes.services import (
    criar_requisicao,
    editar_rascunho,
    enviar_para_autorizacao,
    recusar_requisicao,
    retornar_para_rascunho,
)


def _htmx_redirect(request, url: str) -> HttpResponse:
    """PRG para HTMX: 204 com HX-Redirect; redirect HTTP para requisições normais."""
    if request.headers.get('HX-Request') == 'true':
        response = HttpResponse(status=204)
        response['HX-Redirect'] = url
        return response
    return redirect(url)


def _voltar_url(request) -> str:
    next_url = request.GET.get('next', '')
    if not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        next_url = reverse('requisicoes:minhas')
    return next_url


def _detalhe_context(
    request,
    requisicao: Requisicao,
    *,
    recusa_erro: str = '',
    motivo_recusa: str = '',
):
    itens = list(requisicao.itens.select_related('material').all())
    eventos = list(
        requisicao.eventos.select_related('ator').order_by('-criado_em', '-id')
    )
    return {
        'requisicao': requisicao,
        'itens': itens,
        'eventos': eventos,
        'voltar_url': _voltar_url(request),
        'pode_enviar': (
            requisicao.estado == 'rascunho'
            and pode_enviar_rascunho(request.user, requisicao)
        ),
        'pode_editar': (
            requisicao.estado == 'rascunho'
            and pode_editar_rascunho(request.user, requisicao)
        ),
        'pode_retornar': (
            requisicao.estado == 'aguardando_autorizacao'
            and pode_retornar_para_rascunho(request.user, requisicao)
        ),
        'pode_recusar': (
            requisicao.estado == 'aguardando_autorizacao'
            and pode_recusar_requisicao(request.user, requisicao)
        ),
        'recusa_erro': recusa_erro,
        'motivo_recusa': motivo_recusa,
    }


def _render_detalhe(request, requisicao: Requisicao, **contexto_extra):
    return render(
        request,
        'requisicoes/detalhe.html',
        _detalhe_context(request, requisicao, **contexto_extra),
    )


# ---------------------------------------------------------------------------
# Home do módulo
# ---------------------------------------------------------------------------


@login_required
@require_GET
def home(request):
    """Landing page do módulo de requisições."""
    can_create_requisicao = False
    try:
        resolver_escopo_criacao_requisicao(request.user)
    except PermissaoNegada:
        pass
    else:
        can_create_requisicao = True

    return render(
        request,
        'requisicoes/home.html',
        {
            'can_view_minhas': True,
            'can_create_requisicao': can_create_requisicao,
            'can_view_fila': pode_ver_fila_autorizacao(request.user),
        },
    )


# ---------------------------------------------------------------------------
# Nova requisição — TR-001
# ---------------------------------------------------------------------------


@login_required
@require_http_methods(['GET', 'POST'])
def nova_requisicao(request):
    try:
        escopo = resolver_escopo_criacao_requisicao(request.user)
    except PermissaoNegada as exc:
        messages.error(request, str(exc))
        return redirect('core:home')

    if request.method == 'POST':
        form = RequisicaoCriacaoForm(
            request.POST,
            modo_beneficiario=escopo.modo_beneficiario,
            beneficiarios=escopo.beneficiarios,
        )
        formset = ItemRequisicaoFormSet(request.POST, prefix='itens')

        if form.is_valid() and formset.is_valid():
            if escopo.modo_beneficiario == 'proprio':
                beneficiario_id = request.user.pk
            else:
                modo = form.cleaned_data.get('modo_criacao')
                if modo == 'proprio':
                    beneficiario_id = request.user.pk
                else:
                    beneficiario_id = int(form.cleaned_data['beneficiario_id'])

            itens = formset.linhas_validas()
            acao = request.POST.get('acao', 'rascunho')

            try:
                with transaction.atomic():
                    req = criar_requisicao(
                        ator_id=request.user.pk,
                        beneficiario_id=beneficiario_id,
                        itens=itens,
                        observacao_geral=form.cleaned_data.get('observacao_geral', ''),
                    )
                    if acao == 'enviar':
                        req = enviar_para_autorizacao(
                            ator_id=request.user.pk,
                            requisicao_id=req.pk,
                        )
            except (PermissaoNegada, DadosInvalidos) as exc:
                messages.error(request, str(exc))
            except EstadoInvalido as exc:
                messages.warning(request, str(exc))
            else:
                if acao == 'enviar':
                    messages.success(
                        request,
                        f'Requisição enviada para autorização. Número {req.numero_publico}.',
                    )
                    return redirect('requisicoes:detalhe', pk=req.pk)
                messages.success(
                    request,
                    'Rascunho criado com sucesso. Revise os itens antes de enviar para autorização.',
                )
                return redirect('requisicoes:detalhe', pk=req.pk)

        return render(
            request,
            'requisicoes/rascunho_form.html',
            {
                'form': form,
                'formset': formset,
                'modo': 'criar',
                'escopo': escopo,
            },
        )

    # GET
    form = RequisicaoCriacaoForm(
        modo_beneficiario=escopo.modo_beneficiario,
        beneficiarios=escopo.beneficiarios,
    )
    formset = ItemRequisicaoFormSet(prefix='itens', initial=[{}])
    return render(
        request,
        'requisicoes/rascunho_form.html',
        {
            'form': form,
            'formset': formset,
            'modo': 'criar',
            'escopo': escopo,
        },
    )


# ---------------------------------------------------------------------------
# Editar rascunho — TR-002
# ---------------------------------------------------------------------------


@login_required
@require_http_methods(['GET', 'POST'])
def editar_rascunho_view(request, pk: int):
    requisicao = get_object_or_404(
        Requisicao.objects.select_related('beneficiario__setor', 'setor_beneficiario'),
        pk=pk,
    )

    try:
        exigir_pode_editar_rascunho(request.user, requisicao)
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))

    # Estado precisa ser RASCUNHO — 403 é mais correto que 404 aqui
    if requisicao.estado != 'rascunho':
        raise PermissionDenied('Esta requisição não está em rascunho.')

    if request.method == 'POST':
        form = RequisicaoForm(request.POST)
        formset = ItemRequisicaoFormSet(request.POST, prefix='itens')

        if form.is_valid() and formset.is_valid():
            itens = formset.linhas_validas()
            try:
                editar_rascunho(
                    ator_id=request.user.pk,
                    requisicao_id=requisicao.pk,
                    itens=itens,
                    observacao_geral=form.cleaned_data.get('observacao_geral', ''),
                )
            except (PermissaoNegada, DadosInvalidos, EstadoInvalido) as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, 'Rascunho salvo com sucesso.')
                return redirect('requisicoes:detalhe', pk=requisicao.pk)

        return render(
            request,
            'requisicoes/rascunho_form.html',
            {
                'form': form,
                'formset': formset,
                'modo': 'editar',
                'requisicao': requisicao,
            },
        )

    # GET — preencher com itens existentes
    itens_existentes = list(requisicao.itens.select_related('material').all())
    initial = [
        {
            'material_id': item.material_id,
            'material_label': str(item.material),
            'quantidade_solicitada': int(item.quantidade_solicitada)
            if item.quantidade_solicitada
            else '',
        }
        for item in itens_existentes
    ]
    form = RequisicaoForm(initial={'observacao_geral': requisicao.observacao_geral})
    formset = ItemRequisicaoFormSet(prefix='itens', initial=initial or [{}])

    return render(
        request,
        'requisicoes/rascunho_form.html',
        {
            'form': form,
            'formset': formset,
            'modo': 'editar',
            'requisicao': requisicao,
        },
    )


# ---------------------------------------------------------------------------
# HTMX: nova linha de item
# ---------------------------------------------------------------------------


@login_required
@require_GET
def nova_linha_item(request):
    """Retorna partial HTML com nova linha vazia do formset."""
    try:
        index = int(request.GET.get('index', 0))
    except (ValueError, TypeError):
        index = 0

    form = ItemRequisicaoFormSet.form(prefix=f'itens-{index}')
    form.fields[DELETION_FIELD_NAME] = BooleanField(label='Deletar', required=False)
    return render(
        request,
        'requisicoes/partials/_item_form_row.html',
        {
            'form': form,
            'form_index': index,
            'prefix': f'itens-{index}',
        },
    )


# ---------------------------------------------------------------------------
# JSON: autocomplete de materiais
# ---------------------------------------------------------------------------


@login_required
@require_GET
def buscar_materiais(request):
    """Retorna materiais elegíveis para autocomplete (JSON)."""
    try:
        resolver_escopo_criacao_requisicao(request.user)
    except PermissaoNegada:
        return JsonResponse(
            {'error': 'Sem permissão para buscar materiais.'}, status=403
        )

    q = request.GET.get('q', '').strip()
    materiais = list(materiais_para_requisicao(q=q, limite=20))
    material_ids = [m.pk for m in materiais]

    saldo_por_material: dict = {}
    if material_ids:
        for row in (
            SaldoEstoque.objects.filter(material_id__in=material_ids)
            .values('material_id')
            .annotate(
                disponivel=Sum(
                    ExpressionWrapper(
                        F('saldo_fisico') - F('saldo_reservado'),
                        output_field=DecimalField(),
                    )
                )
            )
        ):
            saldo_por_material[row['material_id']] = row['disponivel']

    resultado = [
        {
            'id': m.pk,
            'codigo': m.codigo,
            'nome': m.nome,
            'unidade': m.unidade,
            'label': f'{m.codigo} — {m.nome}',
            'saldo_disponivel': str(saldo_por_material.get(m.pk, 0)),
        }
        for m in materiais
    ]

    return JsonResponse({'resultados': resultado})


# ---------------------------------------------------------------------------
# Minhas requisições — lista
# ---------------------------------------------------------------------------


@login_required
@require_GET
def minhas_requisicoes_view(request):
    """Lista as requisições onde o usuário é criador ou beneficiário.

    Rascunhos de terceiros são filtrados pelo selector.
    """
    requisicoes = minhas_requisicoes(request.user.pk)
    return render(
        request,
        'requisicoes/lista_minhas.html',
        {'requisicoes': requisicoes},
    )


# ---------------------------------------------------------------------------
# Fila de autorização — lista
# ---------------------------------------------------------------------------


@login_required
@require_GET
def fila_autorizacao_view(request):
    """Lista requisições aguardando autorização no escopo da chefia."""
    try:
        exigir_pode_ver_fila_autorizacao(request.user)
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))

    requisicoes = fila_autorizacao(request.user.pk)
    return render(
        request,
        'requisicoes/fila_autorizacao.html',
        {'requisicoes': requisicoes},
    )


# ---------------------------------------------------------------------------
# Detalhe da requisição
# ---------------------------------------------------------------------------


@login_required
@require_GET
def detalhe_requisicao_view(request, pk: int):
    """Renderiza cabeçalho, itens e timeline da requisição.

    Escopo de visibilidade unificado por ``requisicoes_visiveis_para``;
    objetos fora do escopo retornam 404 (ADR-0010) para não revelar
    existência.
    """
    requisicao = get_object_or_404(
        requisicoes_visiveis_para(request.user.pk),
        pk=pk,
    )
    return _render_detalhe(request, requisicao)


# ---------------------------------------------------------------------------
# Enviar rascunho para autorização — TR-005
# ---------------------------------------------------------------------------


@login_required
@require_http_methods(['POST'])
def enviar_rascunho_view(request, pk: int):
    """Envia rascunho para autorização e redireciona para o detalhe.

    A view não verifica estado nem ator: o service revalida sob lock
    (ADR-0005) e lança PermissaoNegada / EstadoInvalido / DadosInvalidos.
    """
    try:
        requisicao = enviar_para_autorizacao(
            ator_id=request.user.pk,
            requisicao_id=pk,
        )
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))
    except EstadoInvalido as exc:
        messages.warning(request, str(exc))
        return _htmx_redirect(request, reverse('requisicoes:detalhe', args=[pk]))
    except DadosInvalidos as exc:
        messages.error(request, str(exc))
        return _htmx_redirect(request, reverse('requisicoes:detalhe', args=[pk]))

    messages.success(
        request,
        f'Requisição enviada para autorização. Número {requisicao.numero_publico}.',
    )
    return _htmx_redirect(request, reverse('requisicoes:detalhe', args=[requisicao.pk]))


# ---------------------------------------------------------------------------
# Retornar para rascunho / recusar — TR-006 / TR-011
# ---------------------------------------------------------------------------


@login_required
@require_http_methods(['POST'])
def retornar_rascunho_view(request, pk: int):
    """Retorna requisição aguardando autorização para rascunho."""
    try:
        requisicao = retornar_para_rascunho(
            ator_id=request.user.pk,
            requisicao_id=pk,
            observacao=request.POST.get('observacao', ''),
        )
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))
    except EstadoInvalido as exc:
        messages.warning(request, str(exc))
        return _htmx_redirect(request, reverse('requisicoes:detalhe', args=[pk]))
    except DadosInvalidos as exc:
        messages.error(request, str(exc))
        return _htmx_redirect(request, reverse('requisicoes:detalhe', args=[pk]))

    messages.success(
        request,
        f'Requisição {requisicao.numero_publico} retornada para rascunho.',
    )
    return _htmx_redirect(request, reverse('requisicoes:detalhe', args=[requisicao.pk]))


@login_required
@require_http_methods(['POST'])
def recusar_requisicao_view(request, pk: int):
    """Recusa requisição aguardando autorização com motivo obrigatório."""
    motivo = request.POST.get('motivo', '')
    try:
        requisicao = recusar_requisicao(
            ator_id=request.user.pk,
            requisicao_id=pk,
            motivo=motivo,
        )
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))
    except DadosInvalidos as exc:
        requisicao = get_object_or_404(
            requisicoes_visiveis_para(request.user.pk),
            pk=pk,
        )
        return _render_detalhe(
            request,
            requisicao,
            recusa_erro=str(exc),
            motivo_recusa=motivo,
        )
    except EstadoInvalido as exc:
        messages.warning(request, str(exc))
        return _htmx_redirect(request, reverse('requisicoes:detalhe', args=[pk]))

    messages.success(request, f'Requisição {requisicao.numero_publico} recusada.')
    return _htmx_redirect(request, reverse('requisicoes:detalhe', args=[requisicao.pk]))
