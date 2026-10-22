"""Модуль работы с базой данных PostgreSQL.

Содержит класс :class:`Database` для управления соединением с PostgreSQL
и выполнения SQL-запросов с поддержкой транзакций.

Основные возможности:
    - Установка соединения с PostgreSQL
    - Выполнение запросов с параметрами
    - Управление транзакциями (commit/rollback)
    - Context manager для безопасной работы
    - Логирование действий в аудит-таблицу

"""

from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from psycopg2 import Error as Psycopg2Error
import logging
from typing import Optional, List, Tuple, Any
from contextlib import contextmanager
import threading

from .config import Config
from .exceptions import DatabaseError

class Database:
    """Управление пулом подключений к базе данных PostgreSQL.

    Использует ThreadedConnectionPool для безопасной работы 
    в многопоточной среде (например, при использовании QThread).
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.get_instance()
        self._pool: Optional[ThreadedConnectionPool] = None
        # Хранилище для транзакций: привязывает соединение к конкретному потоку
        self._local = threading.local() 
        self._connect()

    def _connect(self):
        """Инициализирует пул соединений."""
        try:
            db_config = self.config.database
            # ИЗМЕНЕНИЕ: Создаем пул вместо одиночного подключения
            # minconn=1 - минимум 1 соединение всегда открыто
            # maxconn=10 - максимум 10 одновременных соединений
            self._pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                dbname=db_config.dbname,
                user=db_config.user,
                password=db_config.password,
                host=db_config.host,
                port=db_config.port
            )
            logging.info("Пул подключений к БД инициализирован.")
        except Psycopg2Error as e:
            logging.critical(f"Не удалось создать пул подключений: {str(e)}")
            raise DatabaseError("Не удалось установить соединение с базой данных", str(e))
        except Exception as e:
            logging.critical(f"Ошибка инициализации БД: {str(e)}")
            raise DatabaseError("Ошибка инициализации подключения", str(e))

    def _get_current_conn(self):
        """Возвращает соединение для текущего потока.
        
        Если мы находимся внутри блока `with db.transaction():`,
        возвращается закрепленное за транзакцией соединение.
        Иначе берется новое соединение из пула.
        """
        if hasattr(self._local, 'conn') and self._local.conn is not None:
            return self._local.conn
        return self._pool.getconn()

    def _return_conn(self, conn):
        """Возвращает соединение в пул.
        
        Если это соединение активной транзакции, не возвращаем его,
        пока транзакция не завершится.
        """
        if hasattr(self._local, 'conn') and self._local.conn is conn:
            return # Соединение управляется блоком transaction()
        self._pool.putconn(conn)

    def log_action(self, user_id: int, action_type: str, details: str = "") -> None:
        """Логирует действие пользователя в аудит-таблицу."""
        query = """
            INSERT INTO audit_log (user_id, action_type, details)
            VALUES (%s, %s, %s)
        """
        try:
            self.execute_query(query, (user_id, action_type, details))
        except Exception as e:
            logging.error(f"Audit log error: {str(e)}")

    def execute_query(
        self, 
        query: str, 
        params: Optional[Tuple] = None, 
        return_result: bool = False
    ) -> Any:
        """Выполняет SQL-запрос."""
        conn = self._get_current_conn()
        try:
            # ИЗМЕНЕНИЕ: Курсор создается локально на каждое действие
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params or ())
                
                if return_result or "RETURNING" in query.upper():
                    try:
                        result = cursor.fetchall()
                        # Коммитим только если мы НЕ внутри транзакции
                        if not (hasattr(self._local, 'conn') and self._local.conn is conn):
                            conn.commit()
                        return result
                    except Psycopg2Error.ProgrammingError:
                        if not (hasattr(self._local, 'conn') and self._local.conn is conn):
                            conn.commit()
                        return True
                
                if not (hasattr(self._local, 'conn') and self._local.conn is conn):
                    conn.commit()
                return True

        except Psycopg2Error as e:
            conn.rollback()
            logging.error(f"Database error: {str(e)}")
            raise DatabaseError(f"Ошибка выполнения запроса: {str(e)}")
        except Exception as e:
            conn.rollback()
            logging.error(f"Unexpected error: {str(e)}")
            raise
        finally:
            self._return_conn(conn)

    def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[dict]:
        """Выполняет SELECT-запрос и возвращает все результаты."""
        conn = self._get_current_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params or ())
                return cursor.fetchall()
        except Psycopg2Error as e:
            conn.rollback()
            logging.error(f"Ошибка запроса: {str(e)}")
            raise DatabaseError(f"Ошибка выполнения запроса: {str(e)}")
        finally:
            self._return_conn(conn)
        
    def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[dict]:
        """Выполняет SELECT-запрос и возвращает одну строку."""
        conn = self._get_current_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params or ())
                return cursor.fetchone()
        except Psycopg2Error as e:
            conn.rollback()
            logging.error(f"Ошибка запроса: {str(e)}")
            raise DatabaseError(f"Ошибка выполнения запроса: {str(e)}")
        finally:
            self._return_conn(conn)
        
    @contextmanager
    def transaction(self):
        """Контекстный менеджер для транзакций.
        
        Берет одно соединение из пула и закрепляет его за текущим потоком
        до завершения блока with. Все методы внутри блока будут использовать
        это соединение.
        """
        # Если мы уже внутри транзакции в этом потоке, просто идем глубже
        if hasattr(self._local, 'conn') and self._local.conn is not None:
            yield
            return

        conn = self._pool.getconn()
        self._local.conn = conn  # Привязываем соединение к потоку
        try:
            yield
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._local.conn = None # Отвязываем соединение
            self._pool.putconn(conn) # Возвращаем в пул

    def is_connected(self) -> bool:
        """Проверяет активность пула."""
        try:
            return self._pool is not None and not self._pool.closed
        except Exception:
            return False
        
    def close(self) -> None:
        """Корректно закрывает все соединения в пуле."""
        try:
            if self._pool:
                self._pool.closeall()
            logging.info("Пул соединений с базой данных закрыт.")
        except Exception as e:
            logging.error(f"Ошибка закрытия пула: {str(e)}")


# =====================================================================================================
# Singelton pattern for Database instance
# _____________________________________________________________________________________________________
# import psycopg2
# from psycopg2.extras import RealDictCursor
# import logging
# from typing import Optional, List, Tuple, Any
# from contextlib import contextmanager

# from .config import Config
# from .exceptions import DatabaseError



# class Database:
#     """Управление подключением и операциями с базой данных PostgreSQL.

#     Обеспечивает основные операции работы с базой данных:
#     - Установка и закрытие соединения
#     - Выполнение SQL-запросов с транзакциями
#     - Логирование действий в аудит-таблицу
#     - Обработка ошибок и восстановление

#     Attributes:
#         conn (psycopg2.connection): Объект соединения с БД
#         cursor (psycopg2.cursor): Курсор для выполнения запросов
#     """

#     def __init__(self, config: Optional[Config] = None):
#         """Инициализирует подключение к базе данных.

#         Args:
#             config: Объект конфигурации (опционально)

#         Raises:
#             DatabaseError: Ошибка подключения к серверу БД
#         """
#         self.config = config or Config.get_instance()
#         self.conn = None
#         self.cursor = None
#         self._in_transaction = False
#         self._connect()


#     def _connect(self):
#             """Устанавливает соединение с БД."""
#             try:
#                 db_config = self.config.database
#                 self.conn = psycopg2.connect(
#                     dbname=db_config.dbname,
#                     user=db_config.user,
#                     password=db_config.password,
#                     host=db_config.host,
#                     port=db_config.port
#                 )
#             #     self.cursor = self.conn.cursor()
#             #     logging.info("Установлено соединение с базой данных.")
#             # except psycopg2.OperationalError as e:
#             #     logging.critical(f"Не удалось подключиться к БД: {str(e)}")
#             #     raise DatabaseError("Не удалось установить соединение с базой данных", str(e))
#             # except Exception as e:
#             #     logging.critical(f"Ошибка инициализации БД: {str(e)}")
#             #     raise DatabaseError("Ошибка инициализации подключения", str(e))
#                 self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
#                 logging.info("Установлено соединение с базой данных.")
#             except psycopg2.OperationalError as e:
#                 logging.critical(f"Не удалось подключиться к БД: {str(e)}")
#                 raise DatabaseError("Не удалось установить соединение с базой данных", str(e))
#             except Exception as e:
#                 logging.critical(f"Ошибка инициализации БД: {str(e)}")
#                 raise DatabaseError("Ошибка инициализации подключения", str(e))


#     def log_action(self, user_id: int, action_type: str, details: str = "") -> None:
#             """Логирует действие пользователя в аудит-таблицу.

#             Args:
#                 user_id: Идентификатор пользователя
#                 action_type: Тип действия (например 'ADD_EMPLOYEE')
#                 details: Дополнительная информация о действии
#             """
#             query = """
#                 INSERT INTO audit_log (user_id, action_type, details)
#                 VALUES (%s, %s, %s)
#             """
#             try:
#                 self.execute_query(query, (user_id, action_type, details))
#             except Exception as e:
#                 logging.error(f"Audit log error: {str(e)}")

#     def execute_query(
#             self, 
#             query: str, 
#             params: Optional[Tuple] = None, 
#             return_result: bool = False
#         ) -> Any:
#             """Выполняет SQL-запрос с обработкой транзакций.

#             Args:
#                 query: SQL-запрос для выполнения
#                 params: Параметры для запроса
#                 return_result: Флаг возврата результатов

#             Returns:
#                 Результаты запроса при return_result=True, иначе True при успехе

#             Raises:
#                 DatabaseError: Ошибки выполнения SQL-запроса
#             """
#             try:
#                 self.cursor.execute(query, params or ())
                
#                 if return_result or "RETURNING" in query.upper():
#                     try:
#                         result = self.cursor.fetchall()
#                         if not self._in_transaction:
#                             self.conn.commit()
#                         return result
#                     except psycopg2.ProgrammingError:
#                         if not self._in_transaction:
#                             self.conn.commit()
#                         return True
                
#                 if not self._in_transaction:
#                     self.conn.commit()
#                 return True
                
#             except psycopg2.Error as e:
#                 self.conn.rollback()
#                 logging.error(f"Database error: {str(e)}")
#                 raise DatabaseError(f"Ошибка выполнения запроса: {str(e)}")
#             except Exception as e:
#                 self.conn.rollback()
#                 logging.error(f"Unexpected error: {str(e)}")
#                 raise

#     def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[dict]:
#         """Выполняет SELECT-запрос и возвращает все результаты.

#         Args:
#             query: SQL SELECT-запрос
#             params: Параметры запроса

#         Returns:
#             Список кортежей с результатами запроса
#         """
#         try:
#             self.cursor.execute(query, params or ())
#             return self.cursor.fetchall()
#         except psycopg2.Error as e:
#             self.conn.rollback()
#             logging.error(f"Ошибка запроса: {str(e)}")
#             raise DatabaseError(f"Ошибка выполнения запроса: {str(e)}")
        
#     def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[dict]:
#         """Выполняет SELECT-запрос и возвращает одну строку.

#         Args:
#             query: SQL SELECT-запрос
#             params: Параметры запроса

#         Returns:
#             Кортеж с результатом или None
#         """
#         try:
#             self.cursor.execute(query, params or ())
#             return self.cursor.fetchone()
#         except psycopg2.Error as e:
#             self.conn.rollback()
#             logging.error(f"Ошибка запроса: {str(e)}")
#             raise DatabaseError(f"Ошибка выполнения запроса: {str(e)}")
        
#     @contextmanager
#     def transaction(self):
#         """Контекстный менеджер для транзакций.
        
#         Пример:
#             with db.transaction():
#                 db.execute_query(...)
#                 db.execute_query(...)
#         """
#         self._in_transaction = True
#         try:
#             yield
#             self.conn.commit()
#         except Exception:
#             self.conn.rollback()
#             raise
#         finally:
#             self._in_transaction = False

#     def is_connected(self) -> bool:
#         """Проверяет активность соединения с БД.

#         Returns:
#             True если соединение активно, иначе False
#         """
#         try:
#             return self.conn is not None and not self.conn.closed
#         except Exception:
#             return False
        
#     def reconnect(self) -> None:
#         """Переподключается к БД при разрыве соединения."""
#         if not self.is_connected():
#             self._connect()

#     def close(self) -> None:
#         """Корректно закрывает соединение с базой данных."""
#         try:
#             if self.cursor:
#                 self.cursor.close()
#             if self.conn:
#                 self.conn.close()
#             logging.info("Соединение с базой данных закрыто.")
#         except Exception as e:
#             logging.error(f"Ошибка закрытия соединения: {str(e)}")

#     def __enter__(self):
#         """Поддержка контекстного менеджера."""
#         return self
    
#     def __exit__(self, exc_type, exc_val, exc_tb):
#         """Закрывает соединение при выходе из контекста."""
#         self.close()
