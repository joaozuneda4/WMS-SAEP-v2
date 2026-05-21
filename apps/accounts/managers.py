"""Manager do modelo de usuário, com criação baseada em matrícula."""

from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    """Cria usuários e superusuários identificados por matrícula."""

    use_in_migrations = True

    def _create_user(self, matricula, password, **extra_fields):
        if not matricula:
            raise ValueError('A matrícula é obrigatória.')
        user = self.model(matricula=matricula, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, matricula, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(matricula, password, **extra_fields)

    def create_superuser(self, matricula, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superusuário precisa de is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superusuário precisa de is_superuser=True.')
        return self._create_user(matricula, password, **extra_fields)
