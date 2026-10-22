"""Репозиторий для работы с сотрудниками.

Содержит класс :class:`EmployeeRepository` для CRUD-операций
с таблицей employees.

Основные методы:
    - :meth:`get_all` - получение списка с фильтрацией
    - :meth:`get_by_id` - получение по ID
    - :meth:`create` - создание записи
    - :meth:`update` - обновление записи
    - :meth:`delete` - удаление записи
    - :meth:`search` - поиск по тексту


"""

from typing import List, Optional, Dict, Any
from .base_repository import BaseRepository
from models.employees import Employee
from core.database import Database


class EmployeeRepository(BaseRepository[Employee]):
    """Репозиторий для CRUD-операций с сотрудниками.

    Пример использования:
        repo = EmployeeRepository(db)
        employees = repo.get_all({'status': 'active'})
        employee = repo.get_by_id(1)
    """

    # Настройка Soft Delete для сотрудников
    soft_delete_column = 'status'
    soft_delete_value = 'fired'      # При "удалении" статус меняется на 'fired'
    active_value = 'active'          # По умолчанию ищем только 'active

    def __init__(self, db: Database):
        super().__init__(db, 'employees')

    def _map_to_entity(self, row: dict) -> Employee:
        """Преобразует строку БД в объект Employee."""
        return Employee.from_db_row(row)

    def _entity_to_params(self, entity: Employee) -> tuple:
        """Преобразует Employee в параметры SQL."""
        return (
            entity.first_name,
            entity.last_name,
            entity.date_of_birth,
            entity.gender,
            entity.hire_date,
            entity.department_id,
            entity.phone,
            entity.email,
            entity.inn,
            entity.snils,
            entity.passport,
            entity.status
        )

    def get_all(self, filters: Optional[Dict[str, Any]] = None) -> List[Employee]:
        """Получает список сотрудников с фильтрацией.
        
        Args:
            filters: Фильтры поиска:
                - first_name (str): Поиск по имени (ILIKE)
                - last_name (str): Поиск по фамилии (ILIKE)
                - department_id (int): Фильтр по отделу
                - status (str): Фильтр по статусу
                
        Returns:
            Список объектов Employee
        """
        query = """
            SELECT 
                e.employee_id, e.first_name, e.last_name, 
                e.date_of_birth, e.gender, e.hire_date,
                e.department_id, e.phone, e.email, 
                e.inn, e.snils, e.passport, e.status,
                e.created_at, e.updated_at,
                d.department_name
            FROM employees e
            LEFT JOIN departments d ON e.department_id = d.department_id
            WHERE 1=1
        """
        params = []

        if filters:
            if filters.get('first_name'):
                query += " AND e.first_name ILIKE %s"
                params.append(f"%{filters['first_name']}%")
            if filters.get('last_name'):
                query += " AND e.last_name ILIKE %s"
                params.append(f"%{filters['last_name']}%")
            if filters.get('department_id'):
                query += " AND e.department_id = %s"
                params.append(filters['department_id'])
            if filters.get('status'):
                query += " AND e.status = %s"
                params.append(filters['status'])

        query += " ORDER BY e.last_name, e.first_name"

        rows = self._db.fetch_all(query, tuple(params))

        return [self._map_to_entity(row) for row in rows]



    def get_by_id(self, employee_id: int) -> Optional[Employee]:
        """Получает сотрудника по ID с полной информацией."""
        query = """
            SELECT 
                e.employee_id, e.first_name, e.last_name,                 e.date_of_birth, e.gender, e.hire_date,
                e.department_id, e.phone, e.email, 
                e.inn, e.snils, e.passport, e.status,
                e.created_at, e.updated_at,
                d.department_name
            FROM employees e
            LEFT JOIN departments d ON e.department_id = d.department_id
            WHERE e.employee_id = %s
        """
        row = self._db.fetch_one(query, (employee_id,))
        return self._map_to_entity(row) if row else None

    def create(self, employee: Employee) -> int:
        """Создает нового сотрудника.
        
        Args:
            employee: Объект Employee для создания
            
        Returns:
            ID созданного сотрудника
        """
        query = """
            INSERT INTO employees (
                first_name, last_name, date_of_birth, gender, 
                hire_date, department_id, phone, email, 
                inn, snils, passport, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING employee_id
        """
        params = self._entity_to_params(employee)
        result = self._db.execute_query(query, params, return_result=True)
        # RealDictCursor возвращает список словарей: доступ по имени колонки
        return result[0]['employee_id'] if result else None

    def update(self, employee: Employee) -> bool:
        """Обновляет данные сотрудника.
        
        Args:
            employee: Объект Employee с обновленными данными
            
        Returns:
            True если обновление успешно
        """
        query = """
            UPDATE employees SET
                first_name = %s, last_name = %s, date_of_birth = %s,
                gender = %s, hire_date = %s, department_id = %s,
                phone = %s, email = %s, inn = %s, snils = %s, passport = %s,
                status = %s, updated_at = NOW()
            WHERE employee_id = %s
        """
        params = self._entity_to_params(employee) + (employee.employee_id,)
        return self._db.execute_query(query, params)

    def delete(self, employee_id: int) -> bool:
        """Мягко "удаляет" сотрудника — фактически помечает уволенным.
        
        Важно: НЕ выполняет физический DELETE. Жёсткое удаление строки
        employees каскадно стирало бы всю зарплатную историю сотрудника
        (salaries.employee_id ON DELETE CASCADE) и обнуляло бы ссылки
        руководителей отделов. Вместо этого статус меняется на 'fired',
        а история выплат сохраняется для отчётности.
        
        Args:
            employee_id: ID сотрудника для увольнения
            
        Returns:
            True если увольнение выполнено успешно
        """
        query = """
            UPDATE employees
            SET status = 'fired', updated_at = NOW()
            WHERE employee_id = %s
        """
        return self._db.execute_query(query, (employee_id,))

    def get_by_department(self, department_id: int) -> List[Employee]:
        """Получает сотрудников указанного отдела.
        
        Args:
            department_id: ID отдела
            
        Returns:
            Список сотрудников отдела
        """
        return self.get_all({'department_id': department_id})

    def count_by_department(self) -> List[tuple]:
        """Возвращает количество сотрудников по отделам.
        
        Returns:
            Список кортежей (department_name, count)
        """
        query = """
            SELECT d.department_name, COUNT(e.employee_id) as employee_count
            FROM departments d
            LEFT JOIN employees e ON d.department_id = e.department_id
            GROUP BY d.department_id, d.department_name
            ORDER BY d.department_name
        """
        rows = self._db.fetch_all(query)
        # RealDictCursor возвращает словари — приводим к кортежам
        # (department_name, count) согласно контракту метода
        return [
            (row['department_name'], row['employee_count'])
            for row in rows
        ]
