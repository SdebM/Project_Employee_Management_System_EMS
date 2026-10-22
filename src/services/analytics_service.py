"""Сервис аналитики и построения графиков."""

from typing import Any, Dict, List

from core.database import Database
from core.permissions import Permission, check_permission


class AnalyticsService:
    """Сервис для аналитики и визуализации данных.
    
    Предоставляет данные для построения графиков:
    - Распределение сотрудников по отделам
    - Динамика зарплат
    - Статистика проектов
    - Средние показатели
    """

    def __init__(self, db: Database):
        self._db = db

    def get_employee_department(self, user:dict) -> List[Dict[str, Any]]:
        """Возвращает количество сотрудников по отделам.
        
        Args:
            user: Данные текущего пользователя
            
        Returns:
            Список словарей {department_name, count}
        """
        check_permission(user, Permission.VIEW_ANALYTICS)

        query = """
            SELECT d.department_name, COUNT(e.employee_id) as count
            FROM departments d
            LEFT JOIN employees e ON d.department_id = e.department_id
            GROUP BY d.department_id, d.department_name
            ORDER BY count DESC
        """

        rows = self._db.fetch_all(query)
        return [
            {'department_name': row['department_name'], 'count': row['count']}
            for row in rows
        ]
    
    def get_salary_dynamics(self, user:dict, months:int = 12) -> List[Dict[str, Any]]:
        """Возвращает динамику выплат по месяцам.
        
        Args:
            user: Данные текущего пользователя
            months: Количество месяцев для анализа
            
        Returns:
            Список словарей {month, total}
        """
        check_permission(user, Permission.VIEW_ANALYTICS)

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
    
    def get_projects_by_status(self, user: dict) -> List[Dict[str, Any]]:
        """Возвращает распределение проектов по статусам.
        
        Returns:
            Список словарей {status, count}
        """
        check_permission(user, Permission.VIEW_ANALYTICS)
        
        query = """
            SELECT status, COUNT(*) as count
            FROM projects
            GROUP BY status
            ORDER BY count DESC
        """
        
        rows = self._db.fetch_all(query)
        
        # Маппинг статусов на русские названия
        status_names = {
            'planning': 'Планирование',
            'in_progress': 'В работе',
            'on_hold': 'Приостановлен',
            'completed': 'Завершен',
            'cancelled': 'Отменен'
        }
        
        return [
            {
                'status': status_names.get(row['status'], row['status']),
                'count': row['count']
            }
            for row in rows
        ]

    def get_average_salary_by_department(self, user: dict) -> List[Dict[str, Any]]:
        """Возвращает среднюю зарплату по отделам.
        
        Returns:
            Список словарей {department_name, avg_salary}
        """
        check_permission(user, Permission.VIEW_ANALYTICS)
        
        query = """
            WITH latest_salaries AS (
                SELECT 
                    s.employee_id,
                    s.salary_amount,
                    ROW_NUMBER() OVER (
                        PARTITION BY s.employee_id
                        ORDER BY s.effective_date DESC
                    ) AS rn
                FROM salaries s
                WHERE s.payment_type = 'salary'
            )
            SELECT 
                d.department_name,
                COALESCE(AVG(ls.salary_amount), 0) as avg_salary
            FROM departments d
            LEFT JOIN employees e ON d.department_id = e.department_id
            LEFT JOIN latest_salaries ls 
                ON e.employee_id = ls.employee_id AND ls.rn = 1
            GROUP BY d.department_id, d.department_name
            ORDER BY avg_salary DESC
        """
        
        rows = self._db.fetch_all(query)
        return [
            {
                'department_name': row['department_name'],
                'avg_salary': float(row['avg_salary']) if row['avg_salary'] else 0
            }
            for row in rows
        ]

    def get_hiring_dynamics(
        self, 
        user: dict, 
        months: int = 24
    ) -> List[Dict[str, Any]]:
        """Возвращает динамику найма сотрудников.
        
        Returns:
            Список словарей {month, hired_count}
        """
        check_permission(user, Permission.VIEW_ANALYTICS)
        
        query = """
            SELECT 
                DATE_TRUNC('month', hire_date) as month,
                COUNT(*) as hired
            FROM employees
            WHERE hire_date >= date_trunc('month', NOW()) - (%s * INTERVAL '1 month')
            GROUP BY month
            ORDER BY month
        """
        
        rows = self._db.fetch_all(query, (months,))
        return [
            {
                'month': row['month'].strftime('%Y-%m') if row['month'] else '',
                'hired_count': row['hired']
            }
            for row in rows
        ]

    def get_department_summary(self, user: dict) -> List[Dict[str, Any]]:
        """Возвращает сводную статистику по отделам.
        
        Returns:
            Список словарей с полной статистикой
        """
        check_permission(user, Permission.VIEW_ANALYTICS)
        
        query = """
            WITH dept_projects AS (
                SELECT department_id, COUNT(*) as project_count
                FROM projects
                GROUP BY department_id
            ),
            dept_salaries AS (
                SELECT 
                    e.department_id,
                    COALESCE(SUM(s.salary_amount), 0) as total_salary,
                    COALESCE(AVG(s.salary_amount), 0) as avg_salary
                FROM employees e
                JOIN salaries s ON e.employee_id = s.employee_id
                GROUP BY e.department_id
            )
            SELECT 
                d.department_name,
                COUNT(e.employee_id) as employee_count,
                COALESCE(dp.project_count, 0) as project_count,
                COALESCE(ds.total_salary, 0) as total_salary,
                COALESCE(ds.avg_salary, 0) as avg_salary
            FROM departments d
            LEFT JOIN employees e ON d.department_id = e.department_id
            LEFT JOIN dept_projects dp ON d.department_id = dp.department_id
            LEFT JOIN dept_salaries ds ON d.department_id = ds.department_id
            GROUP BY d.department_id, d.department_name, 
                     dp.project_count, ds.total_salary, ds.avg_salary
            ORDER BY d.department_name
        """
        
        rows = self._db.fetch_all(query)
        return [
            {
                'department_name': row['department_name'],
                'employee_count': row['employee_count'],
                'project_count': row['project_count'],
                'total_salary': float(row['total_salary']) if row['total_salary'] else 0,
                'avg_salary': float(row['avg_salary']) if row['avg_salary'] else 0
            }
            for row in rows
        ]

    def get_gender_distribution(self, user: dict) -> Dict[str, int]:
        """Возвращает распределение сотрудников по полу.
        
        Returns:
            Словарь {gender: count}
        """
        check_permission(user, Permission.VIEW_ANALYTICS)
        
        query = """
            SELECT gender, COUNT(*) as count
            FROM employees
            WHERE gender IS NOT NULL
            GROUP BY gender
            ORDER BY gender
        """
        
        rows = self._db.fetch_all(query)
        return {row['gender']: row['count'] for row in rows}

    def get_age_distribution(self, user: dict) -> List[Dict[str, Any]]:
        """Возвращает распределение сотрудников по возрастным группам.
        
        Returns:
            Список словарей {age_group, count}
        """
        check_permission(user, Permission.VIEW_ANALYTICS)
        
        query = """
            SELECT 
                CASE 
                    WHEN EXTRACT(YEAR FROM AGE(date_of_birth)) < 25 THEN '18-24'
                    WHEN EXTRACT(YEAR FROM AGE(date_of_birth)) < 35 THEN '25-34'
                    WHEN EXTRACT(YEAR FROM AGE(date_of_birth)) < 45 THEN '35-44'
                    WHEN EXTRACT(YEAR FROM AGE(date_of_birth)) < 55 THEN '45-54'
                    ELSE '55+'
                END as age_group,
                COUNT(*) as count
            FROM employees
            WHERE date_of_birth IS NOT NULL
            GROUP BY age_group
            ORDER BY age_group
        """
        
        rows = self._db.fetch_all(query)
        return [
            {'age_group': row['age_group'], 'count': row['count']}
            for row in rows
        ]