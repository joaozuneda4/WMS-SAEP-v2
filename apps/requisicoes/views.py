"""Views de requisições — finas por definição (ADR-0004).

Fluxo: ler input → chamar service com IDs → traduzir exceção → renderizar/redirect.
Nenhuma regra de domínio, query de escopo ou decisão de autorização própria.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
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
    resolver_escopo_criacao_requisicao,
)
from apps.requisicoes.selectors import materiais_para_requisicao
from apps.requisicoes.services import criar_requisicao, editar_rascunho


def _htmx_redirect(request, url: str) -> HttpResponse:
    """PRG para HTMX: 204 com HX-Redirect; redirect HTTP para requisições normais."""
    if request.headers.get('HX-Request') == 'true':
        response = HttpResponse(status=204)
        response['HX-Redirect'] = url
        return response
    return redirect(url)


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
                if modo == 'self':
                    beneficiario_id = request.user.pk
                else:
                    beneficiario_id = int(form.cleaned_data['beneficiario_id'])

            itens = formset.linhas_validas()

            try:
                req = criar_requisicao(
                    ator_id=request.user.pk,
                    beneficiario_id=beneficiario_id,
                    itens=itens,
                    observacao_geral=form.cleaned_data.get('observacao_geral', ''),
                )
            except (PermissaoNegada, DadosInvalidos) as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    'Rascunho criado com sucesso. Você pode continuar editando antes de enviar para autorização.',
                )
                return redirect('requisicoes:editar_rascunho', pk=req.pk)

        return render(request, 'requisicoes/rascunho_form.html', {
            'form': form,
            'formset': formset,
            'modo': 'criar',
            'escopo': escopo,
        })

    # GET
    form = RequisicaoCriacaoForm(
        modo_beneficiario=escopo.modo_beneficiario,
        beneficiarios=escopo.beneficiarios,
    )
    formset = ItemRequisicaoFormSet(prefix='itens', initial=[{}])
    return render(request, 'requisicoes/rascunho_form.html', {
        'form': form,
        'formset': formset,
        'modo': 'criar',
        'escopo': escopo,
    })


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
                return redirect('requisicoes:editar_rascunho', pk=requisicao.pk)

        return render(request, 'requisicoes/rascunho_form.html', {
            'form': form,
            'formset': formset,
            'modo': 'editar',
            'requisicao': requisicao,
        })

    # GET — preencher com itens existentes
    itens_existentes = list(requisicao.itens.select_related('material').all())
    initial = [
        {
            'material_id': item.material_id,
            'material_label': str(item.material),
            'quantidade_solicitada': int(item.quantidade_solicitada) if item.quantidade_solicitada else '',
        }
        for item in itens_existentes
    ]
    form = RequisicaoForm(initial={'observacao_geral': requisicao.observacao_geral})
    formset = ItemRequisicaoFormSet(prefix='itens', initial=initial or [{}])

    return render(request, 'requisicoes/rascunho_form.html', {
        'form': form,
        'formset': formset,
        'modo': 'editar',
        'requisicao': requisicao,
    })


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

    # Usa o empty_form do formset para garantir prefixo correto
    fs = ItemRequisicaoFormSet(prefix='itens')
    return render(request, 'requisicoes/partials/_item_form_row.html', {
        'form': fs.empty_form,
        'form_index': index,
        'prefix': f'itens-{index}',
    })


# ---------------------------------------------------------------------------
# JSON: autocomplete de materiais
# ---------------------------------------------------------------------------

@login_required
@require_GET
def buscar_materiais(request):
    """Retorna materiais elegíveis para autocomplete (JSON)."""
    q = request.GET.get('q', '').strip()
    materiais = list(materiais_para_requisicao(q=q, limite=20))
    material_ids = [m.pk for m in materiais]

    saldo_por_material: dict = {}
    if material_ids:
        for row in SaldoEstoque.objects.filter(
            material_id__in=material_ids
        ).values('material_id').annotate(
            disponivel=Sum(
                ExpressionWrapper(
                    F('saldo_fisico') - F('saldo_reservado'),
                    output_field=DecimalField(),
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
