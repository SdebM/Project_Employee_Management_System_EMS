"""Сервис бизнес-логики для работы с сотрудниками.

Содержит класс :class:`EmployeeService`, который инкапсулирует:

- Проверку прав доступа перед операциями
- Валидацию данных сотрудника
- Фильтрацию по отделу для менеджеров
- Аудит действий пользователей

Основные методы:
    - :meth:`get_employees` - получение списка
    - :meth:`get_employee_by_id` - получение по ID
    - :meth:`create_employee` - создание
    - :meth:`update_employee` - обновление
    - :meth:`delete_employee` - удаление


"""

from typing import List, Optional, Dict, Any
from datetime import date

from models.employees import Employee
from repositories.employee_repository import EmployeeRepository
from core.database import Database
from core.permissions import Permission, PermissionManager, check_permission
from core.exceptions import ValidationError, EntityNotFoundError
from utils.validators import Validators
from utils.formatters import Formatters


class EmployeeService:
    """Сервис для управления сотрудниками.
    
    Инкапсулирует бизнес-логику:
    - Валидация данных
    - Проверка прав доступа
    - Фильтрация по ролям
    - Аудит действий
    
    Пример использования:
        service = EmployeeService(db)
        employees = service.get_employees(current_user, {'status': 'active'})
    """

    def __init__(self, db: Database):
        """
        Args:
            db: Объект подключения к БД
        """
        self._db = db
        self._repository = EmployeeRepository(db)

    @property
    def db(self) -> Database:
        """Возвращает объект БД (для диалогов)."""
        return self._db

    def get_employees(
        self, 
        user: dict, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Employee]:
        """Получает список сотрудников с учетом прав доступа.
        
        Args:
            user: Данные текущего пользователя
            filters: Фильтры поиска
            
        Returns:
            Список сотрудников (для менеджеров - только из своего отдела)
        """
        check_permission(user, Permission.VIEW_EMPLOYEES)
        
        filters = filters or {}
        
        # По умолчанию показываем только активных сотрудников
        if 'status' not in filters:
            filters['status'] = 'active'
        
        # Менеджеры видят только свой отдел
        if user.get('role') == 'manager' and user.get('department_id'):
            filters['department_id'] = user['department_id']
        
        employees = self._repository.get_all(filters)
        return self._mask_confidential(user, employees)

    @staticmethod
    def _mask_confidential(user: dict, employees) -> list:
        """Маскирует ИНН/СНИЛС/паспорт, если нет права VIEW_CONFIDENTIAL.

        Право есть только у роли admin (см. core.permissions.ROLE_PERMISSIONS),
        но раньше оно нигде не использовалось, и персональные данные
        (ИНН, СНИЛС, паспорт) были видны всем ролям в диалогах и выгрузках.
        Замена выполняется по значению, поэтому в таблицы/экспорт
        замаскированные значения попадают уже на уровне сервиса.
        """
        pm = PermissionManager(user)
        if pm.has_permission(Permission.VIEW_CONFIDENTIAL):
            return employees
        
        for emp in employees:
            emp.inn = Formatters.mask_confidential(emp.inn) or None
            emp.snils = Formatters.mask_confidential(emp.snils) or None
            emp.passport = Formatters.mask_confidential(emp.passport) or None
        return employees

    def get_employee_by_id(self, user: dict, employee_id: int) -> Optional[Employee]:
        """Получает сотрудника по ID.
        
        Args:
            user: Данные текущего пользователя
            employee_id: ID сотрудника
            
        Returns:
            Объект Employee или None
            
        Raises:
            PermissionDeniedError: Если нет прав на просмотр
        """
        check_permission(user, Permission.VIEW_EMPLOYEES)
        
        employee = self._repository.get_by_id(employee_id)
        
        if employee and user.get('role') == 'manager':
            # Менеджер может видеть только сотрудников своего отдела
            if employee.department_id != user.get('department_id'):
                return None
        
        if employee:
            self._mask_confidential(user, [employee])
        
        return employee

    def create_employee(self, user: dict, data: Dict[str, Any]) -> int:
        """Создает нового сотрудника.
        
        Args:
            user: Данные текущего пользователя
            data: Словарь с данными сотрудника
            
        Returns:
            ID созданного сотрудника
            
        Raises:
            ValidationError: При ошибках валидации
            PermissionDeniedError: Если нет прав на создание
        """
        check_permission(user, Permission.CREATE_EMPLOYEE)
        
        # Валидация данных
        self._validate_employee_data(data)
        
        # Создание объекта Employee
        employee = Employee(
            first_name=data['first_name'],
            last_name=data['last_name'],
            date_of_birth=data.get('date_of_birth'),
            gender=data.get('gender', 'М'),
            hire_date=data.get('hire_date', date.today()),
            department_id=data.get('department_id'),
            phone=data.get('phone'),
            email=data.get('email'),
            inn=data.get('inn'),
            snils=data.get('snils'),
            passport=data.get('passport'),
            status='active'
        )
        
        employee_id = self._repository.create(employee)
        
        # Логирование действия
        self._db.log_action(
            user['id'], 
            'CREATE_EMPLOYEE', 
            f"Создан сотрудник: {employee.full_name} (ID: {employee_id})"
        )
        
        return employee_id

    def update_employee(
        self, 
        user: dict, 
        employee_id: int, 
        data: Dict[str, Any]
    ) -> bool:
        """Обновляет данные сотрудника.
        
        Args:
            user: Данные текущего пользователя
            employee_id: ID сотрудника
            data: Словарь с обновленными данными
            
        Returns:
            True если обновление успешно
            
        Raises:
            EntityNotFoundError: Если сотрудник не найден
            ValidationError: При ошибках валидации
        """
        check_permission(user, Permission.EDIT_EMPLOYEE)
        
        employee = self._repository.get_by_id(employee_id)
        if not employee:
            raise EntityNotFoundError("Сотрудник", employee_id)
        
        # Валидация обновленных данных
        self._validate_employee_data(data, is_update=True)
        
        # Обновление полей
        for field, value in data.items():
            if hasattr(employee, field):
                setattr(employee, field, value)
        
        result = self._repository.update(employee)
        
        if result:
            self._db.log_action(
                user['id'],
                'UPDATE_EMPLOYEE',
                f"Обновлен сотрудник: {employee.full_name} (ID: {employee_id})"
            )
        
        return result

    def delete_employee(self, user: dict, employee_id: int) -> bool:
        """Удаляет сотрудника.
        
        Args:
            user: Данные текущего пользователя
            employee_id: ID сотрудника
            
        Returns:
            True если удаление успешно
        """
        check_permission(user, Permission.DELETE_EMPLOYEE)
        
        employee = self._repository.get_by_id(employee_id)
        if not employee:
            raise EntityNotFoundError("Сотрудник", employee_id)
        
        result = self._repository.delete(employee_id)
        
        if result:
            self._db.log_action(
                user['id'],
                'DELETE_EMPLOYEE',
                f"Удален сотрудник: {employee.full_name} (ID: {employee_id})"
            )
        
        return result

    def get_employee_count_by_department(self) -> List[tuple]:
        """Возвращает статистику по отделам."""
        return self._repository.count_by_department()

    def _validate_employee_data(self, data: dict, is_update: bool = False) -> None:
        """Валидирует данные сотрудника.
        
        Args:
            data: Словарь с данными
            is_update: Флаг обновления (для частичной валидации)
            
        Raises:
            ValidationError: При ошибках валидации
        """
        if not is_update:
            # Обязательные поля при создании
            if not data.get('first_name'):
                raise ValidationError("Имя обязательно для заполнения", "first_name")
            if not data.get('last_name'):
                raise ValidationError("Фамилия обязательна для заполнения", "last_name")
        
        # Валидация возраста
        if data.get('date_of_birth') and data.get('hire_date'):
            is_valid, msg = Validators.validate_age(data['date_of_birth'], min_age=18)
            if not is_valid:
                raise ValidationError(msg, "date_of_birth")
        
        # Валидация email
        if data.get('email'):
            is_valid, msg = Validators.validate_email(data['email'])
            if not is_valid:
                raise ValidationError(msg, "email")
        
        # Валидация телефона
        if data.get('phone'):
            # phone = data['phone'].replace(' ', '').replace('-', '')
            # if not phone.replace('+', '').isdigit():
            #     raise ValidationError("Некорректный формат телефона", "phone")
            is_valid, msg = Validators.validate_phone(data['phone'])
            if not is_valid:
                raise ValidationError(msg, "phone")
            
        # Валидация СНИЛС
        if data.get('snils'):
            is_valid, msg = Validators.validate_snils(data['snils'])
            if not is_valid:
                raise ValidationError(msg, "snils")

        # Валидация ИНН
        if data.get('inn'):
            is_valid, msg = Validators.validate_inn(data['inn'])
            if not is_valid:
                raise ValidationError(msg, "inn")
            
        # Валидация паспорта
        if data.get('passport'):
            is_valid, msg = Validators.validate_passport(data['passport'])
            if not is_valid:
                raise ValidationError(msg, "passport")
        

    def _calculate_age(self, birth_date: date, reference_date: date) -> int:
        """Вычисляет возраст на указанную дату."""
        age = reference_date.year - birth_date.year
        if (reference_date.month, reference_date.day) < (birth_date.month, birth_date.day):
            age -= 1
        return age
