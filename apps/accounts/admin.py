from django.contrib import admin

from apps.accounts.models import Setor, User, VinculoAuxiliar


@admin.register(Setor)
class SetorAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nome', 'classificacao', 'chefe', 'ativo')
    list_filter = ('classificacao', 'ativo')
    search_fields = ('codigo', 'nome')
    ordering = ('nome',)


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


@admin.register(VinculoAuxiliar)
class VinculoAuxiliarAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'setor', 'ativo', 'criado_em')
    list_filter = ('ativo', 'setor')
    search_fields = ('usuario__nome', 'setor__nome')
    ordering = ('-criado_em',)
