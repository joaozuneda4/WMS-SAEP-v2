from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.forms import BooleanField
from django.forms.formsets import DELETION_FIELD_NAME
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts.papeis import papel_efetivo
from apps.core.exceptions import (
    ConflitoDominio,
    DadosInvalidos,
    ErroDominio,
    PermissaoNegada,
)
from apps.core.http import htmx_redirect, parse_data_iso
from apps.core.listagem import paginar_com_filtros
from apps.core.presentation import traduz_erro_dominio
from apps.estoque.forms import ItemSaidaExcepcionalFormSet, SaidaExcepcionalForm
from apps.estoque.models import Estoque, SaldoEstoque, TipoMovimentacaoEstoque
from apps.estoque.policies import (
    exigir_pode_consultar_movimentacoes_estoque,
    exigir_pode_consultar_saidas_excepcionais,
    exigir_pode_registrar_saida_excepcional,
    pode_registrar_saida_excepcional,
)
from apps.estoque.selectors import (
    buscar_materiais_saida_excepcional,
    filtrar_movimentacoes,
    listar_saidas_excepcionais,
    movimentacoes_visiveis_para,
    pode_filtrar_movimentacoes_por_setor,
)
from apps.estoque.services import registrar_saida_excepcional


@login_required
@require_GET
def listar_saidas_excepcionais_view(request):
    papel = papel_efetivo(request.user)
    try:
        exigir_pode_consultar_saidas_excepcionais(papel)
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))

    saidas = listar_saidas_excepcionais(request.user.pk)
    return render(
        request,
        'estoque/lista_saidas_excepcionais.html',
        {
            'saidas': saidas,
            'pode_registrar': pode_registrar_saida_excepcional(papel),
        },
    )


PAGINA_MOVIMENTACOES_TAMANHO = 25

# Chip "só saídas": atalho que recorta o ledger nas saídas reais de material.
TIPOS_SO_SAIDAS = [
    TipoMovimentacaoEstoque.CONSUMO,
    TipoMovimentacaoEstoque.SAIDA_EXCEPCIONAL,
]


def _setores_beneficiarios_do_ledger(visiveis):
    """Setores beneficiários presentes no ledger visível (opções do filtro de
    setor, exibido apenas para almoxarifado)."""
    from apps.accounts.models import Setor

    ids = (
        visiveis.exclude(requisicao__isnull=True)
        .values_list('requisicao__setor_beneficiario_id', flat=True)
        .distinct()
    )
    return Setor.objects.filter(pk__in=ids).order_by('nome')


@login_required
@require_GET
def historico_movimentacoes_view(request):
    """Ledger de movimentações visível ao ator (RBAC no selector), filtrável.

    Filtros vivem na querystring (recorte compartilhável). Em requisições HTMX
    devolve apenas o partial da tabela+paginação; caso contrário, a página
    completa. A view chama os selectors por ID (`request.user.pk`) e traduz a
    exceção de domínio em resposta HTTP, conforme ADR-0011/CONVENTIONS.md.
    """
    papel = papel_efetivo(request.user)
    try:
        exigir_pode_consultar_movimentacoes_estoque(papel)
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))

    material = request.GET.get('material', '').strip()
    tipos_brutos = request.GET.getlist('tipos')
    tipos = [t for t in tipos_brutos if t in TipoMovimentacaoEstoque.values]
    data_ini = parse_data_iso(request.GET.get('data_ini'))
    data_fim = parse_data_iso(request.GET.get('data_fim'))

    mostrar_filtro_setor = pode_filtrar_movimentacoes_por_setor(request.user.pk)
    setor = None
    if mostrar_filtro_setor:
        setor_bruto = request.GET.get('setor', '')
        if setor_bruto.isdigit():
            setor = int(setor_bruto)

    visiveis = movimentacoes_visiveis_para(request.user.pk)
    movimentacoes = filtrar_movimentacoes(
        visiveis,
        material=material or None,
        tipos=tipos,
        data_ini=data_ini,
        data_fim=data_fim,
        setor=setor,
    )

    resultado = paginar_com_filtros(
        request, movimentacoes, per_page=PAGINA_MOVIMENTACOES_TAMANHO
    )

    setores_disponiveis = []
    if mostrar_filtro_setor:
        setores_disponiveis = _setores_beneficiarios_do_ledger(visiveis)

    tem_filtro_ativo = bool(
        material or tipos or data_ini or data_fim or setor is not None
    )
    so_saidas_ativo = set(tipos) == set(TIPOS_SO_SAIDAS)

    params_chip_on = request.GET.copy()
    params_chip_on.pop('page', None)
    params_chip_on.setlist('tipos', [t.value for t in TIPOS_SO_SAIDAS])
    url_chip_so_saidas = '?' + params_chip_on.urlencode()

    params_chip_off = request.GET.copy()
    params_chip_off.pop('page', None)
    params_chip_off.setlist('tipos', [])
    url_chip_sem_so_saidas = '?' + params_chip_off.urlencode()

    contexto = {
        'page_obj': resultado.page_obj,
        'is_htmx': resultado.is_htmx,
        'mostrar_filtro_setor': mostrar_filtro_setor,
        'setores_disponiveis': setores_disponiveis,
        'tipos_opcoes': TipoMovimentacaoEstoque.choices,
        'filtros': {
            'material': material,
            'tipos': tipos,
            'data_ini': request.GET.get('data_ini', ''),
            'data_fim': request.GET.get('data_fim', ''),
            'setor': setor,
        },
        'ordem': resultado.ordem,
        'aria_sort': resultado.aria_sort,
        'url_ordenacao': resultado.url_ordenacao,
        'url_chip_so_saidas': url_chip_so_saidas,
        'url_chip_sem_so_saidas': url_chip_sem_so_saidas,
        'tem_filtro_ativo': tem_filtro_ativo,
        'so_saidas_ativo': so_saidas_ativo,
        'querystring_filtros': resultado.querystring_filtros,
    }

    if resultado.is_htmx:
        template = 'estoque/historico_movimentacoes.html#resultados'
    else:
        template = 'estoque/historico_movimentacoes.html'
    return render(request, template, contexto)


@login_required
@require_http_methods(['GET', 'POST'])
def nova_saida_excepcional_view(request):
    papel = papel_efetivo(request.user)
    try:
        exigir_pode_registrar_saida_excepcional(papel)
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))

    estoque = Estoque.objects.filter(ativo=True).first()

    if estoque is None:
        return render(
            request,
            'estoque/nova_saida_excepcional.html',
            {
                'estoque': None,
                'form': SaidaExcepcionalForm(),
                'formset': ItemSaidaExcepcionalFormSet(prefix='itens', initial=[{}]),
                'erro_geral': 'Não há estoque ativo configurado.',
            },
            status=409,
        )

    if request.method == 'GET':
        return render(
            request,
            'estoque/nova_saida_excepcional.html',
            {
                'estoque': estoque,
                'form': SaidaExcepcionalForm(),
                'formset': ItemSaidaExcepcionalFormSet(
                    prefix='itens', initial=[{}], estoque_id=estoque.pk
                ),
            },
        )

    form = SaidaExcepcionalForm(request.POST)
    formset = ItemSaidaExcepcionalFormSet(
        request.POST, prefix='itens', estoque_id=estoque.pk
    )

    if form.is_valid() and formset.is_valid():
        try:
            saida = registrar_saida_excepcional(
                ator_id=request.user.pk,
                estoque_id=estoque.pk,
                motivo=form.cleaned_data['motivo'],
                observacao=form.cleaned_data['observacao'],
                itens=formset.linhas_validas(),
            )
        except PermissaoNegada as exc:
            raise PermissionDenied(str(exc))
        except DadosInvalidos as exc:
            messages.error(request, str(exc))
        except ConflitoDominio as exc:
            messages.warning(request, str(exc))
        else:
            messages.success(
                request, f'Saída {saida.numero_publico} registrada com sucesso.'
            )
            return htmx_redirect(request, reverse('estoque:listar_saidas_excepcionais'))

    return render(
        request,
        'estoque/nova_saida_excepcional.html',
        {'estoque': estoque, 'form': form, 'formset': formset},
    )


@login_required
@require_GET
def nova_linha_item_saida_excepcional_view(request):
    """Retorna partial HTML com nova linha vazia do formset de saída excepcional."""
    papel = papel_efetivo(request.user)
    try:
        exigir_pode_registrar_saida_excepcional(papel)
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))

    try:
        index = int(request.GET.get('index', 0))
    except (ValueError, TypeError):
        index = 0

    form = ItemSaidaExcepcionalFormSet.form(prefix=f'itens-{index}')
    form.fields[DELETION_FIELD_NAME] = BooleanField(label='Deletar', required=False)
    return render(
        request,
        'components/item_form_row.html',
        {
            'material_id_field': form['material_id'],
            'material_label_field': form['material_label'],
            'quantidade_field': form['quantidade'],
            'quantidade_label': 'Quantidade',
            'quantidade_min': '0.001',
            'quantidade_step': 'any',
            'autocomplete_url_name': 'estoque:buscar_materiais_saida_excepcional',
            'autocomplete_item_template': 'estoque/partials/_autocomplete_item_material.html',
            'delete_field': form[DELETION_FIELD_NAME],
            'form_index': index,
        },
    )


@login_required
@require_GET
def buscar_materiais_saida_excepcional_view(request):
    papel = papel_efetivo(request.user)
    try:
        exigir_pode_registrar_saida_excepcional(papel)
    except PermissaoNegada:
        return JsonResponse({'error': 'Sem permissão.'}, status=403)

    q = request.GET.get('q', '').strip()
    materiais = list(buscar_materiais_saida_excepcional(q=q, limite=20))
    material_ids = [m.pk for m in materiais]

    saldo_por_material: dict = {}
    if material_ids:
        for row in (
            SaldoEstoque.objects.filter(material_id__in=material_ids)
            .values('material_id')
            .annotate(
                fisico=Sum(
                    ExpressionWrapper(F('saldo_fisico'), output_field=DecimalField())
                )
            )
        ):
            saldo_por_material[row['material_id']] = row['fisico']

    resultado = [
        {
            'id': m.pk,
            'codigo': m.codigo,
            'nome': m.nome,
            'unidade': m.unidade,
            'label': f'{m.codigo} — {m.nome}',
            'saldo_fisico': str(saldo_por_material.get(m.pk, 0)),
        }
        for m in materiais
    ]
    return JsonResponse({'resultados': resultado})


@login_required
@require_http_methods(['GET'])
def detalhe_saida_excepcional_view(request, pk: int):
    from apps.estoque.policies import pode_estornar_saida_excepcional
    from apps.estoque.selectors import buscar_detalhe_saida_excepcional

    papel = papel_efetivo(request.user)
    try:
        exigir_pode_consultar_saidas_excepcionais(papel)
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))

    saida = buscar_detalhe_saida_excepcional(saida_id=pk)
    if saida is None:
        from django.http import Http404

        raise Http404

    pode_estornar = pode_estornar_saida_excepcional(papel)

    return render(
        request,
        'estoque/detalhe_saida_excepcional.html',
        {
            'saida': saida,
            'pode_estornar': pode_estornar,
        },
    )


@login_required
@require_http_methods(['POST'])
def estornar_saida_excepcional_view(request, pk: int):
    from apps.estoque.policies import exigir_pode_estornar_saida_excepcional
    from apps.estoque.selectors import buscar_detalhe_saida_excepcional
    from apps.estoque.services import estornar_saida_excepcional

    papel = papel_efetivo(request.user)
    try:
        exigir_pode_consultar_saidas_excepcionais(papel)
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))

    try:
        exigir_pode_estornar_saida_excepcional(papel)
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))

    saida = buscar_detalhe_saida_excepcional(saida_id=pk)
    if saida is None:
        from django.http import Http404

        raise Http404

    justificativa = request.POST.get('justificativa', '').strip()

    try:
        estornar_saida_excepcional(
            ator_id=request.user.pk,
            saida_id=pk,
            justificativa=justificativa,
        )
    except ErroDominio as exc:
        pres = traduz_erro_dominio(exc)
        getattr(messages, pres.severity)(request, str(exc))
        return redirect('estoque:detalhe_saida_excepcional', pk=pk)

    messages.success(request, f'Saída {saida.numero_publico} estornada com sucesso.')
    return redirect('estoque:detalhe_saida_excepcional', pk=pk)


@login_required
@require_http_methods(['GET', 'POST'])
def preview_importacao_scpi_view(request):
    from apps.core.exceptions import DadosInvalidos, PermissaoNegada
    from apps.estoque.policies import exigir_pode_visualizar_preview_scpi
    from apps.estoque.selectors import gerar_preview_importacao_scpi

    papel = papel_efetivo(request.user)
    try:
        exigir_pode_visualizar_preview_scpi(papel)
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))

    if request.method == 'GET':
        request.session.pop('scpi_preview_bytes', None)
        request.session.pop('scpi_preview_nome', None)
        return render(request, 'estoque/preview_importacao_scpi.html', {})

    arquivo = request.FILES.get('arquivo')
    if not arquivo:
        return render(
            request,
            'estoque/preview_importacao_scpi.html',
            {'erro_arquivo': 'O arquivo é obrigatório.'},
        )

    estoque = Estoque.objects.filter(ativo=True).first()
    if estoque is None:
        return render(
            request,
            'estoque/preview_importacao_scpi.html',
            {'erro_arquivo': 'Não há estoque ativo configurado.'},
        )

    try:
        conteudo = arquivo.read()
        linhas = gerar_preview_importacao_scpi(
            conteudo_bytes=conteudo,
            estoque_id=estoque.pk,
        )
    except DadosInvalidos as exc:
        return render(
            request,
            'estoque/preview_importacao_scpi.html',
            {'erro_arquivo': str(exc)},
        )

    import base64

    request.session['scpi_preview_bytes'] = base64.b64encode(conteudo).decode('ascii')
    request.session['scpi_preview_nome'] = arquivo.name

    total = len(linhas)
    divergencias = sum(1 for linha in linhas if linha.status == 'divergente')
    novos = sum(1 for linha in linhas if linha.status == 'novo')

    return render(
        request,
        'estoque/preview_importacao_scpi.html',
        {
            'linhas': linhas,
            'total': total,
            'divergencias': divergencias,
            'novos': novos,
            'nome_arquivo': arquivo.name,
            'pode_confirmar': True,
        },
    )


@login_required
@require_http_methods(['GET'])
def sucesso_importacao_scpi_view(request, pk: int):
    from apps.core.exceptions import PermissaoNegada
    from apps.estoque.models import ImportacaoSCPI
    from apps.estoque.policies import exigir_pode_confirmar_importacao_scpi

    papel = papel_efetivo(request.user)
    try:
        exigir_pode_confirmar_importacao_scpi(papel)
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))

    try:
        importacao = ImportacaoSCPI.objects.get(pk=pk)
    except ImportacaoSCPI.DoesNotExist:
        from django.http import Http404

        raise Http404

    return render(
        request,
        'estoque/confirmar_importacao_scpi.html',
        {
            'importacao': importacao,
            'sucesso': True,
        },
    )


@login_required
@require_http_methods(['GET'])
def historico_importacoes_scpi_view(request):
    from apps.core.exceptions import PermissaoNegada
    from apps.estoque.policies import exigir_pode_consultar_historico_scpi
    from apps.estoque.selectors import listar_historico_importacoes_scpi

    papel = papel_efetivo(request.user)
    try:
        exigir_pode_consultar_historico_scpi(papel)
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))

    importacoes = listar_historico_importacoes_scpi()
    return render(
        request,
        'estoque/historico_importacoes_scpi.html',
        {'importacoes': importacoes},
    )


@login_required
@require_GET
def lista_materiais_view(request):
    from apps.core.exceptions import PermissaoNegada
    from apps.estoque.policies import exigir_pode_consultar_catalogo_estoque
    from apps.estoque.selectors import listar_materiais_com_saldo

    papel = papel_efetivo(request.user)
    try:
        exigir_pode_consultar_catalogo_estoque(papel)
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))

    busca = request.GET.get('busca', '').strip()
    saldos = listar_materiais_com_saldo(busca=busca)
    return render(
        request,
        'estoque/lista_materiais.html',
        {'saldos': saldos, 'busca': busca},
    )
