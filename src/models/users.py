"""Модель данных пользователя системы.

Содержит:
    - :class:`UserRole` - перечисление ролей
    - :class:`User` - dataclass пользователя

Роли пользователей:
    - ``admin`` - администратор (полный доступ)
    - ``manager`` - менеджер (просмотр и экспорт)
    - ``employee`` - сотрудник (только просмотр)

Пример:
    ::
    
        user = User(
            username="admin",
            role="admin",
            is_active=True
        )
        print(user.is_admin)  # True
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum


class UserRole(Enum):
    """Роли пользователей в системе."""
    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"


VALID_USER_ROLES = tuple(r.value for r in UserRole)
"""Допустимые строковые значения ролей."""


@dataclass
class User:
    """Модель пользователя системы.

    Поля БД (таблица ``users``):
        id, username, password_hash, role, department_id,
        is_active, created_at, last_login

    Безопасность:
        ``to_dict()`` исключает ``password_hash`` из вывода.
    """

    # --- поля таблицы ---
    id: Optional[int] = None
    username: str = ""
    password_hash: str = ""
    role: str = "employee"
    department_id: Optional[int] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    
    def __post_init__(self) -> None:
        """Проверяет корректность полей после создания."""
        self.username = self.username.strip() if self.username else ""
        if not self.username:
            raise ValueError("username не может быть пустым")
        if self.role not in VALID_USER_ROLES:
            raise ValueError(
                f"role должен быть одним из {VALID_USER_ROLES}, "
                f"получено: '{self.role}'"
            )

    
    @property
    def is_admin(self) -> bool:
        """Проверяет, является ли пользователь администратором."""
        return self.role == UserRole.ADMIN.value

    @property
    def is_manager(self) -> bool:
        """Проверяет, является ли пользователь менеджером."""
        return self.role == UserRole.MANAGER.value

    def has_permission(self, permission: str) -> bool:
        """Проверяет наличие разрешения у пользователя.

        Администратор имеет доступ ко всему (``'all'``).
        """
        permissions = {
            'admin': ['all'],
            'manager': [
                'view_employees', 'view_departments',
                'view_projects', 'export_data', 'view_analytics',
            ],
            'employee': ['view_own_data'],
        }
        user_perms = permissions.get(self.role, [])
        return 'all' in user_perms or permission in user_perms

    
    def to_dict(self) -> dict:
        """Конвертирует модель в словарь (без ``password_hash``)."""
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'department_id': self.department_id,
            'is_active': self.is_active,
            'created_at': self.created_at,
            'last_login': self.last_login

        }

    def to_session_dict(self) -> dict:
        """Возвращает минимальные данные для хранения в сессии."""
        return {
            'id': self.id,
            'role': self.role,
            'department_id': self.department_id,
                'is_active': self.is_active,
                'created_at': self.created_at,
                'last_login': self.last_login

        }

    @classmethod
    def from_db_row(cls, row: dict) -> 'User':
        """Создаёт экземпляр из строки БД (dict от RealDictCursor)."""
        return cls(
            id=row.get('id'),
            username=row.get('username', ''),
            # Если запрос безопасный (без хеша), подставится пустая строка
            password_hash=row.get('password_hash', ''), 
            role=row.get('role', 'employee'),
            department_id=row.get('department_id'),
            is_active=row.get('is_active', True),
            created_at=row.get('created_at'),
            last_login=row.get('last_login')
        )

    
    _ROLE_MAP = {
        'admin': 'Администратор',
        'manager': 'Менеджер',
        'employee': 'Сотрудник',
    }

    def __str__(self) -> str:
        """Краткое строковое представление."""
        role_label = self._ROLE_MAP.get(self.role, self.role)
        status = 'Активен' if self.is_active else 'Неактивен'
        return f"[{self.id or '—'}] {self.username} | {role_label} | {status}"
    
