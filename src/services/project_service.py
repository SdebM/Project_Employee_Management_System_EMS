"""Сервис бизнес-логики для работы с проектами."""

from typing import List, Optional, Dict, Any
from datetime import date

from models.projects import Project
from repositories.project_repository import ProjectRepository
from core.database import Database
from core.permissions import Permission, check_permission
from core.exceptions import ValidationError, EntityNotFoundError


class ProjectService:
    """Сервис для управления проектами."""

    def __init__(self, db: Database):
        self._db = db
        self._repository = ProjectRepository(db)

    def get_projects(
        self, 
        user: dict, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Project]:
        """Получает список проектов с учетом прав доступа."""
        check_permission(user, Permission.VIEW_PROJECTS)
        return self._repository.get_all(filters)

    def get_project_by_id(self, user: dict, project_id: int) -> Optional[Project]:
        """Получает проект по ID."""
        check_permission(user, Permission.VIEW_PROJECTS)
        return self._repository.get_by_id(project_id)

    def create_project(self, user: dict, data: Dict[str, Any]) -> int:
        """Создает новый проект."""
        check_permission(user, Permission.CREATE_PROJECT)
        
        self._validate_project_data(data)
        
        project = Project(
            project_name=data['project_name'],
            description=data.get('description'),
            start_date=data.get('start_date', date.today()),
            end_date=data.get('end_date'),
            status=data.get('status', 'planning'),
            budget=data.get('budget'),
            department_id=data.get('department_id')
        )
        
        project_id = self._repository.create(project)
        
        self._db.log_action(
            user['id'],
            'CREATE_PROJECT',
            f"Создан проект: {project.project_name} (ID: {project_id})"
        )
        
        return project_id

    def update_project(
        self, 
        user: dict, 
        project_id: int, 
        data: Dict[str, Any]
    ) -> bool:
        """Обновляет данные проекта."""
        check_permission(user, Permission.EDIT_PROJECT)
        
        project = self._repository.get_by_id(project_id)
        if not project:
            raise EntityNotFoundError("Проект", project_id)
        
        self._validate_project_data(data, is_update=True)
        
        for field, value in data.items():
            if hasattr(project, field):
                setattr(project, field, value)
        
        result = self._repository.update(project)
        
        if result:
            self._db.log_action(
                user['id'],
                'UPDATE_PROJECT',
                f"Обновлен проект: {project.project_name} (ID: {project_id})"
            )
        
        return result

    def delete_project(self, user: dict, project_id: int) -> bool:
        """Удаляет проект."""
        check_permission(user, Permission.DELETE_PROJECT)
        
        project = self._repository.get_by_id(project_id)
        if not project:
            raise EntityNotFoundError("Проект", project_id)
        
        result = self._repository.delete(project_id)
        
        if result:
            self._db.log_action(
                user['id'],
                'DELETE_PROJECT',
                f"Удален проект: {project.project_name} (ID: {project_id})"
            )
        
        return result

    def get_project_statistics(self) -> List[tuple]:
        """Возвращает статистику проектов по статусам."""
        return self._repository.count_by_status()

    def get_active_projects(self) -> List[Project]:
        """Возвращает активные проекты."""
        return self._repository.get_active_projects()

    def _validate_project_data(self, data: dict, is_update: bool = False) -> None:
        """Валидирует данные проекта."""
        if not is_update:
            if not data.get('project_name'):
                raise ValidationError("Название проекта обязательно", "project_name")
        
        # Проверка дат
        if data.get('start_date') and data.get('end_date'):
            if data['end_date'] < data['start_date']:
                raise ValidationError(
                    "Дата окончания не может быть раньше даты начала",
                    "end_date"
                )
        
        # Проверка бюджета
        if data.get('budget') is not None and data['budget'] < 0:
            raise ValidationError("Бюджет не может быть отрицательным", "budget")
        
        # Проверка статуса
        valid_statuses = ['planning', 'in_progress', 'on_hold', 'completed', 'cancelled']
        if data.get('status') and data['status'] not in valid_statuses:
            raise ValidationError(f"Недопустимый статус: {data['status']}", "status")
