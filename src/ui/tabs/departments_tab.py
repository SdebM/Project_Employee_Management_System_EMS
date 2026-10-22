"""Вкладка отделов.

Реализует управление отделами:
- Просмотр списка отделов
- Добавление, редактирование, удаление
- Фильтрация и поиск
- Экспорт в PDF/Excel
"""

from typing import Optional, List
import logging

from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QLineEdit,
    QLabel,
    QDialog,
    QFormLayout,
    QTextEdit,
    QComboBox,
    QHeaderView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from ui.base_tab import BaseTab
from services.department_service import DepartmentService
from services.employee_service import EmployeeService
from core.permissions import Permission
from core.exceptions import ValidationError, EntityNotFoundError, PermissionDeniedError
from models.departments import Department
from styles import TABLE_STYLES, BUTTON_STYLES


class DepartmentsTab(BaseTab):
    """Вкладка управления отделами.
    
    Использует:
    - DepartmentService для бизнес-логики
    - BaseTab для общего функционала
    """
    
    BUTTON_PERMISSIONS = {
        'btn_add': Permission.CREATE_DEPARTMENT,
        'btn_edit': Permission.EDIT_DEPARTMENT,
        'btn_delete': Permission.DELETE_DEPARTMENT,
        'btn_export_excel': Permission.EXPORT_DATA,
        'btn_export_pdf': Permission.EXPORT_DATA,
    }

    def __init__(
        self, 
        department_service: DepartmentService,
        employee_service: EmployeeService,
        user: dict
    ):
        """
        Args:
            department_service: Сервис работы с отделами
            employee_service: Сервис работы с сотрудниками (для выбора руководителя)
            user: Данные текущего пользователя
        """
        super().__init__(department_service, user)
        self.department_service = department_service
        self.employee_service = employee_service
        self.logger = logging.getLogger(__name__)
        
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
        self.search_name.setPlaceholderText("Название отдела")
        
        panel.addWidget(QLabel("Поиск:"))
        panel.addWidget(self.search_name)
        panel.addStretch()
        
        return panel

    def _create_table(self) -> QTableWidget:
        """Создает таблицу отделов."""
        table = QTableWidget()
        
        columns = ["ID", "Название", "Описание", "Руководитель", "Сотрудников"]
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        
        # Настройка заголовков: равномерное растяжение по ширине,
        # кроме ID — фиксированная узкая колонка.
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, 50)
        
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
        self.btn_add.clicked.connect(self.add_department)
        self.btn_edit.clicked.connect(self.edit_department)
        self.btn_delete.clicked.connect(self.delete_department)
        self.btn_refresh.clicked.connect(self.load_data)
        
        self.btn_export_excel.clicked.connect(self.export_to_excel)
        self.btn_export_pdf.clicked.connect(self.export_to_pdf)
        
        self.search_name.textChanged.connect(self.trigger_search)
        
        self.main_table.doubleClicked.connect(self.edit_department)

    def load_data(self):
        """Загружает список отделов из сервиса."""
        try:
            self.logger.debug(f"DepartmentsTab.load_data called by user={self.user}")
            # Собираем фильтры
            filters = {}
            
            name = self.search_name.text().strip()
            if name:
                filters['department_name'] = name
            
            # Получаем данные через сервис
            departments = self.department_service.get_departments(self.user, filters)

            try:
                sample_ids = [d.department_id for d in departments[:5]]
            except Exception:
                sample_ids = None
            self.logger.debug(f"Получено {len(departments)} отделов, filters={filters}, sample_ids={sample_ids}")
            
            # Заполняем таблицу
            self._populate_table(departments)
            
        except PermissionDeniedError as e:
            self.show_error("Доступ запрещен", str(e))
        except Exception as e:
            self.logger.exception(f"Ошибка загрузки отделов: {e}")
            self.show_error("Ошибка", f"Не удалось загрузить список отделов:\n{e}")

    def _populate_table(self, departments: List[Department]):
        """Заполняет таблицу данными."""
        self.main_table.setRowCount(len(departments))
        
        for row, dept in enumerate(departments):
            self.main_table.setItem(row, 0, QTableWidgetItem(str(dept.department_id)))
            self.main_table.setItem(row, 1, QTableWidgetItem(dept.department_name))
            self.main_table.setItem(row, 2, QTableWidgetItem(dept.description or ""))
            self.main_table.setItem(row, 3, QTableWidgetItem(dept.manager_name or "Не назначен"))
            self.main_table.setItem(row, 4, QTableWidgetItem(str(dept.employee_count)))
            
            # Центрирование
            for col in range(self.main_table.columnCount()):
                item = self.main_table.item(row, col)
                if item:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def add_department(self):
        """Открывает диалог добавления отдела."""
        dialog = DepartmentDialog(self, self.employee_service, self.user)
        dialog.setWindowTitle("Добавить отдел")
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                data = dialog.get_data()
                department_id = self.department_service.create_department(self.user, data)
                self.show_info("Успех", f"Отдел добавлен (ID: {department_id})")
                self.load_data()
            except ValidationError as e:
                self.show_error("Ошибка валидации", e.message)
            except PermissionDeniedError as e:
                self.show_error("Доступ запрещен", str(e))
            except Exception as e:
                logging.error(f"Ошибка добавления: {e}", exc_info=True)
                self.show_error("Ошибка", f"Не удалось добавить отдел:\n{e}")

    def edit_department(self):
        """Открывает диалог редактирования отдела."""
        department_id = self.get_selected_row_id()
        if not department_id:
            return
        
        try:
            department = self.department_service.get_department_by_id(self.user, department_id)
            if not department:
                self.show_error("Ошибка", "Отдел не найден")
                return
            
            dialog = DepartmentDialog(self, self.employee_service, self.user, department)
            dialog.setWindowTitle("Редактировать отдел")
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                data = dialog.get_data()
                self.department_service.update_department(self.user, department_id, data)
                self.show_info("Успех", "Данные отдела обновлены")
                self.load_data()
                
        except ValidationError as e:
            self.show_error("Ошибка валидации", e.message)
        except Exception as e:
            logging.error(f"Ошибка редактирования: {e}", exc_info=True)
            self.show_error("Ошибка", f"Не удалось обновить данные:\n{e}")

    def delete_department(self):
        """Удаляет выбранный отдел."""
        department_id = self.get_selected_row_id()
        if not department_id:
            return
        
        if not self.confirm_action(
            "Подтверждение",
            f"Вы уверены, что хотите удалить отдел с ID {department_id}?"
        ):
            return
        
        try:
            self.department_service.delete_department(self.user, department_id)
            self.show_info("Успех", "Отдел удален")
            self.load_data()
        except ValidationError as e:
            self.show_error("Ошибка", e.message)
        except EntityNotFoundError:
            self.show_error("Ошибка", "Отдел не найден")
        except PermissionDeniedError as e:
            self.show_error("Доступ запрещен", str(e))
        except Exception as e:
            logging.error(f"Ошибка удаления: {e}", exc_info=True)
            self.show_error("Ошибка", f"Не удалось удалить отдел:\n{e}")

    def _get_export_filename(self, extension: str) -> str:
        return f"departments.{extension}"

    def _get_export_title(self) -> str:
        return "Список отделов"


class DepartmentDialog(QDialog):
    """Диалог добавления/редактирования отдела."""
    
    def __init__(
        self, 
        parent, 
        employee_service: EmployeeService,
        user: dict,
        department: Optional[Department] = None
    ):
        super().__init__(parent)
        self.employee_service = employee_service
        self.user = user
        self.department = department
        
        self.setMinimumWidth(400)
        self.init_ui()
        
        if department:
            self._load_data()
    
    def init_ui(self):
        """Инициализирует интерфейс диалога."""
        layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Введите название отдела")
        
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("Описание отдела")
        self.description_edit.setMaximumHeight(100)
        
        self.manager_combo = QComboBox()
        self._load_managers()
        
        layout.addRow("Название*:", self.name_edit)
        layout.addRow("Описание:", self.description_edit)
        layout.addRow("Руководитель:", self.manager_combo)
        
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
    
    def _load_managers(self):
        """Загружает список возможных руководителей."""
        self.manager_combo.clear()
        self.manager_combo.addItem("Не назначен", None)
        
        try:
            employees = self.employee_service.get_employees(self.user, {})
            for emp in employees:
                name = f"{emp.last_name} {emp.first_name}"
                self.manager_combo.addItem(name, emp.employee_id)
        except Exception as e:
            logging.error(f"Ошибка загрузки сотрудников: {e}")
    
    def _load_data(self):
        """Загружает данные отдела в форму."""
        if self.department:
            self.name_edit.setText(self.department.department_name)
            self.description_edit.setPlainText(self.department.description or "")
            
            # Выбираем руководителя
            if hasattr(self.department, 'manager_id') and self.department.manager_id:
                index = self.manager_combo.findData(self.department.manager_id)
                if index >= 0:
                    self.manager_combo.setCurrentIndex(index)
    
    def get_data(self) -> dict:
        """Возвращает данные из формы."""
        return {
            'department_name': self.name_edit.text().strip(),
            'description': self.description_edit.toPlainText().strip() or None,
            'manager_id': self.manager_combo.currentData()
        }
