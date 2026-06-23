from django.contrib import admin

from apps.accounts.models import Setor, User, VinculoAuxiliar


@admin.register(Setor)
class SetorAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nome', 'classificacao', 'chefe', 'ativo')
    list_filter = ('classificacao', 'ativo')
    search_fields = ('codigo', 'nome')
    ordering = ('nome',)

    def save_model(self, request, obj, form, change):
        if change and 'chefe' in form.changed_data and obj.chefe_id is not None:
            from django.core.exceptions import ValidationError

            from apps.accounts.services import trocar_chefe_setor
            from apps.core.exceptions import ErroDominio

            try:
                trocar_chefe_setor(
                    ator_id=request.user.pk,
                    setor_id=obj.pk,
                    novo_chefe_id=obj.chefe_id,
                )
            except ErroDominio as exc:
                raise ValidationError(str(exc)) from exc
            return
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

    def save_model(self, request, obj, form, change):
        if change and 'is_active' in form.changed_data and not obj.is_active:
            from django.core.exceptions import ValidationError

            from apps.accounts.services import desativar_usuario
            from apps.core.exceptions import ErroDominio

            try:
                desativar_usuario(ator_id=request.user.pk, usuario_id=obj.pk)
            except ErroDominio as exc:
                raise ValidationError(str(exc)) from exc
            return
        super().save_model(request, obj, form, change)


@admin.register(VinculoAuxiliar)
class VinculoAuxiliarAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'setor', 'ativo', 'criado_em')
    list_filter = ('ativo', 'setor')
    search_fields = ('usuario__nome', 'setor__nome')
    ordering = ('-criado_em',)

    def save_model(self, request, obj, form, change):
        if 'ativo' in form.changed_data:
            from django.core.exceptions import ValidationError

            from apps.accounts.services import (
                ativar_vinculo_auxiliar,
                desativar_vinculo_auxiliar,
            )
            from apps.core.exceptions import ErroDominio

            try:
                if obj.ativo:
                    ativar_vinculo_auxiliar(
                        ator_id=request.user.pk,
                        usuario_id=obj.usuario_id,
                        setor_id=obj.setor_id,
                    )
                else:
                    desativar_vinculo_auxiliar(
                        ator_id=request.user.pk, vinculo_id=obj.pk
                    )
            except ErroDominio as exc:
                raise ValidationError(str(exc)) from exc
            return
        super().save_model(request, obj, form, change)
