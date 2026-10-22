"""Репозиторий для работы с отделами."""

from typing import List, Optional, Dict, Any
from .base_repository import BaseRepository
from models.departments import Department
from core.database import Database


class DepartmentRepository(BaseRepository[Department]):
    """Репозиторий для CRUD-операций с отделами."""

    soft_delete_column = 'is_active'
    soft_delete_value = False
    active_value = True

    def __init__(self, db: Database):
        super().__init__(db, 'departments')

    def _map_to_entity(self, row: tuple) -> Department:
        """Преобразует строку БД в объект Department."""
        return Department.from_db_row(row)

    def _entity_to_params(self, entity: Department) -> tuple:
        """Преобразует Department в параметры SQL."""
        return (
            entity.department_name,
            entity.description,
            entity.manager_id
        )

    def get_all(self, filters: Optional[Dict[str, Any]] = None) -> List[Department]:
        """Получает список отделов с информацией о количестве сотрудников.
        
        Args:
            filters: Фильтры поиска:
                - department_name (str): Поиск по названию (ILIKE)
                
        Returns:
            Список объектов Department
        """
        query = """
            SELECT 
                d.department_id, d.department_name, d.description,
                d.manager_id, d.created_at, d.updated_at,
                CONCAT(e.first_name, ' ', e.last_name) as manager_name,
                (SELECT COUNT(*) FROM employees WHERE department_id = d.department_id) as emp_count
            FROM departments d
            LEFT JOIN employees e ON d.manager_id = e.employee_id
            WHERE 1=1
        """
        params = []

        if filters:
            if filters.get('department_name'):
                query += " AND d.department_name ILIKE %s"
                params.append(f"%{filters['department_name']}%")

        query += " ORDER BY d.department_name"

        rows = self._db.fetch_all(query, tuple(params))
        departments = []
        for row in rows:
            dept = Department.from_db_row(row)
            dept.manager_name = row.get('manager_name')
            dept.employee_count = row.get('emp_count', 0) or 0
            departments.append(dept)
        return departments

    def get_by_id(self, department_id: int) -> Optional[Department]:
        """Получает отдел по ID вместе со счётчиками сотрудников и проектов.
        
        Счётчики нужны сервису для безопасного удаления отдела:
        employee_count считает только активных сотрудников, project_count —
        связанные проекты (которые иначе каскадно удалятся вместе с отделом).
        """
        query = """
            SELECT 
                d.department_id, d.department_name, d.description,
                d.manager_id, d.created_at, d.updated_at,
                CONCAT(e.first_name, ' ', e.last_name) as manager_name,
                (SELECT COUNT(*) FROM employees 
                    WHERE department_id = d.department_id 
                    AND status = 'active') as employee_count,
                (SELECT COUNT(*) FROM projects 
                    WHERE department_id = d.department_id) as project_count
            FROM departments d
            LEFT JOIN employees e ON d.manager_id = e.employee_id
            WHERE d.department_id = %s
        """
        row = self._db.fetch_one(query, (department_id,))
        if row:
            dept = Department.from_db_row(row)
            dept.manager_name = row.get('manager_name')
            dept.employee_count = row.get('employee_count', 0) or 0
            dept.project_count = row.get('project_count', 0) or 0
            return dept
        return None

    def create(self, department: Department) -> int:
        """Создает новый отдел.
        
        Returns:
            ID созданного отдела
        """
        query = """
            INSERT INTO departments (department_name, description, manager_id)
            VALUES (%s, %s, %s)
            RETURNING department_id
        """
        params = self._entity_to_params(department)
        result = self._db.execute_query(query, params, return_result=True)
        # RealDictCursor возвращает список словарей: доступ по имени колонки
        return result[0]['department_id'] if result else None

    def update(self, department: Department) -> bool:
        """Обновляет данные отдела."""
        query = """
            UPDATE departments SET
                department_name = %s, description = %s,
                manager_id = %s, updated_at = NOW()
            WHERE department_id = %s
        """
        params = self._entity_to_params(department) + (department.department_id,)
        return self._db.execute_query(query, params)

    def delete(self, department_id: int) -> bool:
        """Удаляет отдел."""
        query = "DELETE FROM departments WHERE department_id = %s"
        return self._db.execute_query(query, (department_id,))

    def get_for_dropdown(self) -> List[tuple]:
        """Возвращает список отделов для выпадающего списка.
        
        Returns:
            Список кортежей (department_id, department_name).
            fetch_all() с RealDictCursor возвращает словари, поэтому
            здесь выполняется явное преобразование к кортежам — иначе
            распаковка ``for d_id, d_name in rows`` в UI вернула бы
            имена колонок вместо значений.
        """
        query = """
            SELECT department_id, department_name 
            FROM departments 
            ORDER BY department_name
        """
        rows = self._db.fetch_all(query)
        return [
            (row['department_id'], row['department_name'])
            for row in rows
        ]

    def get_department_statistics(self) -> List[Dict]:
        """Возвращает статистику по отделам.
        
        Returns:
            Список словарей со статистикой
        """
        query = """
            SELECT 
                d.department_name,
                COUNT(e.employee_id) as employee_count,
                COALESCE(SUM(s.salary_amount), 0) as total_salary
            FROM departments d
            LEFT JOIN employees e ON d.department_id = e.department_id
            LEFT JOIN salaries s ON e.employee_id = s.employee_id
            GROUP BY d.department_id, d.department_name
            ORDER BY d.department_name
        """
        rows = self._db.fetch_all(query)
        return [
            {
                'department_name': row['department_name'],
                'employee_count': row['employee_count'],
                'total_salary': float(row['total_salary']) if row['total_salary'] else 0
            }
            for row in rows
        ]
