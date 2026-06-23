from django.contrib import admin, messages
from django.http import HttpResponseRedirect

from apps.accounts.models import Setor, User, VinculoAuxiliar
from apps.core.exceptions import ErroDominio, PermissaoNegada


def _changeform_com_captura_dominio(
    admin_instance, request, object_id, form_url, extra_context
):
    """Wrapper: captura ErroDominio de save_model e exibe como mensagem de erro."""
    from django.core.exceptions import PermissionDenied

    try:
        return admin.ModelAdmin.changeform_view(
            admin_instance, request, object_id, form_url, extra_context
        )
    except PermissaoNegada as exc:
        raise PermissionDenied(str(exc)) from exc
    except ErroDominio as exc:
        admin_instance.message_user(request, str(exc), level=messages.ERROR)
        return HttpResponseRedirect(request.get_full_path())


@admin.register(Setor)
class SetorAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nome', 'classificacao', 'chefe', 'ativo')
    list_filter = ('classificacao', 'ativo')
    search_fields = ('codigo', 'nome')
    ordering = ('nome',)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        return _changeform_com_captura_dominio(
            self, request, object_id, form_url, extra_context
        )

    def save_model(self, request, obj, form, change):
        if change and 'chefe' in form.changed_data:
            from apps.accounts.services import trocar_chefe_setor
            from apps.core.exceptions import ConflitoDominio

            if obj.chefe_id is None:
                raise ConflitoDominio(
                    'Não é possível remover a chefia sem indicar um substituto.',
                    code='chefe_nulo',
                )
            trocar_chefe_setor(
                ator_id=request.user.pk,
                setor_id=obj.pk,
                novo_chefe_id=obj.chefe_id,
            )
        super().save_model(request, obj, form, change)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('matricula', 'nome', 'email', 'setor', 'is_active', 'is_staff')
    list_filter = ('setor', 'is_active', 'is_staff')
    search_fields = ('matricula', 'nome', 'email')
    ordering = ('nome',)
    fieldsets = (
        (None, {'fields': ('matricula', 'password')}),
        ('Informações Pessoais', {'fields': ('nome', 'email', 'setor')}),
        (
            'Permissões',
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser',
                    'groups',
                    'user_permissions',
                )
            },
        ),
        ('Datas Importantes', {'fields': ('last_login', 'date_joined')}),
    )

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        return _changeform_com_captura_dominio(
            self, request, object_id, form_url, extra_context
        )

    def save_model(self, request, obj, form, change):
        if change and 'is_active' in form.changed_data and not obj.is_active:
            from apps.accounts.services import desativar_usuario
            from apps.core.exceptions import ConflitoDominio

            campos_extras = set(form.changed_data) - {'is_active'}
            if campos_extras:
                raise ConflitoDominio(
                    'Desative o usuário separadamente de outras alterações de cadastro.',
                    code='desativacao_com_campos_extras',
                )
            desativar_usuario(ator_id=request.user.pk, usuario_id=obj.pk)
            return  # service já persistiu; super sobrescreveria dados de auditoria
        super().save_model(request, obj, form, change)


@admin.register(VinculoAuxiliar)
class VinculoAuxiliarAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'setor', 'ativo', 'criado_em')
    list_filter = ('ativo', 'setor')
    search_fields = ('usuario__nome', 'setor__nome')
    ordering = ('-criado_em',)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        return _changeform_com_captura_dominio(
            self, request, object_id, form_url, extra_context
        )

    def save_model(self, request, obj, form, change):
        from apps.core.exceptions import ConflitoDominio

        if not change and not obj.ativo:
            raise ConflitoDominio(
                'Não é permitido criar vínculo auxiliar já inativo pelo admin.',
                code='vinculo_inativo_admin',
            )

        if not change and obj.ativo:
            from apps.accounts.services import ativar_vinculo_auxiliar

            vinculo = ativar_vinculo_auxiliar(
                ator_id=request.user.pk,
                usuario_id=obj.usuario_id,
                setor_id=obj.setor_id,
            )
            obj.pk = vinculo.pk
            return  # service já persistiu; super causaria INSERT duplo

        if 'ativo' in form.changed_data:
            campos_identidade = {'usuario', 'setor'} & set(form.changed_data)
            if change and campos_identidade:
                raise ConflitoDominio(
                    'Altere usuário/setor separadamente da ativação do vínculo auxiliar.',
                    code='vinculo_identidade_com_status',
                )

            from apps.accounts.services import (
                ativar_vinculo_auxiliar,
                desativar_vinculo_auxiliar,
            )

            if obj.ativo:
                vinculo = ativar_vinculo_auxiliar(
                    ator_id=request.user.pk,
                    usuario_id=obj.usuario_id,
                    setor_id=obj.setor_id,
                )
                obj.pk = vinculo.pk
                return  # service já persistiu; super causaria INSERT duplo
            elif obj.pk:
                desativar_vinculo_auxiliar(ator_id=request.user.pk, vinculo_id=obj.pk)
                return  # service já persistiu desativado_em; super sobrescreveria
        super().save_model(request, obj, form, change)
