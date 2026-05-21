"""Formulários server-rendered de requisições."""

from django import forms
from django.db import models

from apps.accounts.models import User
from apps.accounts.policies import pode_criar_requisicao_para
from apps.estoque.models import Material, SaldoEstoque


MAX_ITENS_RASCUNHO = 5


class CriarRascunhoRequisicaoForm(forms.Form):
    beneficiario = forms.ModelChoiceField(
        label='Beneficiário',
        queryset=User.objects.none(),
    )
    observacao_geral = forms.CharField(
        label='Observação geral',
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )

    def __init__(self, *args, **kwargs):
        self.ator = kwargs.pop('ator', None)
        super().__init__(*args, **kwargs)
        beneficiarios = User.objects.filter(is_active=True).select_related('setor')
        if self.ator is not None:
            beneficiarios = [
                usuario
                for usuario in beneficiarios
                if pode_criar_requisicao_para(self.ator, usuario)
            ]
            self.fields['beneficiario'].queryset = User.objects.filter(
                id__in=[usuario.id for usuario in beneficiarios],
            ).order_by('nome')
        else:
            self.fields['beneficiario'].queryset = beneficiarios.order_by('nome')

        self.materiais_disponiveis = Material.objects.filter(
            id__in=SaldoEstoque.objects.filter(
                estoque__ativo=True,
                material__ativo=True,
                saldo_fisico__gt=models.F('saldo_reservado'),
            ).values('material_id'),
        ).order_by('nome')
        self.material_choices_datalist = [
            f'{material.codigo} — {material.nome}'
            for material in self.materiais_disponiveis
        ]

        for indice in range(1, MAX_ITENS_RASCUNHO + 1):
            self.fields[f'material_{indice}'] = forms.CharField(
                label=f'Material {indice}',
                required=indice == 1,
                widget=forms.TextInput(
                    attrs={
                        'list': 'materiais-disponiveis',
                        'placeholder': 'Digite código ou nome do material',
                    },
                ),
            )
            self.fields[f'quantidade_solicitada_{indice}'] = forms.DecimalField(
                label='Quantidade solicitada',
                required=indice == 1,
                min_value=0,
                max_digits=12,
                decimal_places=3,
            )

        for field in self.fields.values():
            field.widget.attrs.update(
                {
                    'class': (
                        'mt-2 block w-full rounded-lg border border-slate-300 '
                        'bg-white px-3 py-2 text-sm text-slate-900 shadow-sm '
                        'focus:border-blue-500 focus:outline-none '
                        'focus:ring-2 focus:ring-blue-500'
                    )
                }
            )

    def clean(self):
        cleaned_data = super().clean()
        itens = []
        materiais_usados = set()
        materiais = {
            str(material.id): material for material in self.materiais_disponiveis
        } | {
            f'{material.codigo} — {material.nome}': material
            for material in self.materiais_disponiveis
        }

        for indice in range(1, MAX_ITENS_RASCUNHO + 1):
            material_valor = cleaned_data.get(f'material_{indice}')
            quantidade = cleaned_data.get(f'quantidade_solicitada_{indice}')
            if not material_valor and quantidade is None:
                continue
            if not material_valor or quantidade is None:
                raise forms.ValidationError(
                    'Informe material e quantidade para cada item preenchido.',
                    code='item_incompleto',
                )
            material = materiais.get(str(material_valor))
            if material is None:
                raise forms.ValidationError(
                    'Selecione um material disponível.',
                    code='material_invalido',
                )
            if quantidade <= 0:
                raise forms.ValidationError(
                    'A quantidade solicitada deve ser maior que zero.',
                    code='quantidade_invalida',
                )
            if material.id in materiais_usados:
                raise forms.ValidationError(
                    'A requisição não pode repetir o mesmo material.',
                    code='material_repetido',
                )
            materiais_usados.add(material.id)
            itens.append(
                {
                    'material_id': material.id,
                    'quantidade_solicitada': quantidade,
                }
            )

        if not itens:
            raise forms.ValidationError(
                'A requisição deve ter ao menos um item.',
                code='requisicao_sem_itens',
            )
        self.itens_limpos = itens
        return cleaned_data

    def clean_quantidade_solicitada_1(self):
        quantidade = self.cleaned_data.get('quantidade_solicitada_1')
        if quantidade is None:
            return quantidade
        if quantidade <= 0:
            raise forms.ValidationError(
                'A quantidade solicitada deve ser maior que zero.',
                code='quantidade_invalida',
            )
        return quantidade
