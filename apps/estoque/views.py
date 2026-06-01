from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from apps.core.exceptions import ConflitoDominio, DadosInvalidos, PermissaoNegada
from apps.estoque.models import Estoque, SaldoEstoque
from apps.estoque.policies import (
    exigir_pode_consultar_saidas_excepcionais,
    exigir_pode_registrar_saida_excepcional,
    pode_registrar_saida_excepcional,
)
from apps.estoque.selectors import (
    buscar_materiais_saida_excepcional,
    listar_saidas_excepcionais,
)
from apps.estoque.services import registrar_saida_excepcional

MOTIVO_SAIDA_OPCOES = [
    ('avaria', 'Avaria / Deterioração'),
    ('vencimento', 'Vencimento / Prazo expirado'),
    ('obsolescencia', 'Descarte por obsolescência'),
    ('extravio', 'Perda / Extravio'),
    ('ajuste', 'Ajuste de inventário'),
    ('doacao', 'Doação'),
    ('outro', 'Outro'),
]

_MOTIVO_SAIDA_VALORES = {v for v, _ in MOTIVO_SAIDA_OPCOES}


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


@login_required
@require_http_methods(['GET', 'POST'])
def nova_saida_excepcional_view(request):
    try:
        exigir_pode_registrar_saida_excepcional(request.user)
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))

    estoque = Estoque.objects.filter(ativo=True).first()

    if estoque is None:
        return render(
            request,
            'estoque/nova_saida_excepcional.html',
            {
                'estoque': None,
                'motivo_choices': MOTIVO_SAIDA_OPCOES,
                'erro_geral': 'Não há estoque ativo configurado.',
            },
            status=409,
        )

    ctx_base = {'estoque': estoque, 'motivo_choices': MOTIVO_SAIDA_OPCOES}

    if request.method == 'GET':
        return render(request, 'estoque/nova_saida_excepcional.html', ctx_base)

    motivo = request.POST.get('motivo', '').strip()
    observacao = request.POST.get('observacao', '').strip()

    erros = {}
    if not motivo or motivo not in _MOTIVO_SAIDA_VALORES:
        erros['motivo'] = 'Selecione um motivo válido.'
    if not observacao:
        erros['observacao'] = 'A observação é obrigatória.'

    try:
        total_forms = int(request.POST.get('itens-TOTAL_FORMS', 0))
        if total_forms < 0:
            total_forms = 0
    except (TypeError, ValueError):
        total_forms = 0
        erros['itens'] = 'Estrutura de itens inválida.'

    itens_raw = []
    for i in range(total_forms):
        mid = request.POST.get(f'itens-{i}-material_id', '').strip()
        qtd = request.POST.get(f'itens-{i}-quantidade', '').strip()
        if bool(mid) ^ bool(qtd):
            erros['itens'] = (
                'Preencha material e quantidade para cada linha adicionada.'
            )
        elif mid and qtd:
            itens_raw.append({'material_id': mid, 'quantidade': qtd})

    if not itens_raw and 'itens' not in erros:
        erros['itens'] = 'Adicione ao menos um material.'

    def _render_erro(extra=None):
        ctx = {**ctx_base, 'erros': erros, 'motivo': motivo, 'observacao': observacao}
        if extra:
            ctx.update(extra)
        return render(request, 'estoque/nova_saida_excepcional.html', ctx)

    if erros:
        return _render_erro()

    try:
        saida = registrar_saida_excepcional(
            ator_id=request.user.pk,
            estoque_id=estoque.pk,
            motivo=motivo,
            observacao=observacao,
            itens=itens_raw,
        )
    except DadosInvalidos as exc:
        return _render_erro({'erro_geral': str(exc)})
    except ConflitoDominio as exc:
        return _render_erro({'erro_geral': str(exc)})

    messages.success(request, f'Saída {saida.numero_publico} registrada com sucesso.')
    return redirect('estoque:listar_saidas_excepcionais')


@login_required
@require_GET
def buscar_materiais_saida_excepcional_view(request):
    try:
        exigir_pode_registrar_saida_excepcional(request.user)
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

    try:
        exigir_pode_consultar_saidas_excepcionais(request.user)
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))

    saida = buscar_detalhe_saida_excepcional(saida_id=pk)
    if saida is None:
        from django.http import Http404

        raise Http404

    pode_estornar = pode_estornar_saida_excepcional(request.user)

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

    try:
        exigir_pode_consultar_saidas_excepcionais(request.user)
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))

    try:
        exigir_pode_estornar_saida_excepcional(request.user)
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
    except (DadosInvalidos, ConflitoDominio) as exc:
        messages.error(request, str(exc))
        return redirect('estoque:detalhe_saida_excepcional', pk=pk)

    messages.success(request, f'Saída {saida.numero_publico} estornada com sucesso.')
    return redirect('estoque:detalhe_saida_excepcional', pk=pk)


@login_required
@require_http_methods(['GET', 'POST'])
def preview_importacao_scpi_view(request):
    from apps.core.exceptions import DadosInvalidos, PermissaoNegada
    from apps.estoque.policies import exigir_pode_visualizar_preview_scpi
    from apps.estoque.selectors import gerar_preview_importacao_scpi

    try:
        exigir_pode_visualizar_preview_scpi(request.user)
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc))

    if request.method == 'GET':
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
        },
    )
