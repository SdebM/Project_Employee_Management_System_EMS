"""Модель данных зарплаты.

Содержит dataclass :class:`Salary` для представления
записи о выплате зарплаты сотруднику.

Типы выплат:
    - ``salary``  — основная зарплата
    - ``bonus``   — премия
    - ``advance`` — аванс

Пример::

    from decimal import Decimal

    salary = Salary(
        employee_id=1,
        salary_amount=Decimal("50000.00"),
        payment_type="salary"
    )
    print(salary.formatted_amount)  # "50 000.00 ₽"
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
from decimal import Decimal


PAYMENT_TYPES = ('salary', 'bonus', 'advance')
"""Допустимые типы выплат."""


@dataclass
class Salary:
    """Модель зарплатной записи.

    Поля БД (таблица ``salaries``):
        salary_id, employee_id, salary_amount, effective_date,
        payment_type, description, created_at, updated_at

    Вспомогательные поля (не хранятся в БД):
        employee_name  — ФИО сотрудника (из JOIN)
        department_name — название отдела (из JOIN)
    """

    # --- поля таблицы ---
    salary_id: Optional[int] = None
    employee_id: int = 0
    salary_amount: Decimal = Decimal("0.00")
    effective_date: Optional[date] = None
    payment_type: str = "salary"
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # --- вспомогательные поля (JOIN) ---
    employee_name: Optional[str] = field(default=None, repr=False)
    department_name: Optional[str] = field(default=None, repr=False)

    
    def __post_init__(self) -> None:
        """Проверяет корректность полей после создания."""
        if self.salary_amount < 0:
            raise ValueError(
                f"salary_amount не может быть отрицательной: "
                f"{self.salary_amount}"
            )
        if self.payment_type not in PAYMENT_TYPES:
            raise ValueError(
                f"payment_type должен быть одним из {PAYMENT_TYPES}, "
                f"получено: '{self.payment_type}'"
            )

   
    @property
    def formatted_amount(self) -> str:
        """Возвращает сумму в формате ``'50 000.00 ₽'``."""
        return f"{self.salary_amount:,.2f} ₽".replace(",", " ")

    
    def to_dict(self) -> dict:
        """Конвертирует модель в словарь для сохранения в БД.

        Возвращает только поля таблицы ``salaries`` (без служебных
        ``created_at`` / ``updated_at`` и вспомогательных JOIN-полей).
        """
        return {
            'salary_id': self.salary_id,
            'employee_id': self.employee_id,
            'salary_amount': float(self.salary_amount),
            'effective_date': self.effective_date,
            'payment_type': self.payment_type,
            'description': self.description,
            'created_at': self.created_at,
            'updated_at': self.updated_at

        }

    @classmethod
    def from_db_row(cls, row: dict) -> 'Salary':
        """Создаёт экземпляр из строки БД (dict от RealDictCursor)."""
        amount_raw = row.get('salary_amount')
        return cls(
            salary_id=row.get('salary_id'),
            employee_id=row.get('employee_id', 0),
            salary_amount=Decimal(str(amount_raw)) if amount_raw else Decimal("0.00"),
            effective_date=row.get('effective_date'),
            payment_type=row.get('payment_type') or 'salary',
            description=row.get('description'),
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at'),
            # Вспомогательные поля (из JOIN)
            employee_name=row.get('employee_name'),
            department_name=row.get('department_name')
        )

    
    def __str__(self) -> str:
        """Краткое строковое представление."""
        type_map = {
            'salary': 'Зарплата',
            'bonus': 'Премия',
            'advance': 'Аванс',
        }
        label = type_map.get(self.payment_type, self.payment_type)
        return (
            f"Зарплата #{self.salary_id}: "
            f"{label} {self.formatted_amount} "
            f"(сотрудник {self.employee_id}, "
            f"дата {self.effective_date})"
        )
