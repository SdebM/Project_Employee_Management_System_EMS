"""Репозиторий для работы с зарплатами."""

from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import date
from .base_repository import BaseRepository
from models.salaries import Salary
from core.database import Database


class SalaryRepository(BaseRepository[Salary]):
    """Репозиторий для CRUD-операций с зарплатными записями."""

    soft_delete_column = 'is_active'
    soft_delete_value = False
    active_value = True

    def __init__(self, db: Database):
        super().__init__(db, 'salaries')

    def _map_to_entity(self, row: tuple) -> Salary:
        """Преобразует строку БД в объект Salary."""
        return Salary.from_db_row(row)

    def _entity_to_params(self, entity: Salary) -> tuple:
        """Преобразует Salary в параметры SQL."""
        return (
            entity.employee_id,
            entity.salary_amount,
            entity.effective_date,
            entity.payment_type,
            entity.description
        )

    def get_all(self, filters: Optional[Dict[str, Any]] = None) -> List[Salary]:
        """Получает список зарплатных записей с фильтрацией.
        
        Args:
            filters: Фильтры поиска:
                - employee_id (int): Фильтр по сотруднику
                - employee_name (str): Поиск по ФИО (ILIKE)
                - payment_type (str): Тип выплаты
                - date_from (date): Начало периода
                - date_to (date): Конец периода
                
        Returns:
            Список объектов Salary
        """
        query = """
            SELECT 
                s.salary_id, s.employee_id, s.salary_amount,
                s.effective_date, s.payment_type, s.description,
                s.created_at,
                CONCAT(e.first_name, ' ', e.last_name) as employee_name,
                d.department_name
            FROM salaries s
            JOIN employees e ON s.employee_id = e.employee_id
            LEFT JOIN departments d ON e.department_id = d.department_id
            WHERE 1=1
        """
        params = []

        if filters:
            if filters.get('employee_id'):
                query += " AND s.employee_id = %s"
                params.append(filters['employee_id'])
            if filters.get('employee_name'):
                query += " AND (e.first_name ILIKE %s OR e.last_name ILIKE %s)"
                params.extend([f"%{filters['employee_name']}%"] * 2)
            if filters.get('payment_type'):
                query += " AND s.payment_type = %s"
                params.append(filters['payment_type'])
            if filters.get('date_from'):
                query += " AND s.effective_date >= %s"
                params.append(filters['date_from'])
            if filters.get('date_to'):
                query += " AND s.effective_date <= %s"
                params.append(filters['date_to'])

        query += " ORDER BY s.effective_date DESC"

        rows = self._db.fetch_all(query, tuple(params))
        salaries = []
        for row in rows:
            sal = Salary.from_db_row(row)
            sal.employee_name = row.get('employee_name')
            sal.department_name = row.get('department_name')
            salaries.append(sal)
        return salaries

    def get_by_id(self, salary_id: int) -> Optional[Salary]:
        """Получает запись о зарплате по ID."""
        query = """
            SELECT 
                s.salary_id, s.employee_id, s.salary_amount,
                s.effective_date, s.payment_type, s.description,
                s.created_at,
                CONCAT(e.first_name, ' ', e.last_name) as employee_name
            FROM salaries s
            JOIN employees e ON s.employee_id = e.employee_id
            WHERE s.salary_id = %s
        """
        row = self._db.fetch_one(query, (salary_id,))
        if row:
            sal = Salary.from_db_row(row)
            sal.employee_name = row.get('employee_name')
            return sal
        return None

    def create(self, salary: Salary) -> int:
        """Создает новую запись о зарплате."""
        query = """
            INSERT INTO salaries (
                employee_id, salary_amount, effective_date, 
                payment_type, description
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING salary_id
        """
        params = self._entity_to_params(salary)
        result = self._db.execute_query(query, params, return_result=True)
        # RealDictCursor возвращает список словарей: доступ по имени колонки
        return result[0]['salary_id'] if result else None

    def update(self, salary: Salary) -> bool:
        """Обновляет данные о зарплате."""
        query = """
            UPDATE salaries SET
                employee_id = %s, salary_amount = %s, effective_date = %s,
                payment_type = %s, description = %s
            WHERE salary_id = %s
        """
        params = self._entity_to_params(salary) + (salary.salary_id,)
        return self._db.execute_query(query, params)

    def delete(self, salary_id: int) -> bool:
        """Удаляет запись о зарплате."""
        query = "DELETE FROM salaries WHERE salary_id = %s"
        return self._db.execute_query(query, (salary_id,))

    def get_salary_dynamics(self, months: int = 12) -> List[tuple]:
        """Возвращает динамику выплат по месяцам.
        
        Args:
            months: Количество месяцев для анализа
            
        Returns:
            Список кортежей (month, total_amount)
        """
        query = """
            SELECT 
                DATE_TRUNC('month', effective_date) as month,
                SUM(salary_amount) as total
            FROM salaries
            WHERE effective_date >= date_trunc('month', NOW()) - (%s * INTERVAL '1 month')
            GROUP BY month
            ORDER BY month
        """
        rows = self._db.fetch_all(query, (months,))
        return [
            {
                'month': row['month'].strftime('%Y-%m') if row['month'] else '',
                'total': float(row['total']) if row['total'] else 0
            }
            for row in rows
        ]

    def get_average_by_department(self) -> List[tuple]:
        """Возвращает среднюю зарплату по отделам.
        
        Returns:
            Список кортежей (department_name, avg_salary)
        """
        query = """
            SELECT 
                d.department_name,
                AVG(s.salary_amount) as avg_salary
            FROM departments d
            JOIN employees e ON d.department_id = e.department_id
            JOIN salaries s ON e.employee_id = s.employee_id
            GROUP BY d.department_id, d.department_name
            ORDER BY avg_salary DESC
        """
        return self._db.fetch_all(query)

    def get_total_by_period(self, date_from: date, date_to: date) -> Decimal:
        """Возвращает общую сумму выплат за период.
        
        Args:
            date_from: Начало периода
            date_to: Конец периода
            
        Returns:
            Общая сумма выплат
        """
        query = """
            SELECT COALESCE(SUM(salary_amount), 0) AS total
            FROM salaries
            WHERE effective_date BETWEEN %s AND %s
        """
        result = self._db.fetch_one(query, (date_from, date_to))
        # RealDictRow — словарь: доступ по алиасу колонки
        return Decimal(str(result['total'])) if result else Decimal("0")
