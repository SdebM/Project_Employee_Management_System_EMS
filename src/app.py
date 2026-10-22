"""DI-контейнер приложения (Dependency Injection).

Этот модуль содержит класс :class:`Application`, который управляет
жизненным циклом всех компонентов приложения и предоставляет
единую точку доступа к сервисам и репозиториям.

Паттерны проектирования:
    - **Singleton** - единственный экземпляр Application
    - **Dependency Injection** - внедрение зависимостей через свойства
    - **Lazy Initialization** - ленивая инициализация компонентов

Пример использования:
    ::
    
        # Получение экземпляра
        app = Application.get_instance()
        app.initialize()
        
        # Использование сервисов
        employees = app.employee_service.get_employees(user)
        
        # Завершение работы
        app.shutdown()

См. также:
    - :mod:`core.config` - конфигурация
    - :mod:`core.database` - база данных
    - :mod:`services` - бизнес-логика
    - :mod:`repositories` - доступ к данным
"""

from typing import Optional
import logging
from datetime import datetime

from core.config import Config
from core.database import Database
from repositories import (
    EmployeeRepository,
    DepartmentRepository,
    ProjectRepository,
    SalaryRepository,
    UserRepository,
)
from services import (
    EmployeeService,
    DepartmentService,
    ProjectService,
    SalaryService,
    AuthService,
    AnalyticsService,
)


class Application:
    """Главный контейнер зависимостей приложения.
    
    Управляет жизненным циклом всех компонентов:
    
    - Конфигурация (:class:`core.config.Config`)
    - Подключение к БД (:class:`core.database.Database`)
    - Репозитории (слой доступа к данным)
    - Сервисы (слой бизнес-логики)
    
    Реализует паттерн **Singleton** - существует только один экземпляр.
    
    Attributes:
        _instance: Единственный экземпляр класса (class-level)
        _config: Объект конфигурации
        _db: Объект подключения к БД
    
    Example:
        Базовое использование::
        
            app = Application.get_instance()
            app.initialize()
            
            # Работа с сотрудниками
            employees = app.employee_service.get_employees(user, filters)
            
            # Завершение работы
            app.shutdown()
    
    Note:
        Все сервисы и репозитории создаются лениво при первом обращении.
    """
    
    _instance: Optional['Application'] = None

    def __init__(self) -> None:
        """Инициализирует пустой контейнер.
        
        Warning:
            Не вызывайте конструктор напрямую. 
            Используйте :meth:`get_instance`.
        """
        self._config: Optional[Config] = None
        self._db: Optional[Database] = None
        
        # Репозитории
        self._employee_repo: Optional[EmployeeRepository] = None
        self._department_repo: Optional[DepartmentRepository] = None
        self._project_repo: Optional[ProjectRepository] = None
        self._salary_repo: Optional[SalaryRepository] = None
        self._user_repo: Optional[UserRepository] = None
        
        # Сервисы
        self._employee_service: Optional[EmployeeService] = None
        self._department_service: Optional[DepartmentService] = None
        self._project_service: Optional[ProjectService] = None
        self._salary_service: Optional[SalaryService] = None
        self._auth_service: Optional[AuthService] = None
        self._analytics_service: Optional[AnalyticsService] = None

    @classmethod
    def get_instance(cls) -> 'Application':
        """Возвращает единственный экземпляр приложения."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        """Сбрасывает экземпляр (для тестов)."""
        if cls._instance:
            cls._instance.shutdown()
        cls._instance = None

    def initialize(self):
        """Инициализирует все компоненты приложения."""
        self._setup_logging()
        self._config = Config.get_instance()
        self._db = Database(self._config)
        logging.info("Приложение инициализировано")

    def shutdown(self):
        """Корректно завершает работу приложения."""
        if self._db and self._db.is_connected():
            self._db.close()
        logging.info("Приложение завершено")

    def _setup_logging(self):
        """Настраивает логирование."""
        logging.basicConfig(
            filename=f'app_errors_{datetime.now().strftime("%Y-%m-%d")}.log',
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    # === Properties для ленивой инициализации ===

    @property
    def config(self) -> Config:
        """Возвращает конфигурацию."""
        if not self._config:
            self._config = Config.get_instance()
        return self._config

    @property
    def db(self) -> Database:
        """Возвращает подключение к БД."""
        if not self._db:
            self._db = Database(self.config)
        return self._db

    # Репозитории
    @property
    def employee_repository(self) -> EmployeeRepository:
        if not self._employee_repo:
            self._employee_repo = EmployeeRepository(self.db)
        return self._employee_repo

    @property
    def department_repository(self) -> DepartmentRepository:
        if not self._department_repo:
            self._department_repo = DepartmentRepository(self.db)
        return self._department_repo

    @property
    def project_repository(self) -> ProjectRepository:
        if not self._project_repo:
            self._project_repo = ProjectRepository(self.db)
        return self._project_repo

    @property
    def salary_repository(self) -> SalaryRepository:
        if not self._salary_repo:
            self._salary_repo = SalaryRepository(self.db)
        return self._salary_repo

    @property
    def user_repository(self) -> UserRepository:
        if not self._user_repo:
            self._user_repo = UserRepository(self.db)
        return self._user_repo

    # Сервисы
    @property
    def employee_service(self) -> EmployeeService:
        if not self._employee_service:
            self._employee_service = EmployeeService(self.db)
        return self._employee_service

    @property
    def department_service(self) -> DepartmentService:
        if not self._department_service:
            self._department_service = DepartmentService(self.db)
        return self._department_service

    @property
    def project_service(self) -> ProjectService:
        if not self._project_service:
            self._project_service = ProjectService(self.db)
        return self._project_service

    @property
    def salary_service(self) -> SalaryService:
        if not self._salary_service:
            self._salary_service = SalaryService(self.db)
        return self._salary_service

    @property
    def auth_service(self) -> AuthService:
        if not self._auth_service:
            self._auth_service = AuthService(self.db)
        return self._auth_service

    @property
    def analytics_service(self) -> AnalyticsService:
        if not self._analytics_service:
            self._analytics_service = AnalyticsService(self.db)
        return self._analytics_service
