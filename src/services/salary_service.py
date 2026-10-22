"""Сервис бизнес-логики для работы с зарплатами."""

from typing import List, Optional, Dict, Any
from datetime import date
from decimal import Decimal

from models.salaries import Salary
from repositories.salary_repository import SalaryRepository
from core.database import Database
from core.permissions import Permission, check_permission
from core.exceptions import ValidationError, EntityNotFoundError


class SalaryService:
    """Сервис для управления зарплатными записями."""

    def __init__(self, db: Database):
        self._db = db
        self._repository = SalaryRepository(db)

    def get_salaries(
        self, 
        user: dict, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Salary]:
        """Получает список зарплатных записей."""
        check_permission(user, Permission.VIEW_SALARIES)
        return self._repository.get_all(filters)

    def get_salary_by_id(self, user: dict, salary_id: int) -> Optional[Salary]:
        """Получает запись о зарплате по ID."""
        check_permission(user, Permission.VIEW_SALARIES)
        return self._repository.get_by_id(salary_id)

    def create_salary(self, user: dict, data: Dict[str, Any]) -> int:
        """Создает новую запись о зарплате.
        
        Принимает сумму в поле ``amount``; для обратной совместимости
        допускается также ``salary_amount`` (старое имя из UI-диалога).
        """
        check_permission(user, Permission.CREATE_SALARY)
        
        # Нормализация: оба варианта имени ключа сводятся к 'amount'
        if 'amount' not in data and 'salary_amount' in data:
            data['amount'] = data.pop('salary_amount')
        
        self._validate_salary_data(data)
        
        salary = Salary(
            employee_id=data['employee_id'],
            salary_amount=Decimal(str(data['amount'])),
            effective_date=data.get('effective_date', date.today()),
            payment_type=data.get('payment_type', 'salary'),
            description=data.get('description')
        )
        
        salary_id = self._repository.create(salary)
        
        self._db.log_action(
            user['id'],
            'CREATE_SALARY',
            f"Создана запись о зарплате ID: {salary_id}, сумма: {salary.formatted_amount}"
        )
        
        return salary_id

    def update_salary(
        self, 
        user: dict, 
        salary_id: int, 
        data: Dict[str, Any]
    ) -> bool:
        """Обновляет данные о зарплате."""
        check_permission(user, Permission.EDIT_SALARY)
        
        salary = self._repository.get_by_id(salary_id)
        if not salary:
            raise EntityNotFoundError("Запись о зарплате", salary_id)
        
        # Нормализация ключей суммы: UI может прислать 'amount' или
        # 'salary_amount' — атрибут модели называется salary_amount
        if 'amount' in data:
            data['salary_amount'] = data.pop('amount')
        if 'salary_amount' in data:
            data['salary_amount'] = Decimal(str(data['salary_amount']))
        
        self._validate_salary_data(data, is_update=True)
        
        for field, value in data.items():
            if hasattr(salary, field):
                setattr(salary, field, value)
        
        result = self._repository.update(salary)
        
        if result:
            self._db.log_action(
                user['id'],
                'UPDATE_SALARY',
                f"Обновлена запись о зарплате ID: {salary_id}"
            )
        
        return result

    def delete_salary(self, user: dict, salary_id: int) -> bool:
        """Удаляет запись о зарплате."""
        check_permission(user, Permission.DELETE_SALARY)
        
        salary = self._repository.get_by_id(salary_id)
        if not salary:
            raise EntityNotFoundError("Запись о зарплате", salary_id)
        
        result = self._repository.delete(salary_id)
        
        if result:
            self._db.log_action(
                user['id'],
                'DELETE_SALARY',
                f"Удалена запись о зарплате ID: {salary_id}"
            )
        
        return result

    def get_salary_dynamics(self, months: int = 12) -> List[tuple]:
        """Возвращает динамику выплат по месяцам."""
        return self._repository.get_salary_dynamics(months)

    def get_average_by_department(self) -> List[tuple]:
        """Возвращает среднюю зарплату по отделам."""
        return self._repository.get_average_by_department()

    def get_total_for_period(self, date_from: date, date_to: date) -> Decimal:
        """Возвращает общую сумму выплат за период."""
        return self._repository.get_total_by_period(date_from, date_to)

    def _validate_salary_data(self, data: dict, is_update: bool = False) -> None:
        """Валидирует данные о зарплате."""
        if not is_update:
            if not data.get('employee_id'):
                raise ValidationError("ID сотрудника обязателен", "employee_id")
            if not data.get('amount'):
                raise ValidationError("Сумма обязательна", "amount")
        
        # Проверяем сумму независимо от имени ключа ('amount' при создании,
        # 'salary_amount' после нормализации при обновлении)
        amount_raw = data.get('amount', data.get('salary_amount'))
        if amount_raw is not None:
            try:
                amount = Decimal(str(amount_raw))
                if amount <= 0:
                    raise ValidationError("Сумма должна быть положительной", "amount")
            except (ValueError, TypeError, ArithmeticError):
                raise ValidationError("Некорректный формат суммы", "amount")
        
        valid_types = ['salary', 'bonus', 'advance']
        if data.get('payment_type') and data['payment_type'] not in valid_types:
            raise ValidationError("Недопустимый тип выплаты", "payment_type")
