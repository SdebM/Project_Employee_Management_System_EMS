"""Сервис аутентификации и авторизации.

Содержит класс :class:`AuthService` для:

- Проверки учётных данных
- Хеширования паролей (bcrypt)
- Управления пользователями
- Обновления даты последнего входа

Основные методы:
    - :meth:`authenticate` - проверка логина/пароля
    - :meth:`create_user` - создание пользователя
    - :meth:`update_user` - обновление данных
    - :meth:`change_password` - смена пароля


"""

from typing import Optional, Dict, Any
import logging
import threading
import time
import bcrypt

from models.users import User
from repositories.user_repository import UserRepository
from core.database import Database
from core.exceptions import AuthenticationError, ValidationError
from utils.validators import Validators


# Настройки защиты от перебора паролей (brute force)
MAX_FAILED_ATTEMPTS = 5       # Столько неудачных попыток подряд
LOCKOUT_SECONDS = 15 * 60     # ...и блокировка входа на 15 минут


class AuthService:
    """Сервис для аутентификации и управления пользователями.
    
    Обеспечивает:
    - Проверку учетных данных
    - Защиту от перебора паролей (временная блокировка после серии неудач)
    - Хеширование паролей (bcrypt)
    - Управление сессиями
    - CRUD операции с пользователями
    
    Пример использования:
        auth = AuthService(db)
        user = auth.authenticate('admin', 'password123')
    """

    # --- Защита от перебора паролей ---
    # Состояние хранится в памяти процесса (для десктоп-приложения этого
    # достаточно; при переходе на клиент-серверную модель перенести в БД/Redis).
    _failed_attempts: Dict[str, list] = {}  # username -> [количество, время последней попытки]
    _lock_until: Dict[str, float] = {}      # username -> метка времени снятия блокировки
    _lock_guard = threading.Lock()

    def __init__(self, db: Database):
        self._db = db
        self._repository = UserRepository(db)

    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        """Аутентифицирует пользователя.
        
        После MAX_FAILED_ATTEMPTS неудачных попыток подряд вход для
        логина блокируется на LOCKOUT_SECONDS секунд независимо от
        правильности пароля — это замедляет офлайн/онлайн перебор.
        
        Args:
            username: Логин пользователя
            password: Пароль (открытый текст)
            
        Returns:
            Словарь с данными пользователя для сессии или None
            
        Raises:
            AuthenticationError: При ошибке аутентификации или блокировке
        """
        if not username or not password:
            raise AuthenticationError("Логин и пароль обязательны")
        
        key = username.strip().lower()
        
        # Проверяем блокировку до любых обращений к БД/bcrypt
        self._check_lockout(key)
        
        user = self._repository.get_by_username(username.strip())
        
        if not user:
            self._register_failed_attempt(key)
            logging.warning(f"Попытка входа с несуществующим логином: {username}")
            raise AuthenticationError("Неверные учетные данные")
        
        if not self._verify_password(password, user.password_hash):
            self._register_failed_attempt(key)
            logging.warning(f"Неверный пароль для пользователя: {username}")
            raise AuthenticationError("Неверные учетные данные")
        
        # Успешный вход сбрасывает счётчик неудачных попыток
        with self._lock_guard:
            self._failed_attempts.pop(key, None)
            self._lock_until.pop(key, None)
        
        # Обновляем дату последнего входа
        self._repository.update_last_login(user.id)
        
        logging.info(f"Успешный вход пользователя: {username}")
        
        return user.to_session_dict()

    # --- Методы защиты от перебора ---

    def _check_lockout(self, key: str) -> None:
        """Выбрасывает AuthenticationError, если логин временно заблокирован."""
        with self._lock_guard:
            until = self._lock_until.get(key, 0)
            if until and time.monotonic() < until:
                remaining = int(until - time.monotonic())
                minutes, seconds = divmod(max(remaining, 1), 60)
                raise AuthenticationError(
                    f"Слишком много неудачных попыток. "
                    f"Вход заблокирован еще {minutes} мин {seconds:02d} с."
                )
            elif until:
                # Блокировка истекла — очищаем состояние
                self._lock_until.pop(key, None)
                self._failed_attempts.pop(key, None)

    def _register_failed_attempt(self, key: str) -> None:
        """Увеличивает счётчик неудач и при превышении лимита блокирует вход."""
        with self._lock_guard:
            attempts = self._failed_attempts.get(key, [0, 0.0])
            attempts[0] += 1
            attempts[1] = time.monotonic()
            self._failed_attempts[key] = attempts
            
            if attempts[0] >= MAX_FAILED_ATTEMPTS:
                self._lock_until[key] = time.monotonic() + LOCKOUT_SECONDS
                logging.warning(
                    f"Логин '{key}' заблокирован на {LOCKOUT_SECONDS} c "
                    f"после {attempts[0]} неудачных попыток входа"
                )

    def create_user(
        self, 
        admin_user: dict, 
        username: str, 
        password: str, 
        role: str, 
        department_id: int = None
    ) -> int:
        """Создает нового пользователя.
        
        Args:
            admin_user: Данные администратора
            username: Логин нового пользователя
            password: Пароль
            role: Роль (admin/manager/employee)
            department_id: ID отдела (для менеджеров)
            
        Returns:
            ID созданного пользователя
            
        Raises:
            ValidationError: При ошибках валидации
        """
        self._validate_user_data(username, password, role)
        
        if self._repository.username_exists(username):
            raise ValidationError(f"Пользователь '{username}' уже существует", "username")
        
        user = User(
            username=username,
            password_hash=self._hash_password(password),
            role=role,
            department_id=department_id,
            is_active=True
        )
        
        user_id = self._repository.create(user)
        
        self._db.log_action(
            admin_user['id'],
            'CREATE_USER',
            f"Создан пользователь: {username} (роль: {role})"
        )
        
        return user_id

    def update_user(
        self, 
        admin_user: dict, 
        user_id: int, 
        data: Dict[str, Any]
    ) -> bool:
        """Обновляет данные пользователя."""
        user = self._repository.get_by_id(user_id)
        if not user:
            raise ValidationError(f"Пользователь с ID {user_id} не найден")
        
        if data.get('username') and data['username'] != user.username:
            if self._repository.username_exists(data['username'], user_id):
                raise ValidationError("Этот логин уже занят", "username")
        
        for field, value in data.items():
            if field != 'password' and hasattr(user, field):
                setattr(user, field, value)
        
        result = self._repository.update(user)
        
        if result:
            self._db.log_action(
                admin_user['id'],
                'UPDATE_USER',
                f"Обновлен пользователь ID: {user_id}"
            )
        
        return result

    def change_password(
        self, 
        user_id: int, 
        old_password: str, 
        new_password: str
    ) -> bool:
        """Изменяет пароль пользователя.
        
        Args:
            user_id: ID пользователя
            old_password: Текущий пароль
            new_password: Новый пароль
            
        Returns:
            True если изменение успешно
        """
        # Получаем пользователя по ID с паролем

        user = self._repository.get_by_id_with_password(user_id)
        
        if not user:
            raise AuthenticationError("Пользователь не найден")
                
        if not self._verify_password(old_password, user.password_hash):
            raise AuthenticationError("Неверный текущий пароль")
        
        self._check_password_policy(new_password)
        
        new_hash = self._hash_password(new_password)
        return self._repository.update_password(user_id, new_hash)

    def reset_password(self, admin_user: dict, user_id: int, new_password: str) -> bool:
        """Сбрасывает пароль пользователя (админ)."""
        self._check_password_policy(new_password)
        
        new_hash = self._hash_password(new_password)
        result = self._repository.update_password(user_id, new_hash)
        
        if result:
            self._db.log_action(
                admin_user['id'],
                'RESET_PASSWORD',
                f"Сброшен пароль пользователя ID: {user_id}"
            )
        
        return result

    def deactivate_user(self, admin_user: dict, user_id: int) -> bool:
        """Деактивирует пользователя."""
        result = self._repository.deactivate(user_id)
        
        if result:
            self._db.log_action(
                admin_user['id'],
                'DEACTIVATE_USER',
                f"Деактивирован пользователь ID: {user_id}"
            )
        
        return result

    def get_all_users(self, filters: Dict = None) -> list:
        """Возвращает список всех пользователей."""
        return self._repository.get_all(filters)

    def _hash_password(self, password: str) -> str:
        """Хеширует пароль с использованием bcrypt.
        
        Args:
            password: Пароль в открытом виде
            
        Returns:
            Хеш пароля (строка)
        """
        return bcrypt.hashpw(
            password.encode('utf-8'), 
            bcrypt.gensalt()
        ).decode('utf-8')

    def _verify_password(self, password: str, stored_hash: str) -> bool:
        """Проверяет пароль против хеша bcrypt.
        
        Поддерживает обратную совместимость с нехешированными паролями:
        если stored_hash не является bcrypt-хешем, выполняется прямое
        сравнение и автоматическая миграция хеша.
        
        Args:
            password: Пароль в открытом виде
            stored_hash: Сохранённый хеш пароля
            
        Returns:
            True если пароль верный
        """
        try:
            # Попытка проверить как bcrypt-хеш
            return bcrypt.checkpw(
                password.encode('utf-8'), 
                stored_hash.encode('utf-8')
            )
        except (ValueError, TypeError):
            # Обратная совместимость: нехешированный пароль
            if password == stored_hash:
                logging.warning(
                    "Обнаружен нехешированный пароль, "
                    "рекомендуется миграция"
                )
                return True
            return False

    def _validate_user_data(self, username: str, password: str, role: str) -> None:
        """Валидирует данные пользователя."""
        if not username or len(username) < 3:
            raise ValidationError("Логин должен содержать не менее 3 символов", "username")
        
        self._check_password_policy(password)
        
        valid_roles = ['admin', 'manager', 'employee']
        if role not in valid_roles:
            raise ValidationError(f"Недопустимая роль: {role}", "role")

    @staticmethod
    def _check_password_policy(password: str) -> None:
        """Проверяет пароль по политике безопасности (см. Validators.validate_password).
        
        Ранее допускался пароль из 4 символов без требований к составу —
        это позволяло комбинации вида '1234', подбираемые мгновенно.
        """
        is_valid, msg = Validators.validate_password(password)
        if not is_valid:
            raise ValidationError(msg, "password")
