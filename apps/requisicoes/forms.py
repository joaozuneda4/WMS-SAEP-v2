"""Forms e formsets para criação e edição de rascunho de requisição."""

from decimal import Decimal

from django import forms
from django.forms import BaseFormSet, formset_factory

from apps.requisicoes.types import LinhaAtendimento


class RequisicaoForm(forms.Form):
    """Campos editáveis do cabeçalho de rascunho."""

    observacao_geral = forms.CharField(
        label='Observação geral',
        required=False,
        widget=forms.Textarea(
            attrs={
                'rows': 3,
                'class': 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500 focus:outline-none',
            }
        ),
    )


MODO_CRIACAO_CHOICES = [
    ('proprio', 'Mim mesmo'),
    ('outro', 'Outro beneficiário'),
]


class RequisicaoCriacaoForm(RequisicaoForm):
    """Cabeçalho na criação: adiciona seleção de beneficiário quando aplicável."""

    modo_criacao = forms.ChoiceField(
        label='Criar para',
        choices=MODO_CRIACAO_CHOICES,
        required=False,
        widget=forms.RadioSelect(),
    )
    beneficiario_id = forms.IntegerField(
        label='Beneficiário',
        required=False,
        widget=forms.HiddenInput(),
    )

    def __init__(
        self, *args, modo_beneficiario='proprio', beneficiarios=None, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.modo_beneficiario = modo_beneficiario

        if modo_beneficiario == 'proprio':
            # Sem seleção — beneficiário implícito
            del self.fields['modo_criacao']
            del self.fields['beneficiario_id']
        else:
            self.fields['modo_criacao'].initial = 'proprio'
            # Mostrar select de terceiros
            choices = [('', '---------')] + [
                (u.pk, f'{u.nome} ({u.matricula}) — {u.setor.nome}')
                for u in (beneficiarios or [])
            ]
            self.fields['beneficiario_id'] = forms.ChoiceField(
                label='Beneficiário',
                required=False,
                choices=choices,
                widget=forms.Select(
                    attrs={
                        'class': 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500 focus:outline-none'
                    }
                ),
            )

    def clean(self):
        cleaned_data = super().clean()
        if self.modo_beneficiario == 'proprio':
            return cleaned_data

        modo = cleaned_data.get('modo_criacao')
        if not modo:
            self.add_error('modo_criacao', 'Selecione para quem criar a requisição.')
            return cleaned_data

        if modo == 'outro':
            beneficiario_id = cleaned_data.get('beneficiario_id')
            if not beneficiario_id:
                self.add_error('beneficiario_id', 'Selecione o beneficiário.')

        return cleaned_data


class ItemRequisicaoForm(forms.Form):
    """Linha de item no formset de criação/edição de rascunho."""

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
    quantidade_solicitada = forms.IntegerField(
        label='Quantidade',
        min_value=1,
        required=False,
        widget=forms.NumberInput(
            attrs={
                'class': 'w-28 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500 focus:outline-none',
                'step': '1',
                'min': '1',
            }
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        material_id = cleaned_data.get('material_id')
        quantidade = cleaned_data.get('quantidade_solicitada')

        # Linha vazia (não preenchida) é ignorada na validação individual;
        # o formset clean() decide se há linhas suficientes.
        if not material_id and not quantidade:
            return cleaned_data

        if not material_id:
            self.add_error('material_label', 'Selecione um material.')
        if not quantidade or quantidade <= 0:
            self.add_error(
                'quantidade_solicitada', 'Informe uma quantidade maior que zero.'
            )

        return cleaned_data

    def is_linha_valida(self) -> bool:
        """True se a linha tem material e quantidade válidos."""
        return bool(
            self.cleaned_data.get('material_id')
            and self.cleaned_data.get('quantidade_solicitada', 0) > 0
        )


class BaseItemRequisicaoFormSet(BaseFormSet):
    """Formset base com validação de duplicidade e mínimo de itens."""

    def clean(self):
        if any(self.errors):
            return

        material_ids = []
        linhas_validas = 0

        for form in self.forms:
            if self._form_deletado(form):
                continue
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
            raise forms.ValidationError('A requisição precisa ter ao menos um item.')

    def _form_deletado(self, form) -> bool:
        """True se o form foi marcado para deleção (via campo DELETE do formset)."""
        return self.can_delete and form.cleaned_data.get(
            forms.formsets.DELETION_FIELD_NAME, False
        )

    def linhas_validas(self) -> list[dict]:
        """Retorna lista de dicts com material_id e quantidade_solicitada dos itens válidos."""
        resultado = []
        for form in self.forms:
            if self._form_deletado(form):
                continue
            if not form.cleaned_data or not form.is_linha_valida():
                continue
            resultado.append(
                {
                    'material_id': form.cleaned_data['material_id'],
                    'quantidade_solicitada': form.cleaned_data['quantidade_solicitada'],
                }
            )
        return resultado


ItemRequisicaoFormSet = formset_factory(
    ItemRequisicaoForm,
    formset=BaseItemRequisicaoFormSet,
    extra=0,
    can_delete=True,
)


# ---------------------------------------------------------------------------
# Atendimento (TR-016/017/018)
# ---------------------------------------------------------------------------


class RegistrarAtendimentoCabecalhoForm(forms.Form):
    """Cabeçalho do formulário de atendimento."""

    retirante_nome = forms.CharField(
        label='Retirante',
        max_length=150,
        widget=forms.TextInput(
            attrs={
                'class': (
                    'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm '
                    'focus:border-blue-500 focus:ring-2 focus:ring-blue-500 '
                    'focus:outline-none'
                ),
                'autocomplete': 'off',
                'placeholder': 'Nome de quem está retirando',
            }
        ),
    )
    observacao = forms.CharField(
        label='Observação',
        required=False,
        widget=forms.Textarea(
            attrs={
                'rows': 2,
                'class': (
                    'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm '
                    'focus:border-blue-500 focus:ring-2 focus:ring-blue-500 '
                    'focus:outline-none'
                ),
                'placeholder': 'Opcional',
            }
        ),
    )


class ItemAtendimentoForm(forms.Form):
    """Linha do formset de atendimento (uma por item autorizado)."""

    item_id = forms.IntegerField(widget=forms.HiddenInput())
    quantidade_entregue = forms.DecimalField(
        label='Quantidade entregue',
        min_value=Decimal('0'),
        max_digits=12,
        decimal_places=3,
        widget=forms.NumberInput(
            attrs={
                'class': (
                    'w-32 rounded-lg border border-slate-300 px-3 py-2 text-sm '
                    'focus:border-blue-500 focus:ring-2 focus:ring-blue-500 '
                    'focus:outline-none'
                ),
                'step': '0.001',
                'min': '0',
                'inputmode': 'decimal',
            }
        ),
    )
    justificativa = forms.CharField(
        label='Justificativa',
        required=False,
        widget=forms.TextInput(
            attrs={
                'class': (
                    'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm '
                    'focus:border-blue-500 focus:ring-2 focus:ring-blue-500 '
                    'focus:outline-none'
                ),
                'placeholder': 'Motivo da entrega menor que autorizada',
            }
        ),
    )


class BaseItemAtendimentoFormSet(BaseFormSet):
    """Valida pertencimento e unicidade de item_id contra conjunto permitido."""

    def __init__(self, *args, item_ids_permitidos=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.item_ids_permitidos = {int(i) for i in (item_ids_permitidos or [])}

    def clean(self):
        if any(self.errors):
            return
        item_ids_permitidos = set(self.item_ids_permitidos or [])
        vistos: set[int] = set()
        for form in self.forms:
            if not form.cleaned_data:
                continue
            item_id = form.cleaned_data.get('item_id')
            if item_id is None:
                continue
            if item_id not in item_ids_permitidos:
                form.add_error('item_id', 'Item inválido para esta requisição.')
                raise forms.ValidationError('Item inválido para esta requisição.')
            if item_id in vistos:
                form.add_error('item_id', 'Item duplicado no atendimento.')
                raise forms.ValidationError('Item duplicado no atendimento.')
            vistos.add(item_id)

    def linhas_atendimento(self) -> list[LinhaAtendimento]:
        """Retorna VOs tipados com os dados de atendimento de cada item."""
        resultado = []
        for form in self.forms:
            if not form.cleaned_data:
                continue
            resultado.append(
                LinhaAtendimento(
                    item_id=form.cleaned_data['item_id'],
                    quantidade_entregue=form.cleaned_data['quantidade_entregue'],
                    justificativa=form.cleaned_data.get('justificativa', ''),
                )
            )
        return resultado


class RegistrarDevolucaoForm(forms.Form):
    """Formulário de devolução de item de requisição atendida (TR-020)."""

    quantidade = forms.DecimalField(
        label='Quantidade devolvida',
        min_value=Decimal('0.001'),
        decimal_places=3,
        widget=forms.NumberInput(
            attrs={
                'class': (
                    'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm '
                    'focus:border-blue-500 focus:ring-2 focus:ring-blue-500 '
                    'focus:outline-none'
                ),
                'step': '0.001',
                'min': '0.001',
            }
        ),
    )
    observacao = forms.CharField(
        label='Observação',
        required=False,
        widget=forms.Textarea(
            attrs={
                'rows': 2,
                'class': (
                    'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm '
                    'focus:border-blue-500 focus:ring-2 focus:ring-blue-500 '
                    'focus:outline-none'
                ),
                'placeholder': 'Opcional',
            }
        ),
    )

    def clean_quantidade(self):
        quantidade = self.cleaned_data.get('quantidade')
        if quantidade is not None and quantidade <= 0:
            raise forms.ValidationError('A quantidade deve ser maior que zero.')
        return quantidade


class EstornarRequisicaoForm(forms.Form):
    """Formulário de estorno de requisição atendida (TR-021)."""

    justificativa = forms.CharField(
        label='Justificativa',
        widget=forms.Textarea(
            attrs={
                'rows': 3,
                'class': (
                    'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm '
                    'focus:border-blue-500 focus:ring-2 focus:ring-blue-500 '
                    'focus:outline-none'
                ),
                'placeholder': 'Motivo obrigatório do estorno',
            }
        ),
    )

    def clean_justificativa(self):
        justificativa = self.cleaned_data.get('justificativa', '').strip()
        if not justificativa:
            raise forms.ValidationError('A justificativa é obrigatória.')
        return justificativa


ItemAtendimentoFormSet = formset_factory(
    ItemAtendimentoForm,
    formset=BaseItemAtendimentoFormSet,
    extra=0,
    can_delete=False,
)
