"""Репозиторий для работы с пользователями системы."""

from typing import List, Optional, Dict, Any
from .base_repository import BaseRepository
from models.users import User
from core.database import Database


class UserRepository(BaseRepository[User]):
    """Репозиторий для CRUD-операций с пользователями."""

    soft_delete_column = 'is_active'
    soft_delete_value = False
    active_value = True

    def __init__(self, db: Database):
        super().__init__(db, 'users')

    def _map_to_entity(self, row: tuple) -> User:
        """Преобразует строку БД в объект User."""
        return User.from_db_row(row)

    def _entity_to_params(self, entity: User) -> tuple:
        """Преобразует User в параметры SQL."""
        return (
            entity.username,
            entity.password_hash,
            entity.role,
            entity.department_id,
            entity.is_active
        )

    def get_all(self, filters: Optional[Dict[str, Any]] = None) -> List[User]:
        """Получает список пользователей.
        
        Args:
            filters: Фильтры поиска:
                - username (str): Поиск по логину (ILIKE)
                - role (str): Фильтр по роли
                - is_active (bool): Фильтр по активности
                
        Returns:
            Список объектов User (без паролей)
        """
        query = """
            SELECT 
                u.id, u.username, u.role, u.department_id, 
                u.is_active, u.created_at
            FROM users u
            WHERE 1=1
        """
        params = []

        if filters:
            if filters.get('username'):
                query += " AND u.username ILIKE %s"
                params.append(f"%{filters['username']}%")
            if filters.get('role'):
                query += " AND u.role = %s"
                params.append(filters['role'])
            if filters.get('is_active') is not None:
                query += " AND u.is_active = %s"
                params.append(filters['is_active'])

        query += " ORDER BY u.username"
        
        rows = self._db.fetch_all(query, tuple(params))
        users = []
        for row in rows:
            user = User(
                id=row['id'],
                username=row['username'],
                password_hash="",  # Не выбираем пароли для безопасности
                role=row['role'],
                department_id=row['department_id'],
                is_active=row['is_active'],
                created_at=row.get('created_at'),
            )
            users.append(user)
        return users
    
    def get_by_id(self, user_id: int) -> Optional[User]:
        """Получает пользователя по ID."""
        query = """
            SELECT id, username, role, department_id, is_active, created_at
            FROM users 
            WHERE id = %s
        """
        row = self._db.fetch_one(query, (user_id,))
        if row:
            return User(
                id=row['id'],
                username=row['username'],
                password_hash="",  # Не выбираем пароль для безопасности
                role=row['role'],
                department_id=row['department_id'],
                is_active=row['is_active'],
                created_at=row.get('created_at'),
            )
        return None
    
    def get_by_id_with_password(self, user_id: int) -> Optional[User]:
        """Получает пользователя по ID с хешем пароля (для аутентификации)."""
        query = """
            SELECT id, username, password_hash, role, department_id, is_active, created_at, last_login
            FROM users 
            WHERE id = %s
        """
        row = self._db.fetch_one(query, (user_id,))
        return User.from_db_row(row) if row else None

    def get_by_username(self, username: str) -> Optional[User]:
        """Получает пользователя по логину (с паролем для аутентификации).
        
        Args:
            username: Логин пользователя
            
        Returns:
            Объект User с password_hash или None
        """
        query = """
            SELECT id, username, password_hash, role, department_id, is_active
            FROM users 
            WHERE username = %s AND is_active = TRUE
        """
        row = self._db.fetch_one(query, (username,))
        return User.from_db_row(row) if row else None

    def create(self, user: User) -> int:
        """Создает нового пользователя.
        
        Returns:
            ID созданного пользователя
        """
        query = """
            INSERT INTO users (username, password_hash, role, department_id, is_active)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """
        params = self._entity_to_params(user)
        result = self._db.execute_query(query, params, return_result=True)
        # RealDictCursor возвращает список словарей: доступ по имени колонки
        return result[0]['id'] if result else None

    def update(self, user: User) -> bool:
        """Обновляет данные пользователя (без пароля)."""
        query = """
            UPDATE users SET
                username = %s, role = %s, department_id = %s, is_active = %s
            WHERE id = %s
        """
        params = (user.username, user.role, user.department_id, user.is_active, user.id)
        return self._db.execute_query(query, params)

    def update_password(self, user_id: int, password_hash: str) -> bool:
        """Обновляет пароль пользователя.
        
        Args:
            user_id: ID пользователя
            password_hash: Новый хеш пароля
            
        Returns:
            True если обновление успешно
        """
        query = "UPDATE users SET password_hash = %s WHERE id = %s"
        return self._db.execute_query(query, (password_hash, user_id))

    def update_last_login(self, user_id: int) -> bool:
        """Обновляет дату последнего входа.
        
        Note:
            В текущей схеме БД столбец last_login отсутствует.
            Метод оставлен для совместимости.
        """
        # Столбец last_login отсутствует в текущей схеме БД
        # Можно добавить: ALTER TABLE users ADD COLUMN last_login TIMESTAMP;
        return True

    def delete(self, user_id: int) -> bool:
        """Удаляет пользователя."""
        query = "DELETE FROM users WHERE id = %s"
        return self._db.execute_query(query, (user_id,))

    def deactivate(self, user_id: int) -> bool:
        """Деактивирует пользователя (мягкое удаление).
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True если деактивация успешна
        """
        query = "UPDATE users SET is_active = FALSE WHERE id = %s"
        return self._db.execute_query(query, (user_id,))

    def username_exists(self, username: str, exclude_id: int = None) -> bool:
        """Проверяет существование логина.
        
        Args:
            username: Логин для проверки
            exclude_id: ID пользователя для исключения (при обновлении)
            
        Returns:
            True если логин уже занят
        """
        query = "SELECT 1 FROM users WHERE username = %s"
        params = [username]
        
        if exclude_id:
            query += " AND id != %s"
            params.append(exclude_id)
            
        result = self._db.fetch_one(query, tuple(params))
        return result is not None
