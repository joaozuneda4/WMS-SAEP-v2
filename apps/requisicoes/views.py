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

from apps.core.exceptions import (
    ConflitoDominio,
    DadosInvalidos,
    ErroDominio,
    EstadoInvalido,
    PermissaoNegada,
)
from apps.core.presentation import traduz_erro_dominio
from apps.estoque.models import SaldoEstoque
from apps.estoque.selectors import entregue_liquida_por_material
from apps.requisicoes.forms import (
    ItemAtendimentoFormSet,
    ItemRequisicaoFormSet,
    RegistrarAtendimentoCabecalhoForm,
    EstornarRequisicaoForm,
    RegistrarDevolucaoForm,
    RequisicaoCriacaoForm,
    RequisicaoForm,
)
from apps.requisicoes.models import EstadoRequisicao, Requisicao
from apps.requisicoes.policies import (
    exigir_pode_editar_rascunho,
    exigir_pode_ver_fila_atendimento,
    exigir_pode_ver_fila_autorizacao,
    pode_atender_retirada,
    pode_autorizar_requisicao,
    pode_cancelar_requisicao,
    pode_copiar_requisicao,
    pode_editar_rascunho,
    pode_enviar_rascunho,
    pode_recusar_requisicao,
    pode_estornar_requisicao,
    pode_registrar_devolucao,
    pode_retornar_para_rascunho,
    pode_separar_para_retirada,
    pode_ver_fila_autorizacao,
    resolver_escopo_criacao_requisicao,
)
from apps.requisicoes.selectors import (
    fila_atendimento,
    fila_autorizacao,
    materiais_para_requisicao,
    minhas_requisicoes,
    requisicoes_visiveis_para,
    saldos_por_materiais,
)
from apps.requisicoes.services import (
    autorizar_requisicao,
    copiar_requisicao,
    criar_requisicao,
    cancelar_ou_descartar_requisicao,
    editar_rascunho,
    enviar_para_autorizacao,
    recusar_requisicao,
    registrar_atendimento,
    estornar_requisicao,
    registrar_devolucao,
    retornar_para_rascunho,
    separar_para_retirada,
)


def _htmx_redirect(request, url: str) -> HttpResponse:
    """PRG para HTMX: 204 com HX-Redirect; redirect HTTP para requisições normais."""
    if request.headers.get('HX-Request') == 'true':
        response = HttpResponse(status=204)
        response['HX-Redirect'] = url
        return response
    return redirect(url)


def _voltar_url(request, default: str = '') -> str:
    if not default:
        default = reverse('requisicoes:minhas')
    next_url = request.POST.get('next') or request.GET.get('next', '')
    if not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        next_url = default
    return next_url


def _detalhe_context(
    request,
    requisicao: Requisicao,
    *,
    recusa_erro: str = '',
    motivo_recusa: str = '',
    cancelacao_erro: str = '',
    justificativa_cancelamento: str = '',
    cancelamento_modal_aberto: bool = False,
):
    itens = list(requisicao.itens.select_related('material').all())
    pode_devolver = (
        requisicao.estado == EstadoRequisicao.ATENDIDA
        and pode_registrar_devolucao(request.user, requisicao)
    )
    if pode_devolver:
        for item in itens:
            item.entregue_liquida = entregue_liquida_por_material(
                requisicao_id=requisicao.pk, material_id=item.material_id
            )
            item.modal_devolver_id = f'devolver-{item.pk}'
    eventos = list(
        requisicao.eventos.select_related('ator').order_by('-criado_em', '-id')
    )
    enviada_em = None
    if requisicao.estado != EstadoRequisicao.RASCUNHO:
        enviada_em = next(
            (e.criado_em for e in eventos if e.evento == 'envio_autorizacao'),
            None,
        )
    cancelavel = pode_cancelar_requisicao(request.user, requisicao)
    if cancelavel:
        if (
            requisicao.estado == EstadoRequisicao.RASCUNHO
            and requisicao.numero_publico is None
        ):
            cancelamento_titulo = 'Descartar rascunho'
            cancelamento_descricao = (
                'Este rascunho ainda não foi enviado. O descarte remove o registro '
                'definitivamente e não consome número público nem reserva de estoque.'
            )
            cancelamento_trigger = 'Descartar rascunho'
            cancelamento_confirmar = 'Descartar'
            cancelamento_requer_justificativa = False
            cancelamento_variacao = 'danger'
        elif requisicao.estado == EstadoRequisicao.RASCUNHO:
            cancelamento_titulo = 'Cancelar rascunho'
            cancelamento_descricao = (
                'Este rascunho já foi enviado alguma vez. O cancelamento encerra '
                'a requisição sem nova reserva e preserva o número público.'
            )
            cancelamento_trigger = 'Cancelar rascunho'
            cancelamento_confirmar = 'Confirmar cancelamento'
            cancelamento_requer_justificativa = False
            cancelamento_variacao = 'danger'
        elif requisicao.estado == EstadoRequisicao.AGUARDANDO_AUTORIZACAO:
            cancelamento_titulo = 'Cancelar requisição'
            cancelamento_descricao = (
                'A requisição será encerrada antes da autorização. Não há reserva '
                'de estoque a liberar e a justificativa é opcional.'
            )
            cancelamento_trigger = 'Cancelar requisição'
            cancelamento_confirmar = 'Confirmar cancelamento'
            cancelamento_requer_justificativa = False
            cancelamento_variacao = 'danger'
        else:
            cancelamento_titulo = 'Cancelar requisição'
            cancelamento_descricao = (
                'A requisição será encerrada e as reservas voltam ao saldo '
                'disponível. O saldo físico permanece inalterado.'
            )
            cancelamento_trigger = 'Cancelar requisição'
            cancelamento_confirmar = 'Confirmar cancelamento'
            cancelamento_requer_justificativa = True
            cancelamento_variacao = 'danger'
    else:
        cancelamento_titulo = ''
        cancelamento_descricao = ''
        cancelamento_trigger = ''
        cancelamento_confirmar = ''
        cancelamento_requer_justificativa = False
        cancelamento_variacao = ''

    estados_copiavel = {EstadoRequisicao.ATENDIDA, EstadoRequisicao.RECUSADA}
    pode_copiar = requisicao.estado in estados_copiavel and pode_copiar_requisicao(
        request.user, requisicao
    )

    return {
        'requisicao': requisicao,
        'itens': itens,
        'eventos': eventos,
        'voltar_url': _voltar_url(request),
        'pode_enviar': (
            requisicao.estado == EstadoRequisicao.RASCUNHO
            and pode_enviar_rascunho(request.user, requisicao)
        ),
        'pode_editar': (
            requisicao.estado == EstadoRequisicao.RASCUNHO
            and pode_editar_rascunho(request.user, requisicao)
        ),
        'pode_retornar': (
            requisicao.estado == EstadoRequisicao.AGUARDANDO_AUTORIZACAO
            and pode_retornar_para_rascunho(request.user, requisicao)
        ),
        'pode_autorizar': (
            requisicao.estado == EstadoRequisicao.AGUARDANDO_AUTORIZACAO
            and pode_autorizar_requisicao(request.user, requisicao)
        ),
        'pode_recusar': (
            requisicao.estado == EstadoRequisicao.AGUARDANDO_AUTORIZACAO
            and pode_recusar_requisicao(request.user, requisicao)
        ),
        'pode_separar_retirada': (
            requisicao.estado == EstadoRequisicao.AUTORIZADA
            and pode_separar_para_retirada(request.user, requisicao)
        ),
        'pode_atender_retirada': (
            requisicao.estado == EstadoRequisicao.PRONTA_PARA_RETIRADA
            and pode_atender_retirada(request.user, requisicao)
        ),
        'pode_cancelar': cancelavel,
        'pode_copiar': pode_copiar,
        'cancelamento_titulo': cancelamento_titulo,
        'cancelamento_descricao': cancelamento_descricao,
        'cancelamento_trigger': cancelamento_trigger,
        'cancelamento_confirmar': cancelamento_confirmar,
        'cancelamento_requer_justificativa': cancelamento_requer_justificativa,
        'cancelamento_variacao': cancelamento_variacao,
        'cancelamento_erro': cancelacao_erro,
        'justificativa_cancelamento': justificativa_cancelamento,
        'cancelamento_modal_aberto': cancelamento_modal_aberto or bool(cancelacao_erro),
        'recusa_erro': recusa_erro,
        'motivo_recusa': motivo_recusa,
        'cancelamento_hidden_inputs': {'next': _voltar_url(request)},
        'recusar_hidden_inputs': {'next': _voltar_url(request)},
        'retornar_hidden_inputs': {'next': _voltar_url(request)},
        'autorizar_hidden_inputs': {'next': _voltar_url(request)},
        'enviar_hidden_inputs': {'next': _voltar_url(request)},
        'separar_hidden_inputs': {'next': _voltar_url(request)},
        'enviada_em': enviada_em,
        'pode_devolver': pode_devolver,
        'devolucao_form': RegistrarDevolucaoForm(),
        'pode_estornar': (
            requisicao.estado == EstadoRequisicao.ATENDIDA
            and pode_estornar_requisicao(request.user, requisicao)
        ),
        'estorno_form': EstornarRequisicaoForm(),
    }


def _render_detalhe(request, requisicao: Requisicao, **contexto_extra):
    return render(
        request,
        'requisicoes/detalhe.html',
        _detalhe_context(request, requisicao, **contexto_extra),
    )


def _render_modal_erro(
    request,
    *,
    modal_id: str,
    titulo: str,
    descricao: str,
    erro: str,
    form_body_template: str,
    confirm_label: str,
    confirm_variant: str,
    cancel_label: str = 'Voltar',
    icon_variant: str = 'danger',
    contexto_form: dict | None = None,
) -> HttpResponse:
    """Renderiza o fragment de corpo do modal com erros e retorna HTTP 422.

    Permite que o cliente HTMX troque apenas o conteúdo do modal mantendo-o aberto.
    Fallback (sem HTMX) ainda retorna 422 — caller pode redirecionar se preferir.
    """
    contexto = {
        'id': modal_id,
        'titulo': titulo,
        'descricao': descricao,
        'erro': erro,
        'form_body_template': form_body_template,
        'confirm_label': confirm_label,
        'confirm_variant': confirm_variant,
        'cancel_label': cancel_label,
        'icon_variant': icon_variant,
    }
    if contexto_form:
        contexto.update(contexto_form)
    response = render(
        request,
        'requisicoes/partials/_modal_body_fragment.html',
        contexto,
    )
    response.status_code = 422
    return response


# ---------------------------------------------------------------------------
# Home do módulo
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Nova requisição — TR-001
# ---------------------------------------------------------------------------


@login_required
@require_http_methods(['GET', 'POST'])
def nova_requisicao(request):
    try:
        escopo = resolver_escopo_criacao_requisicao(request.user)
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))

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
            except PermissaoNegada as exc:
                raise PermissionDenied(str(exc))
            except ErroDominio as exc:
                pres = traduz_erro_dominio(exc)
                getattr(messages, pres.severity)(request, str(exc))
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
    material_ids = [item.material_id for item in itens_existentes]
    saldo_info = saldos_por_materiais(material_ids)
    tem_item_inelegivel = any(not v['elegivel'] for v in saldo_info.values())

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

    # saldo_info keyed by str(material_id) for template dict lookup
    saldo_info_str = {str(k): v for k, v in saldo_info.items()}

    return render(
        request,
        'requisicoes/rascunho_form.html',
        {
            'form': form,
            'formset': formset,
            'modo': 'editar',
            'requisicao': requisicao,
            'saldo_info': saldo_info_str,
            'tem_item_inelegivel': tem_item_inelegivel,
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


@login_required
@require_GET
def buscar_beneficiarios(request):
    """Retorna beneficiários elegíveis para autocomplete (JSON).

    Restrição de escopo idêntica à de criação de requisição.
    """
    try:
        escopo = resolver_escopo_criacao_requisicao(request.user)
    except PermissaoNegada:
        return JsonResponse(
            {'error': 'Sem permissão para buscar beneficiários.'}, status=403
        )

    q = request.GET.get('q', '').strip()
    qs = escopo.beneficiarios
    if q:
        qs = qs.filter(nome__icontains=q) | qs.filter(matricula__icontains=q)

    resultado = [
        {
            'id': u.pk,
            'nome': u.nome,
            'matricula': u.matricula,
            'setor': u.setor.nome if u.setor else '',
            'label': f'{u.nome} ({u.matricula})',
        }
        for u in qs[:20]
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
# Autorizar requisição — TR-008
# ---------------------------------------------------------------------------


@login_required
@require_http_methods(['POST'])
def autorizar_requisicao_view(request, pk: int):
    """Autoriza integralmente uma requisição e reserva saldo."""
    get_object_or_404(requisicoes_visiveis_para(request.user.pk), pk=pk)
    try:
        requisicao = autorizar_requisicao(
            ator_id=request.user.pk,
            requisicao_id=pk,
        )
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))
    except EstadoInvalido as exc:
        messages.warning(request, str(exc))
        return _htmx_redirect(request, reverse('requisicoes:detalhe', args=[pk]))
    except ConflitoDominio as exc:
        messages.warning(request, str(exc))
        return _htmx_redirect(request, reverse('requisicoes:detalhe', args=[pk]))
    except DadosInvalidos as exc:
        messages.error(request, str(exc))
        return _htmx_redirect(request, reverse('requisicoes:detalhe', args=[pk]))

    messages.success(
        request,
        f'Requisição {requisicao.numero_publico} autorizada com sucesso.',
    )
    detalhe_url = reverse('requisicoes:detalhe', args=[requisicao.pk])
    return _htmx_redirect(request, _voltar_url(request, default=detalhe_url))


@login_required
@require_GET
def fila_atendimento_view(request):
    """Lista requisições autorizadas/prontas para almoxarifado."""
    try:
        exigir_pode_ver_fila_atendimento(request.user)
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))

    requisicoes = fila_atendimento(request.user.pk)
    return render(
        request,
        'requisicoes/fila_atendimento.html',
        {'requisicoes': requisicoes},
    )


@login_required
@require_http_methods(['POST'])
def separar_retirada_view(request, pk: int):
    """Aplica TR-015 (autorizada -> pronta_para_retirada)."""
    get_object_or_404(requisicoes_visiveis_para(request.user.pk), pk=pk)
    try:
        requisicao = separar_para_retirada(
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

    numero = requisicao.numero_publico or f'#{requisicao.pk}'
    messages.success(
        request,
        f'Requisição {numero} pronta para retirada.',
    )
    detalhe_url = reverse('requisicoes:detalhe', args=[requisicao.pk])
    return _htmx_redirect(request, _voltar_url(request, default=detalhe_url))


@login_required
@require_http_methods(['GET', 'POST'])
def registrar_atendimento_view(request, pk: int):
    """Aplica TR-016/017 (pronta_para_retirada -> atendida) com total ou parcial."""
    requisicao = get_object_or_404(requisicoes_visiveis_para(request.user.pk), pk=pk)

    if requisicao.estado != EstadoRequisicao.PRONTA_PARA_RETIRADA:
        messages.warning(request, 'Esta requisição não está pronta para retirada.')
        return _htmx_redirect(request, reverse('requisicoes:detalhe', args=[pk]))
    if not pode_atender_retirada(request.user, requisicao):
        raise PermissionDenied(
            'Você não tem permissão para registrar o atendimento desta requisição.'
        )

    itens_autorizados = list(
        requisicao.itens.select_related('material')
        .filter(quantidade_autorizada__gt=0)
        .order_by('id')
    )

    def _render(cabecalho_form, formset_form, *, status=200):
        linhas = list(zip(itens_autorizados, formset_form.forms))
        return render(
            request,
            'requisicoes/atender_retirada.html',
            {
                'requisicao': requisicao,
                'itens': itens_autorizados,
                'cabecalho': cabecalho_form,
                'formset': formset_form,
                'linhas': linhas,
                'voltar_url': _voltar_url(
                    request, default=reverse('requisicoes:detalhe', args=[pk])
                ),
            },
            status=status,
        )

    item_ids_permitidos = [item.id for item in itens_autorizados]

    if request.method == 'GET':
        cabecalho = RegistrarAtendimentoCabecalhoForm()
        formset = ItemAtendimentoFormSet(
            initial=[
                {
                    'item_id': item.id,
                    'quantidade_entregue': item.quantidade_autorizada,
                    'justificativa': '',
                }
                for item in itens_autorizados
            ],
            prefix='itens',
            item_ids_permitidos=item_ids_permitidos,
        )
        return _render(cabecalho, formset)

    cabecalho = RegistrarAtendimentoCabecalhoForm(request.POST)
    formset = ItemAtendimentoFormSet(
        request.POST,
        prefix='itens',
        item_ids_permitidos=item_ids_permitidos,
    )

    cabecalho_valido = cabecalho.is_valid()
    formset_valido = formset.is_valid()
    if not (cabecalho_valido and formset_valido):
        messages.error(request, 'Corrija os campos destacados.')
        return _render(cabecalho, formset, status=400)

    itens_payload = []
    for form in formset.forms:
        if not form.cleaned_data:
            continue
        itens_payload.append(
            {
                'item_id': form.cleaned_data['item_id'],
                'quantidade_entregue': form.cleaned_data['quantidade_entregue'],
                'justificativa': form.cleaned_data.get('justificativa', ''),
            }
        )

    try:
        requisicao = registrar_atendimento(
            ator_id=request.user.pk,
            requisicao_id=pk,
            itens=itens_payload,
            retirante_nome=cabecalho.cleaned_data['retirante_nome'],
            observacao=cabecalho.cleaned_data.get('observacao', ''),
        )
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))
    except EstadoInvalido as exc:
        messages.warning(request, str(exc))
        return _htmx_redirect(request, reverse('requisicoes:detalhe', args=[pk]))
    except ConflitoDominio as exc:
        messages.warning(request, str(exc))
        return _htmx_redirect(request, reverse('requisicoes:detalhe', args=[pk]))
    except DadosInvalidos as exc:
        messages.error(request, str(exc))
        return _htmx_redirect(request, reverse('requisicoes:detalhe', args=[pk]))

    numero = requisicao.numero_publico or f'#{requisicao.pk}'
    messages.success(
        request,
        f'Retirada da requisição {numero} registrada com sucesso.',
    )
    detalhe_url = reverse('requisicoes:detalhe', args=[requisicao.pk])
    return _htmx_redirect(request, _voltar_url(request, default=detalhe_url))


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
    detalhe_url = reverse('requisicoes:detalhe', args=[requisicao.pk])
    return _htmx_redirect(request, _voltar_url(request, default=detalhe_url))


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
    return _htmx_redirect(
        request,
        _voltar_url(
            request, default=reverse('requisicoes:detalhe', args=[requisicao.pk])
        ),
    )


@login_required
@require_http_methods(['POST'])
def cancelar_requisicao_view(request, pk: int):
    """Cancela ou descarta requisição antes da retirada final."""
    requisicao = get_object_or_404(
        requisicoes_visiveis_para(request.user.pk),
        pk=pk,
    )
    estado_origem = requisicao.estado
    numero_publico = requisicao.numero_publico
    justificativa = request.POST.get('justificativa', '')

    try:
        resultado_cancelamento = cancelar_ou_descartar_requisicao(
            ator_id=request.user.pk,
            requisicao_id=pk,
            justificativa=justificativa,
        )
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))
    except DadosInvalidos as exc:
        if exc.code == 'justificativa_cancelamento_obrigatoria':
            if request.headers.get('HX-Request') == 'true':
                return _render_modal_erro(
                    request,
                    modal_id='confirmar-cancelar',
                    titulo='Cancelar requisição',
                    descricao=(
                        'A requisição será encerrada e as reservas voltam '
                        'ao saldo disponível.'
                    ),
                    erro=str(exc),
                    form_body_template=(
                        'requisicoes/partials/_modal_form_cancelar.html'
                    ),
                    confirm_label='Confirmar cancelamento',
                    confirm_variant='danger',
                    icon_variant='danger',
                    contexto_form={
                        'justificativa_cancelamento': justificativa,
                        'cancelamento_requer_justificativa': True,
                    },
                )
            return _render_detalhe(
                request,
                requisicao,
                cancelacao_erro=str(exc),
                justificativa_cancelamento=justificativa,
                cancelamento_modal_aberto=True,
            )
        messages.error(request, str(exc))
        return _htmx_redirect(request, reverse('requisicoes:detalhe', args=[pk]))
    except EstadoInvalido as exc:
        messages.warning(request, str(exc))
        return _htmx_redirect(request, reverse('requisicoes:detalhe', args=[pk]))
    except ConflitoDominio as exc:
        messages.warning(request, str(exc))
        return _htmx_redirect(request, reverse('requisicoes:detalhe', args=[pk]))

    numero = numero_publico or f'#{pk}'
    if resultado_cancelamento is None:
        messages.success(request, f'Rascunho {numero} descartado com sucesso.')
        return _htmx_redirect(
            request,
            _voltar_url(request, default=reverse('requisicoes:minhas')),
        )

    if estado_origem == EstadoRequisicao.RASCUNHO:
        messages.success(request, f'Rascunho {numero} cancelado com sucesso.')
    elif estado_origem == EstadoRequisicao.AGUARDANDO_AUTORIZACAO:
        messages.success(request, f'Requisição {numero} cancelada.')
    else:
        messages.success(
            request,
            f'Requisição {numero} cancelada. Reservas liberadas.',
        )

    return _htmx_redirect(request, reverse('requisicoes:detalhe', args=[pk]))


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
        if request.headers.get('HX-Request') == 'true':
            return _render_modal_erro(
                request,
                modal_id='confirmar-recusar',
                titulo='Recusar requisição',
                descricao=(
                    'A recusa encerra a requisição sem reservar ou baixar estoque.'
                ),
                erro=str(exc),
                form_body_template='requisicoes/partials/_modal_form_recusar.html',
                confirm_label='Confirmar recusa',
                confirm_variant='danger',
                icon_variant='danger',
                contexto_form={'motivo_recusa': motivo},
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
    return _htmx_redirect(
        request,
        _voltar_url(
            request, default=reverse('requisicoes:detalhe', args=[requisicao.pk])
        ),
    )


@login_required
@require_http_methods(['GET', 'POST'])
def copiar_requisicao_view(request, pk: int):
    """Copia requisição atendida ou recusada para novo rascunho (REQ-09).

    GET mostra confirmação; POST executa a cópia e redireciona para editar.
    """
    requisicao = get_object_or_404(
        requisicoes_visiveis_para(request.user.pk),
        pk=pk,
    )

    if request.method == 'GET':
        return render(
            request,
            'requisicoes/copiar_confirmacao.html',
            {'requisicao': requisicao},
        )

    try:
        novo = copiar_requisicao(
            ator_id=request.user.pk,
            requisicao_id=requisicao.pk,
        )
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))
    except ErroDominio as exc:
        pres = traduz_erro_dominio(exc)
        getattr(messages, pres.severity)(request, str(exc))
        return _render_detalhe(request, requisicao)

    messages.success(
        request,
        'Rascunho criado. Verifique os itens marcados antes de enviar para autorização.',
    )
    return redirect('requisicoes:editar_rascunho', pk=novo.pk)


@login_required
@require_http_methods(['POST'])
def registrar_devolucao_view(request, pk: int, item_pk: int) -> HttpResponse:
    """Registra devolução de item de requisição atendida (TR-020)."""
    get_object_or_404(requisicoes_visiveis_para(request.user.pk), pk=pk)
    form = RegistrarDevolucaoForm(request.POST)
    if not form.is_valid():
        messages.warning(request, form.errors.as_text())
        return _htmx_redirect(request, reverse('requisicoes:detalhe', args=[pk]))
    try:
        registrar_devolucao(
            ator_id=request.user.pk,
            requisicao_id=pk,
            item_id=item_pk,
            quantidade=form.cleaned_data['quantidade'],
            observacao=form.cleaned_data.get('observacao', ''),
        )
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))
    except ErroDominio as exc:
        pres = traduz_erro_dominio(exc)
        getattr(messages, pres.severity)(request, str(exc))
    else:
        messages.success(request, 'Devolução registrada com sucesso.')
    return _htmx_redirect(request, reverse('requisicoes:detalhe', args=[pk]))


@login_required
@require_http_methods(['POST'])
def estornar_requisicao_view(request, pk: int) -> HttpResponse:
    """Estorna requisição atendida (TR-021)."""
    get_object_or_404(requisicoes_visiveis_para(request.user.pk), pk=pk)
    form = EstornarRequisicaoForm(request.POST)
    if not form.is_valid():
        messages.warning(request, form.errors.as_text())
        return _htmx_redirect(request, reverse('requisicoes:detalhe', args=[pk]))
    try:
        estornar_requisicao(
            ator_id=request.user.pk,
            requisicao_id=pk,
            justificativa=form.cleaned_data['justificativa'],
        )
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))
    except ErroDominio as exc:
        pres = traduz_erro_dominio(exc)
        getattr(messages, pres.severity)(request, str(exc))
    else:
        messages.success(request, 'Requisição estornada com sucesso.')
    return _htmx_redirect(request, reverse('requisicoes:detalhe', args=[pk]))


@login_required
@require_http_methods(['POST'])
def confirmar_importacao_scpi_view(request):
    import base64

    from django.urls import reverse as _reverse

    from apps.core.exceptions import ConflitoDominio, DadosInvalidos, PermissaoNegada
    from apps.estoque.models import Estoque
    from apps.estoque.policies import exigir_pode_confirmar_importacao_scpi
    from apps.estoque.services import confirmar_importacao_scpi
    from apps.requisicoes.services.ciclo_vida import (
        registrar_timeline_divergencia_importacao,
    )

    try:
        exigir_pode_confirmar_importacao_scpi(request.user)
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))

    conteudo_b64 = request.session.get('scpi_preview_bytes')
    arquivo_nome = request.session.get('scpi_preview_nome', 'importacao.csv')

    if not conteudo_b64:
        return render(
            request,
            'estoque/confirmar_importacao_scpi.html',
            {
                'erro': 'Nenhuma pré-visualização ativa. Faça o upload do arquivo novamente.'
            },
        )

    estoque = Estoque.objects.filter(ativo=True).first()
    if estoque is None:
        return render(
            request,
            'estoque/confirmar_importacao_scpi.html',
            {'erro': 'Não há estoque ativo configurado.'},
        )

    try:
        conteudo = base64.b64decode(conteudo_b64)
        importacao = confirmar_importacao_scpi(
            ator_id=request.user.id,
            conteudo_bytes=conteudo,
            arquivo_nome=arquivo_nome,
            estoque_id=estoque.pk,
            _pos_importacao_hook=registrar_timeline_divergencia_importacao,
        )
    except ConflitoDominio as exc:
        return render(
            request,
            'estoque/confirmar_importacao_scpi.html',
            {'erro': str(exc)},
        )
    except DadosInvalidos as exc:
        return render(
            request,
            'estoque/confirmar_importacao_scpi.html',
            {'erro': str(exc)},
        )

    request.session.pop('scpi_preview_bytes', None)
    request.session.pop('scpi_preview_nome', None)

    from django.http import HttpResponseRedirect

    return HttpResponseRedirect(
        _reverse('estoque:sucesso_importacao_scpi', kwargs={'pk': importacao.pk})
    )
