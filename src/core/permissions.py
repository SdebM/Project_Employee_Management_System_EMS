"""Система управления правами доступа.

Модуль реализует Role-Based Access Control (RBAC):

- :class:`Permission` - константы разрешений
- :data:`ROLE_PERMISSIONS` - матрица прав по ролям
- :class:`PermissionManager` - проверка прав пользователя
- :func:`check_permission` - функция проверки с исключением
- :func:`require_permission` - декоратор для методов

Роли системы:
    - **admin** - полный доступ ко всем операциям
    - **manager** - просмотр и экспорт данных своего отдела
    - **employee** - только просмотр общих данных

Пример использования:
    ::
    
        from core.permissions import Permission, check_permission, PermissionManager
        
        # Проверка через функцию (вызывает исключение)
        check_permission(user, Permission.CREATE_EMPLOYEE)
        
        # Проверка через менеджер
        pm = PermissionManager(user)
        if pm.has_permission(Permission.EDIT_EMPLOYEE):
            # выполнить редактирование
            pass

См. также:
    - :mod:`core.exceptions` - исключение PermissionDeniedError
    - :mod:`services` - использование в сервисах
"""

from typing import Dict, List, Set
from functools import wraps
from .exceptions import PermissionDeniedError


class Permission:
    """Константы разрешений."""
    # Сотрудники
    VIEW_EMPLOYEES = "view_employees"
    CREATE_EMPLOYEE = "create_employee"
    EDIT_EMPLOYEE = "edit_employee"
    DELETE_EMPLOYEE = "delete_employee"
    VIEW_CONFIDENTIAL = "view_confidential"  # ИНН, паспорт

    # Отделы
    VIEW_DEPARTMENTS = "view_departments"
    CREATE_DEPARTMENT = "create_department"
    EDIT_DEPARTMENT = "edit_department"
    DELETE_DEPARTMENT = "delete_department"

    # Проекты
    VIEW_PROJECTS = "view_projects"
    CREATE_PROJECT = "create_project"
    EDIT_PROJECT = "edit_project"
    DELETE_PROJECT = "delete_project"

    # Зарплаты
    VIEW_SALARIES = "view_salaries"
    CREATE_SALARY = "create_salary"
    EDIT_SALARY = "edit_salary"
    DELETE_SALARY = "delete_salary"

    # Аналитика
    VIEW_ANALYTICS = "view_analytics"
    EXPORT_DATA = "export_data"

    # Пользователи
    VIEW_USERS = "view_users"
    CREATE_USER = "create_user"
    EDIT_USER = "edit_user"
    DELETE_USER = "delete_user"


# Матрица разрешений по ролям
ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    'admin': {
        # Полный доступ ко всему
        Permission.VIEW_EMPLOYEES, Permission.CREATE_EMPLOYEE,
        Permission.EDIT_EMPLOYEE, Permission.DELETE_EMPLOYEE,
        Permission.VIEW_CONFIDENTIAL,
        Permission.VIEW_DEPARTMENTS, Permission.CREATE_DEPARTMENT,
        Permission.EDIT_DEPARTMENT, Permission.DELETE_DEPARTMENT,
        Permission.VIEW_PROJECTS, Permission.CREATE_PROJECT,
        Permission.EDIT_PROJECT, Permission.DELETE_PROJECT,
        Permission.VIEW_SALARIES, Permission.CREATE_SALARY,
        Permission.EDIT_SALARY, Permission.DELETE_SALARY,
        Permission.VIEW_ANALYTICS, Permission.EXPORT_DATA,
        Permission.VIEW_USERS, Permission.CREATE_USER,
        Permission.EDIT_USER, Permission.DELETE_USER,
    },
    'manager': {
        # Просмотр и экспорт, без конфиденциальных данных
        Permission.VIEW_EMPLOYEES,
        Permission.VIEW_DEPARTMENTS,
        Permission.VIEW_PROJECTS,
        Permission.VIEW_ANALYTICS,
        Permission.EXPORT_DATA,
    },
    'employee': {
        # Только просмотр своих данных
        Permission.VIEW_EMPLOYEES,
        Permission.VIEW_DEPARTMENTS,
    }
}


class PermissionManager:
    """Менеджер проверки прав доступа.
    
    Attributes:
        user: Данные текущего пользователя
        
    Пример использования:
        pm = PermissionManager(current_user)
        if pm.has_permission(Permission.CREATE_EMPLOYEE):
            # создание сотрудника
    """

    def __init__(self, user: dict):
        """
        Args:
            user: Словарь с данными пользователя:
                - role (str): Роль пользователя
                - department_id (int | None): ID отдела
        """
        self.user = user
        self.role = user.get('role', 'employee')
        self.department_id = user.get('department_id')

    def has_permission(self, permission: str) -> bool:
        """Проверяет наличие разрешения у пользователя.
        
        Args:
            permission: Строка разрешения из класса Permission
            
        Returns:
            True если разрешение есть, иначе False
        """
        role_perms = ROLE_PERMISSIONS.get(self.role, set())
        return permission in role_perms

    def check_permission(self, permission: str) -> None:
        """Проверяет разрешение и выбрасывает исключение при отказе.
        
        Args:
            permission: Строка разрешения
            
        Raises:
            PermissionDeniedError: Если нет разрешения
        """
        if not self.has_permission(permission):
            raise PermissionDeniedError(
                f"Недостаточно прав для операции: {permission}"
            )

    def get_allowed_tabs(self) -> List[int]:
        """Возвращает индексы доступных вкладок.
        
        Returns:
            Список индексов вкладок для текущей роли
        """
        tabs_by_role = {
            'admin': [0, 1, 2, 3, 4, 5],  # Все вкладки
            'manager': [0, 1, 2, 4],       # Сотр, Отд, Проекты, Аналитика
            'employee': [0]                 # Только Сотрудники
        }
        return tabs_by_role.get(self.role, [])

    def filter_by_department(self, query_params: dict) -> dict:
        """Добавляет фильтр по отделу для менеджеров.
        
        Args:
            query_params: Параметры запроса
            
        Returns:
            Обновленные параметры с фильтром отдела
        """
        if self.role == 'manager' and self.department_id:
            query_params['department_id'] = self.department_id
        return query_params


def check_permission(user: dict, permission: str) -> None:
    """Функция-хелпер для проверки разрешения.
    
    Args:
        user: Данные пользователя
        permission: Требуемое разрешение
        
    Raises:
        PermissionDeniedError: Если нет разрешения
    """
    pm = PermissionManager(user)
    pm.check_permission(permission)


def require_permission(permission: str):
    """Декоратор для проверки разрешений на уровне метода.
    
    Args:
        permission: Требуемое разрешение
        
    Пример:
        @require_permission(Permission.CREATE_EMPLOYEE)
        def add_employee(self, user, data):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            user = kwargs.get('user') or (args[0] if args else None)
            if user:
                check_permission(user, permission)
            return func(self, *args, **kwargs)
        return wrapper
    return decorator
