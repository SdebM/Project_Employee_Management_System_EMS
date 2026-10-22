"""Инфраструктурный слой приложения.

Пакет содержит базовые компоненты инфраструктуры:

- :class:`Database` - управление подключением к PostgreSQL
- :class:`Config` - конфигурация приложения (Singleton)
- Исключения: :class:`AppException`, :class:`DatabaseError`, 
  :class:`ValidationError`, :class:`AuthenticationError`,
  :class:`EntityNotFoundError`, :class:`DuplicateEntityError`
- :class:`PermissionManager` - управление правами доступа
"""

from .database import Database
from .config import Config
from .exceptions import (
    AppException,
    DatabaseError,
    ValidationError,
    AuthenticationError,
    PermissionDeniedError,
    EntityNotFoundError,
    DuplicateEntityError,
)
from .permissions import PermissionManager, check_permission

__all__ = [
    'Database', 'Config',
    'AppException', 'DatabaseError', 'ValidationError',
    'AuthenticationError', 'PermissionDeniedError',
    'EntityNotFoundError', 'DuplicateEntityError',
    'PermissionManager', 'check_permission'
]
