"""Модель данных сотрудника.

Содержит dataclass :class:`Employee` для представления
данных сотрудника в приложении.

Основные возможности:
    - Создание из строки БД: :meth:`Employee.from_db_row`
    - Конвертация в словарь: :meth:`Employee.to_dict`
    - Вычисляемые свойства: ``full_name``, ``age``
    - Валидация полей при создании: ``__post_init__``

Порядок столбцов в БД (таблица employees):
    employee_id, first_name, last_name, date_of_birth, gender,
    hire_date, department_id, phone, email, inn, snils, passport,
    status, created_at, updated_at

Пример:
    ::

        employee = Employee(
            first_name="Иван",
            last_name="Петров",
            date_of_birth=date(1990, 5, 15),
            hire_date=date.today()
        )
        print(employee.full_name)  # "Иван Петров"
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

VALID_GENDERS = ('М', 'Ж')
VALID_STATUSES = ('active', 'inactive', 'fired')

@dataclass
class Employee:
    """Модель сотрудника.

    Attributes:
        employee_id: Уникальный идентификатор сотрудника
        first_name: Имя
        last_name: Фамилия
        date_of_birth: Дата рождения
        gender: Пол ('М' или 'Ж')
        hire_date: Дата приема на работу
        department_id: ID отдела (опционально)
        phone: Телефон (опционально)
        email: Email (опционально)
        inn: ИНН (опционально, конфиденциально)
        snils: СНИЛС (опционально, конфиденциально)
        passport: Паспортные данные (опционально, конфиденциально)
        status: Статус ('active', 'inactive', 'fired')
        created_at: Дата создания записи
        updated_at: Дата последнего обновления
    """
    # --- Обязательные поля (NOT NULL в БД) ---
    employee_id: Optional[int] = None  # None до сохранения в БД
    first_name: str = ""
    last_name: str = ""
    date_of_birth: Optional[date] = None  # NOT NULL — Optional только до заполнения
    gender: str = "М"
    hire_date: Optional[date] = None  # NOT NULL — Optional только до заполнения

    # --- Опциональные поля ---
    department_id: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    inn: Optional[str] = None
    snils: Optional[str] = None
    passport: Optional[str] = None
    status: str = "active"

    # --- Служебные поля (генерируются БД) ---
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Дополнительные поля для отображения (не хранятся в БД)
    department_name: Optional[str] = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        """Валидация и нормализация полей после инициализации."""
        self._validate_choice('gender', self.gender, VALID_GENDERS)
        self._validate_choice('status', self.status, VALID_STATUSES)

        # Нормализация строковых полей
        self.first_name = self.first_name.strip() if self.first_name else ""
        self.last_name = self.last_name.strip() if self.last_name else ""

        if not self.first_name or not self.last_name:
            raise ValueError("Имя и фамилия обязательны")

    @staticmethod
    def _validate_choice(field_name: str, value: str, valid_values: tuple) -> None:
        """Проверяет, что значение входит в набор допустимых.

        Args:
            field_name: Название поля (для сообщения об ошибке).
            value: Проверяемое значение.
            valid_values: Кортеж допустимых значений.

        Raises:
            ValueError: Если значение не входит в допустимые.
        """
        if value not in valid_values:
            raise ValueError(
                f"Недопустимое значение поля '{field_name}': '{value}'. "
                f"Допустимые значения: {valid_values}"
            )

    @property
    def full_name(self) -> str:
        """Возвращает полное имя сотрудника."""
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self) -> Optional[int]:
        """Вычисляет возраст сотрудника."""
        if not self.date_of_birth:
            return None
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    def to_dict(self) -> dict:
        """Конвертирует модель в словарь для сохранения."""
        return {
            'employee_id': self.employee_id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'date_of_birth': self.date_of_birth,
            'gender': self.gender,
            'hire_date': self.hire_date,
            'department_id': self.department_id,
            'phone': self.phone,
            'email': self.email,
            'inn': self.inn,
            'snils': self.snils,
            'passport': self.passport,
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def to_safe_dict(self) -> dict:
        """Словарь без конфиденциальных данных."""
        d = self.to_dict()
        for key in ('inn', 'snils', 'passport'):
            d.pop(key, None)
        return d

    def __str__(self) -> str:
        """Строковое представление сотрудника."""
        status_map = {'active': 'Активен', 'inactive': 'Неактивен', 'fired': 'Уволен'}
        parts = [f"[{self.employee_id or '—'}] {self.full_name}"]
        if self.department_name:
            parts.append(f"отдел: {self.department_name}")
        parts.append(f"статус: {status_map.get(self.status, self.status)}")
        return ' | '.join(parts)

    @classmethod
    def from_db_row(cls, row: dict) -> 'Employee':
        """Создает экземпляр из строки БД.
        
        """
        return cls(
            employee_id=row.get('employee_id'),
            first_name=row.get('first_name', ''),
            last_name=row.get('last_name', ''),
            date_of_birth=row.get('date_of_birth'),
            gender=row.get('gender', 'М'),
            hire_date=row.get('hire_date'),
            department_id=row.get('department_id'),
            phone=row.get('phone'),
            email=row.get('email'),
            inn=row.get('inn'),
            snils=row.get('snils'),
            passport=row.get('passport'),
            status=row.get('status', 'active'),
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at'),
            department_name=row.get('department_name') # Для JOIN полей
        )
        