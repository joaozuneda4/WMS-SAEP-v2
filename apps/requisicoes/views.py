"""Views server-rendered de requisições."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from apps.core.exceptions import ConflitoDominio, DadosInvalidos, PermissaoNegada
from apps.requisicoes.forms import CriarRascunhoRequisicaoForm
from apps.requisicoes.models import Requisicao
from apps.requisicoes.services import criar_rascunho_requisicao


class NovaRequisicaoView(LoginRequiredMixin, View):
    template_name = 'requisicoes/nova.html'
    form_class = CriarRascunhoRequisicaoForm

    def get(self, request):
        return render(
            request,
            self.template_name,
            {'form': self.form_class(ator=request.user)},
        )

    def post(self, request):
        form = self.form_class(request.POST, ator=request.user)
        beneficiario_id = request.POST.get('beneficiario')
        if (
            beneficiario_id
            and beneficiario_id.isdecimal()
            and not form.fields['beneficiario']
            .queryset.filter(
                id=int(beneficiario_id),
            )
            .exists()
        ):
            raise PermissionDenied(
                'Você não pode criar requisição para este beneficiário.'
            )
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        try:
            requisicao = criar_rascunho_requisicao(
                ator_id=request.user.id,
                beneficiario_id=form.cleaned_data['beneficiario'].id,
                itens=form.itens_limpos,
                observacao_geral=form.cleaned_data['observacao_geral'],
            )
        except PermissaoNegada as exc:
            raise PermissionDenied(str(exc)) from exc
        except (DadosInvalidos, ConflitoDominio) as exc:
            form.add_error(None, str(exc))
            return render(request, self.template_name, {'form': form})
        return redirect(reverse('requisicoes:detalhe', args=[requisicao.id]))


class DetalheRequisicaoView(LoginRequiredMixin, View):
    template_name = 'requisicoes/detalhe.html'

    def get(self, request, pk):
        requisicao = get_object_or_404(
            Requisicao.objects.select_related(
                'criador',
                'beneficiario',
                'setor_beneficiario',
            ).prefetch_related('itens__material', 'eventos__ator'),
            pk=pk,
        )
        if request.user.id not in {requisicao.criador_id, requisicao.beneficiario_id}:
            raise PermissionDenied
        return render(request, self.template_name, {'requisicao': requisicao})
