"""Вкладка проектов.

Реализует управление проектами:
- Просмотр списка проектов
- Добавление, редактирование, удаление
- Фильтрация по статусу и отделу
- Экспорт в PDF/Excel
"""

from typing import Optional, List
from datetime import date
import logging

from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLineEdit,
    QComboBox,
    QLabel,
    QDialog,
    QFormLayout,
    QTextEdit,
    QDateEdit,
    QDoubleSpinBox,
)
from PyQt6.QtWidgets import QCheckBox
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QIcon, QColor

from ui.base_tab import BaseTab
from services.project_service import ProjectService
from services.department_service import DepartmentService
from core.permissions import Permission
from core.exceptions import ValidationError, EntityNotFoundError, PermissionDeniedError
from models.projects import Project
from styles import TABLE_STYLES, BUTTON_STYLES
from utils.formatters import Formatters


# Маппинг статусов
STATUS_MAP = {
    'planning': 'Планирование',
    'in_progress': 'В работе',
    'on_hold': 'Приостановлен',
    'completed': 'Завершён',
    'cancelled': 'Отменён'
}

STATUS_COLORS = {
    'planning': '#17a2b8',      # голубой
    'in_progress': '#28a745',   # зеленый
    'on_hold': '#ffc107',       # желтый
    'completed': '#6c757d',     # серый
    'cancelled': '#dc3545'      # красный
}


class ProjectsTab(BaseTab):
    """Вкладка управления проектами.
    
    Использует:
    - ProjectService для бизнес-логики
    - BaseTab для общего функционала
    """
    
    BUTTON_PERMISSIONS = {
        'btn_add': Permission.CREATE_PROJECT,
        'btn_edit': Permission.EDIT_PROJECT,
        'btn_delete': Permission.DELETE_PROJECT,
        'btn_export_excel': Permission.EXPORT_DATA,
        'btn_export_pdf': Permission.EXPORT_DATA,
    }

    def __init__(
        self, 
        project_service: ProjectService,
        department_service: DepartmentService,
        user: dict
    ):
        """
        Args:
            project_service: Сервис работы с проектами
            department_service: Сервис работы с отделами
            user: Данные текущего пользователя
        """
        super().__init__(project_service, user)
        self.project_service = project_service
        self.department_service = department_service
        
        self.init_ui()
        self.setup_access_control()
        self.load_data()

    def init_ui(self):
        """Инициализирует интерфейс вкладки."""
        main_layout = QVBoxLayout()

        # Панель управления
        control_panel = self._create_control_panel()
        
        # Панель поиска
        search_panel = self._create_search_panel()
        
        # Таблица
        self.main_table = self._create_table()
        
        # Нижняя панель
        bottom_panel = self._create_bottom_panel()

        # Сборка
        main_layout.addLayout(control_panel)
        main_layout.addLayout(search_panel)
        main_layout.addWidget(self.main_table)
        main_layout.addLayout(bottom_panel)
        
        self.setLayout(main_layout)
        
        # Подключение сигналов
        self._connect_signals()

    def _create_control_panel(self) -> QHBoxLayout:
        """Создает панель с кнопками управления."""
        panel = QHBoxLayout()
        
        self.btn_add = QPushButton("Добавить")
        self.btn_edit = QPushButton("Редактировать")
        self.btn_delete = QPushButton("Удалить")
        
        self.btn_add.setStyleSheet(BUTTON_STYLES.get("primary", ""))
        self.btn_edit.setStyleSheet(BUTTON_STYLES.get("secondary", ""))
        self.btn_delete.setStyleSheet(BUTTON_STYLES.get("secondary", ""))
        
        panel.addWidget(self.btn_add)
        panel.addWidget(self.btn_edit)
        panel.addWidget(self.btn_delete)
        panel.addStretch()
        
        return panel

    def _create_search_panel(self) -> QHBoxLayout:
        """Создает панель поиска."""
        panel = QHBoxLayout()
        
        self.search_name = QLineEdit()
        self.search_name.setPlaceholderText("Название проекта")
        
        self.status_combo = QComboBox()
        self.status_combo.addItem("Все статусы", None)
        for status_key, status_name in STATUS_MAP.items():
            self.status_combo.addItem(status_name, status_key)
        
        self.department_combo = QComboBox()
        self._load_departments()
        # Фильтры по датам создания/обновления
        self.created_from_chk = QCheckBox("Дата создания от")
        self.created_from_date = QDateEdit()
        self.created_from_date.setCalendarPopup(True)
        self.created_to_chk = QCheckBox("до")
        self.created_to_date = QDateEdit()
        self.created_to_date.setCalendarPopup(True)

        self.updated_from_chk = QCheckBox("Дата обновления от")
        self.updated_from_date = QDateEdit()
        self.updated_from_date.setCalendarPopup(True)
        self.updated_to_chk = QCheckBox("до")
        self.updated_to_date = QDateEdit()
        self.updated_to_date.setCalendarPopup(True)
        
        panel.addWidget(QLabel("Фильтры:"))
        panel.addWidget(self.search_name)
        panel.addWidget(self.status_combo)
        panel.addWidget(self.department_combo)
        # created
        panel.addWidget(self.created_from_chk)
        panel.addWidget(self.created_from_date)
        panel.addWidget(self.created_to_chk)
        panel.addWidget(self.created_to_date)
        # updated
        panel.addWidget(self.updated_from_chk)
        panel.addWidget(self.updated_from_date)
        panel.addWidget(self.updated_to_chk)
        panel.addWidget(self.updated_to_date)
        panel.addStretch()
        
        return panel

    def _create_table(self) -> QTableWidget:
        """Создает таблицу проектов."""
        table = QTableWidget()
        
        columns = ["ID", "Название", "Статус", "Дата начала", 
                   "Дата окончания", "Бюджет", "Отдел", "Дата создания", "Дата обновления"]
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)

        # Настройка заголовков — равномерное растяжение колонок
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # Стили
        table.setStyleSheet(TABLE_STYLES.get("base", ""))
        header.setStyleSheet(TABLE_STYLES.get("header", ""))
        
        # Настройки
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setMinimumHeight(400)
        table.setShowGrid(True)
        
        return table

    def _create_bottom_panel(self) -> QHBoxLayout:
        """Создает нижнюю панель с кнопками."""
        panel = QHBoxLayout()
        
        # Кнопка обновления
        self.btn_refresh = QPushButton()
        self.btn_refresh.setIcon(QIcon.fromTheme("view-refresh"))
        self.btn_refresh.setToolTip("Обновить данные")
        self.btn_refresh.setFixedSize(32, 32)
        
        # Кнопки экспорта
        self.btn_export_excel = QPushButton("Экспорт в Excel")
        self.btn_export_pdf = QPushButton("Экспорт в PDF")
        
        self.btn_export_excel.setStyleSheet(BUTTON_STYLES.get("export", ""))
        self.btn_export_pdf.setStyleSheet(BUTTON_STYLES.get("pdf", ""))
        
        panel.addWidget(self.btn_refresh)
        panel.addStretch()
        panel.addWidget(self.btn_export_excel)
        panel.addWidget(self.btn_export_pdf)
        
        return panel

    def _connect_signals(self):
        """Подключает сигналы к слотам."""
        self.btn_add.clicked.connect(self.add_project)
        self.btn_edit.clicked.connect(self.edit_project)
        self.btn_delete.clicked.connect(self.delete_project)
        self.btn_refresh.clicked.connect(self.load_data)
        
        self.btn_export_excel.clicked.connect(self.export_to_excel)
        self.btn_export_pdf.clicked.connect(self.export_to_pdf)
        
        self.search_name.textChanged.connect(self.trigger_search)
        self.status_combo.currentIndexChanged.connect(self.trigger_search)
        self.department_combo.currentIndexChanged.connect(self.trigger_search)
        
        self.main_table.doubleClicked.connect(self.edit_project)

    def _load_departments(self):
        """Загружает отделы в комбобокс."""
        try:
            departments = self.department_service.get_departments_for_dropdown()
            self.department_combo.clear()
            self.department_combo.addItem("Все отделы", None)
            for dept_id, dept_name in departments:
                self.department_combo.addItem(dept_name, dept_id)
        except Exception as e:
            logging.error(f"Ошибка загрузки отделов: {e}")

    def load_data(self):
        """Загружает список проектов из сервиса."""
        try:
            # Собираем фильтры
            filters = {}
            
            name = self.search_name.text().strip()
            if name:
                filters['project_name'] = name
            
            status = self.status_combo.currentData()
            if status:
                filters['status'] = status
            
            dept_id = self.department_combo.currentData()
            if dept_id:
                filters['department_id'] = dept_id

            # даты создания/обновления (по чекбоксам)
            if getattr(self, 'created_from_chk', None) and self.created_from_chk.isChecked():
                d = self.created_from_date.date()
                filters['created_from'] = date(d.year(), d.month(), d.day())
            if getattr(self, 'created_to_chk', None) and self.created_to_chk.isChecked():
                d = self.created_to_date.date()
                # включительно: добавим 1 день
                from datetime import timedelta
                filters['created_to'] = date(d.year(), d.month(), d.day()) + timedelta(days=1)
            if getattr(self, 'updated_from_chk', None) and self.updated_from_chk.isChecked():
                d = self.updated_from_date.date()
                filters['updated_from'] = date(d.year(), d.month(), d.day())
            if getattr(self, 'updated_to_chk', None) and self.updated_to_chk.isChecked():
                d = self.updated_to_date.date()
                from datetime import timedelta
                filters['updated_to'] = date(d.year(), d.month(), d.day()) + timedelta(days=1)
            
            # Получаем данные через сервис
            projects = self.project_service.get_projects(self.user, filters)
            
            # Заполняем таблицу
            self._populate_table(projects)
            
        except PermissionDeniedError as e:
            self.show_error("Доступ запрещен", str(e))
        except Exception as e:
            logging.error(f"Ошибка загрузки проектов: {e}")
            self.show_error("Ошибка", "Не удалось загрузить список проектов")

    def _populate_table(self, projects: List[Project]):
        """Заполняет таблицу данными."""
        self.main_table.setRowCount(len(projects))
        
        for row, proj in enumerate(projects):
            self.main_table.setItem(row, 0, QTableWidgetItem(str(proj.project_id)))
            self.main_table.setItem(row, 1, QTableWidgetItem(proj.project_name))
            
            # Статус с цветом
            status_text = STATUS_MAP.get(proj.status, proj.status)
            status_item = QTableWidgetItem(status_text)
            status_color = STATUS_COLORS.get(proj.status, '#000000')
            status_item.setForeground(QColor(status_color))
            self.main_table.setItem(row, 2, status_item)
            
            self.main_table.setItem(row, 3, QTableWidgetItem(
                Formatters.format_date(proj.start_date)
            ))
            self.main_table.setItem(row, 4, QTableWidgetItem(
                Formatters.format_date(proj.end_date)
            ))
            self.main_table.setItem(row, 5, QTableWidgetItem(
                Formatters.format_money(proj.budget) if proj.budget else ""
            ))
            self.main_table.setItem(row, 6, QTableWidgetItem(proj.department_name or ""))
            # Дата создания и обновления
            self.main_table.setItem(row, 7, QTableWidgetItem(
                Formatters.format_datetime(proj.created_at)
            ))
            self.main_table.setItem(row, 8, QTableWidgetItem(
                Formatters.format_datetime(proj.updated_at)
            ))
            
            # Центрирование
            for col in range(self.main_table.columnCount()):
                item = self.main_table.item(row, col)
                if item:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def add_project(self):
        """Открывает диалог добавления проекта."""
        dialog = ProjectDialog(self, self.department_service, self.user)
        dialog.setWindowTitle("Добавить проект")
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                data = dialog.get_data()
                project_id = self.project_service.create_project(self.user, data)
                self.show_info("Успех", f"Проект добавлен (ID: {project_id})")
                self.load_data()
            except ValidationError as e:
                self.show_error("Ошибка валидации", e.message)
            except PermissionDeniedError as e:
                self.show_error("Доступ запрещен", str(e))
            except Exception as e:
                logging.error(f"Ошибка добавления: {e}")
                self.show_error("Ошибка", "Не удалось добавить проект")

    def edit_project(self):
        """Открывает диалог редактирования проекта."""
        project_id = self.get_selected_row_id()
        if not project_id:
            return
        
        try:
            project = self.project_service.get_project_by_id(self.user, project_id)
            if not project:
                self.show_error("Ошибка", "Проект не найден")
                return
            
            dialog = ProjectDialog(self, self.department_service, self.user, project)
            dialog.setWindowTitle("Редактировать проект")
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                data = dialog.get_data()
                self.project_service.update_project(self.user, project_id, data)
                self.show_info("Успех", "Данные проекта обновлены")
                self.load_data()
                
        except ValidationError as e:
            self.show_error("Ошибка валидации", e.message)
        except Exception as e:
            logging.error(f"Ошибка редактирования: {e}")
            self.show_error("Ошибка", "Не удалось обновить данные")

    def delete_project(self):
        """Удаляет выбранный проект."""
        project_id = self.get_selected_row_id()
        if not project_id:
            return
        
        if not self.confirm_action(
            "Подтверждение",
            f"Вы уверены, что хотите удалить проект с ID {project_id}?"
        ):
            return
        
        try:
            self.project_service.delete_project(self.user, project_id)
            self.show_info("Успех", "Проект удален")
            self.load_data()
        except EntityNotFoundError:
            self.show_error("Ошибка", "Проект не найден")
        except PermissionDeniedError as e:
            self.show_error("Доступ запрещен", str(e))
        except Exception as e:
            logging.error(f"Ошибка удаления: {e}")
            self.show_error("Ошибка", "Не удалось удалить проект")

    def _get_export_filename(self, extension: str) -> str:
        return f"projects.{extension}"

    def _get_export_title(self) -> str:
        return "Список проектов"


class ProjectDialog(QDialog):
    """Диалог добавления/редактирования проекта."""
    
    def __init__(
        self, 
        parent, 
        department_service: DepartmentService,
        user: dict,
        project: Optional[Project] = None
    ):
        super().__init__(parent)
        self.department_service = department_service
        self.user = user
        self.project = project
        
        self.setMinimumWidth(450)
        self.init_ui()
        
        if project:
            self._load_data()
    
    def init_ui(self):
        """Инициализирует интерфейс диалога."""
        layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Введите название проекта")
        
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("Описание проекта")
        self.description_edit.setMaximumHeight(80)
        
        self.status_combo = QComboBox()
        for status_key, status_name in STATUS_MAP.items():
            self.status_combo.addItem(status_name, status_key)
        
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate())
        
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate().addMonths(3))
        
        self.budget_spin = QDoubleSpinBox()
        self.budget_spin.setRange(0, 999999999.99)
        self.budget_spin.setDecimals(2)
        self.budget_spin.setSuffix(" ₽")
        self.budget_spin.setSpecialValueText("Не указан")
        
        self.department_combo = QComboBox()
        self._load_departments()
        
        layout.addRow("Название*:", self.name_edit)
        layout.addRow("Описание:", self.description_edit)
        layout.addRow("Статус:", self.status_combo)
        layout.addRow("Дата начала:", self.start_date_edit)
        layout.addRow("Дата окончания:", self.end_date_edit)
        layout.addRow("Бюджет:", self.budget_spin)
        layout.addRow("Отдел:", self.department_combo)
        # Показать read-only даты создания/обновления (только при редактировании)
        self.created_label = QLabel("")
        self.updated_label = QLabel("")
        layout.addRow("Дата создания:", self.created_label)
        layout.addRow("Дата обновления:", self.updated_label)
        
        # Кнопки
        button_layout = QHBoxLayout()
        self.btn_save = QPushButton("Сохранить")
        self.btn_cancel = QPushButton("Отмена")
        
        self.btn_save.setStyleSheet(BUTTON_STYLES.get("primary", ""))
        self.btn_cancel.setStyleSheet(BUTTON_STYLES.get("secondary", ""))
        
        self.btn_save.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.btn_save)
        button_layout.addWidget(self.btn_cancel)
        
        layout.addRow(button_layout)
        self.setLayout(layout)
    
    def _load_departments(self):
        """Загружает список отделов."""
        self.department_combo.clear()
        self.department_combo.addItem("Не назначен", None)
        
        try:
            departments = self.department_service.get_departments_for_dropdown()
            for dept_id, dept_name in departments:
                self.department_combo.addItem(dept_name, dept_id)
        except Exception as e:
            logging.error(f"Ошибка загрузки отделов: {e}")
    
    def _load_data(self):
        """Загружает данные проекта в форму."""
        if self.project:
            self.name_edit.setText(self.project.project_name)
            self.description_edit.setPlainText(self.project.description or "")
            
            # Статус
            index = self.status_combo.findData(self.project.status)
            if index >= 0:
                self.status_combo.setCurrentIndex(index)
            
            # Даты
            if self.project.start_date:
                self.start_date_edit.setDate(QDate(
                    self.project.start_date.year,
                    self.project.start_date.month,
                    self.project.start_date.day
                ))
            
            if self.project.end_date:
                self.end_date_edit.setDate(QDate(
                    self.project.end_date.year,
                    self.project.end_date.month,
                    self.project.end_date.day
                ))
            
            # Бюджет
            if self.project.budget:
                self.budget_spin.setValue(float(self.project.budget))
            
            # Отдел
            if self.project.department_id:
                index = self.department_combo.findData(self.project.department_id)
                if index >= 0:
                    self.department_combo.setCurrentIndex(index)
            # Даты создания/обновления (если есть)
            if getattr(self.project, 'created_at', None):
                self.created_label.setText(Formatters.format_datetime(self.project.created_at))
            if getattr(self.project, 'updated_at', None):
                self.updated_label.setText(Formatters.format_datetime(self.project.updated_at))
    
    def get_data(self) -> dict:
        """Возвращает данные из формы."""
        start_date = self.start_date_edit.date()
        end_date = self.end_date_edit.date()
        
        return {
            'project_name': self.name_edit.text().strip(),
            'description': self.description_edit.toPlainText().strip() or None,
            'status': self.status_combo.currentData(),
            'start_date': date(start_date.year(), start_date.month(), start_date.day()),
            'end_date': date(end_date.year(), end_date.month(), end_date.day()),
            'budget': self.budget_spin.value() if self.budget_spin.value() > 0 else None,
            'department_id': self.department_combo.currentData()
        }
