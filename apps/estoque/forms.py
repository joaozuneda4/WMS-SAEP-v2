"""Forms e formset de itens de saída excepcional."""

from decimal import Decimal

from django import forms
from django.forms import BaseFormSet, formset_factory

MOTIVO_SAIDA_OPCOES = [
    ('avaria', 'Avaria / Deterioração'),
    ('vencimento', 'Vencimento / Prazo expirado'),
    ('obsolescencia', 'Descarte por obsolescência'),
    ('extravio', 'Perda / Extravio'),
    ('ajuste', 'Ajuste de inventário'),
    ('doacao', 'Doação'),
    ('outro', 'Outro'),
]


class SaidaExcepcionalForm(forms.Form):
    """Cabeçalho de registro de saída excepcional (SAE-09: motivo fechado, observação obrigatória)."""

    motivo = forms.ChoiceField(
        label='Motivo',
        choices=MOTIVO_SAIDA_OPCOES,
        widget=forms.Select(
            attrs={
                'class': 'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500',
                'autocomplete': 'off',
            }
        ),
    )
    observacao = forms.CharField(
        label='Observação',
        widget=forms.Textarea(
            attrs={
                'rows': 3,
                'class': 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Descreva o contexto e justificativa para esta saída…',
            }
        ),
    )

    def clean_observacao(self):
        observacao = self.cleaned_data.get('observacao', '').strip()
        if not observacao:
            raise forms.ValidationError('A observação é obrigatória.')
        return observacao


class ItemSaidaExcepcionalForm(forms.Form):
    """Linha do formset de itens de saída excepcional."""

    material_id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(attrs={'class': 'material-id-input'}),
    )
    material_label = forms.CharField(
        label='Material',
        required=False,
        widget=forms.TextInput(
            attrs={
                'class': 'material-autocomplete w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500 focus:outline-none',
                'type': 'search',
                'autocomplete': 'off',
                'placeholder': 'Buscar por código ou nome...',
            }
        ),
    )
    quantidade = forms.DecimalField(
        label='Quantidade',
        min_value=Decimal('0.001'),
        decimal_places=3,
        required=False,
        widget=forms.NumberInput(
            attrs={
                'class': 'w-28 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500 focus:outline-none',
                'step': 'any',
                'min': '0.001',
            }
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        material_id = cleaned_data.get('material_id')
        quantidade = cleaned_data.get('quantidade')

        # Linha vazia (não preenchida) é ignorada na validação individual;
        # o formset clean() decide se há linhas suficientes.
        if not material_id and not quantidade:
            return cleaned_data

        if not material_id:
            self.add_error('material_label', 'Selecione um material.')
        if not quantidade or quantidade <= 0:
            self.add_error('quantidade', 'Informe uma quantidade maior que zero.')

        return cleaned_data

    def is_linha_valida(self) -> bool:
        """True se a linha tem material e quantidade válidos."""
        return bool(
            self.cleaned_data.get('material_id')
            and self.cleaned_data.get('quantidade', 0) > 0
        )


class BaseItemSaidaExcepcionalFormSet(BaseFormSet):
    """Formset base com validação de duplicidade, elegibilidade e mínimo de itens."""

    def clean(self):
        if any(self.errors):
            return

        material_ids = []
        linhas_validas = 0

        for form in self.forms:
            if not form.cleaned_data:
                continue
            if not form.is_linha_valida():
                continue

            linhas_validas += 1
            material_id = form.cleaned_data['material_id']

            if material_id in material_ids:
                form.add_error(
                    'material_label',
                    'Este material já foi adicionado em outra linha.',
                )
                raise forms.ValidationError(
                    'Não é permitido adicionar o mesmo material mais de uma vez.'
                )
            material_ids.append(material_id)

        if linhas_validas == 0:
            raise forms.ValidationError('A saída precisa ter ao menos um item.')

        self._validar_elegibilidade(material_ids)

    def _validar_elegibilidade(self, material_ids: list[int]) -> None:
        """Anexa erro à linha cujo material está inativo ou sem saldo físico.

        Mesmo critério de `buscar_materiais_saida_excepcional` — consulta única
        pra evitar N+1 (uma query por linha).
        """
        from apps.estoque.models import Material

        elegiveis = set(
            Material.objects.filter(
                pk__in=material_ids, ativo=True, saldos__saldo_fisico__gt=0
            )
            .distinct()
            .values_list('pk', flat=True)
        )
        for form in self.forms:
            if not form.cleaned_data or not form.is_linha_valida():
                continue
            material_id = form.cleaned_data['material_id']
            if material_id not in elegiveis:
                form.add_error(
                    'material_label',
                    'Material inelegível: inativo ou sem saldo disponível.',
                )

    def linhas_validas(self) -> list[dict]:
        """Retorna lista de dicts com material_id e quantidade dos itens válidos."""
        resultado = []
        for form in self.forms:
            if not form.cleaned_data or not form.is_linha_valida():
                continue
            resultado.append(
                {
                    'material_id': form.cleaned_data['material_id'],
                    'quantidade': form.cleaned_data['quantidade'],
                }
            )
        return resultado


ItemSaidaExcepcionalFormSet = formset_factory(
    ItemSaidaExcepcionalForm,
    formset=BaseItemSaidaExcepcionalFormSet,
    extra=0,
)
