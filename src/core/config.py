"""Конфигурация приложения.

Этот модуль содержит классы для управления конфигурацией:

- :class:`DatabaseConfig` - настройки подключения к PostgreSQL
- :class:`AppConfig` - общие настройки приложения
- :class:`Config` - главный класс конфигурации (Singleton)

Учётные данные БД читаются из окружения (переменные или файл ``.env``
в корне проекта — см. ``.env.example``). Пароль НЕ имеет значения
по умолчанию: захардкоженный пароль в репозитории — утечка секрета.

Переменные окружения:
    - ``DB_HOST`` - хост БД (по умолчанию: localhost)
    - ``DB_PORT`` - порт БД (по умолчанию: 5432)
    - ``DB_NAME`` - имя базы данных
    - ``DB_USER`` - пользователь БД
    - ``DB_PASSWORD`` - пароль БД (обязателен; без него запуск
      невозможен и приложение завершится с понятной ошибкой)
"""

import os
import logging
import sys
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv
load_dotenv()

@dataclass
class DatabaseConfig:
    """Настройки подключения к базе данных PostgreSQL.
    
    Attributes:
        dbname: Имя базы данных
        user: Имя пользователя
        password: Пароль
        host: Хост сервера
        port: Порт подключения
    
    Example:
        ::
        
            # Загрузка из переменных окружения
            config = DatabaseConfig.from_env()
            
            # Или явное создание
            config = DatabaseConfig(
                dbname='mydb',
                user='admin',
                password='secret'
            )
    """
    dbname: str = "empls_db"
    user: str = "postgres"
    # Пароль намеренно пуст: секреты не хранятся в коде.
    # Задайте его через переменную окружения DB_PASSWORD или файл .env.
    password: str = ""
    host: str = "localhost"
    port: str = "5432"

    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        """Загружает конфигурацию из переменных окружения.
        
        Использует переменные DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT.
        Если переменная не задана, используется значение по умолчанию.
        
        Returns:
            Новый экземпляр DatabaseConfig
        
        Raises:
            SystemExit: если DB_PASSWORD не задан — приложение не должно
                запускаться с пустым паролем БД.
        """
        password = os.getenv('DB_PASSWORD', '')
        if not password:
            logging.critical(
                "DB_PASSWORD не задан. Создайте файл .env по образцу "
                ".env.example или экспортируйте переменную окружения."
            )
            # Понятное сообщение в stderr вместо traceback psycopg2
            print(
                "Ошибка: не задан пароль БД.\n"
                "Создайте файл .env по образцу .env.example в корне проекта "
                "или задайте переменную окружения DB_PASSWORD.",
                file=sys.stderr
            )
            raise SystemExit(1)
        
        return cls(
            dbname=os.getenv('DB_NAME', cls.dbname),
            user=os.getenv('DB_USER', cls.user),
            password=password,
            host=os.getenv('DB_HOST', cls.host),
            port=os.getenv('DB_PORT', cls.port)
        )


@dataclass
class AppConfig:
    """Общие настройки приложения.
    
    Attributes:
        app_name: Название приложения
        version: Текущая версия
        debug: Режим отладки
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR)
        log_file_pattern: Шаблон имени файла логов
    """
    app_name: str = "Employee Systems"
    version: str = "1.01"
    debug: bool = False
    log_level: str = "INFO"
    log_file_pattern: str = "app_errors_{date}.log"


class Config:
    """Главный класс конфигурации приложения.
    
    Реализует паттерн Singleton для единой точки доступа к настройкам.
    """
    _instance: Optional['Config'] = None

    def __init__(self):
        self.database = DatabaseConfig.from_env()
        self.app = AppConfig()

    @classmethod
    def get_instance(cls) -> 'Config':
        """Возвращает единственный экземпляр конфигурации."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        """Сбрасывает экземпляр (для тестов)."""
        cls._instance = None
