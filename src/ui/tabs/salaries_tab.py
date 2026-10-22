"""Вкладка зарплат.

Реализует управление зарплатными записями:
- Просмотр списка выплат
- Добавление, редактирование, удаление
- Фильтрация по сотруднику, типу, периоду
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
    QComboBox,
    QLabel,
    QDialog,
    QFormLayout,
    QTextEdit,
    QDateEdit,
    QDoubleSpinBox,
    QHeaderView,
)
from PyQt6.QtCore import Qt, QDate, QSignalBlocker
from PyQt6.QtGui import QIcon

from ui.base_tab import BaseTab
from services.salary_service import SalaryService
from services.employee_service import EmployeeService
from core.permissions import Permission
from core.exceptions import ValidationError, EntityNotFoundError, PermissionDeniedError
from models.salaries import Salary
from styles import TABLE_STYLES, BUTTON_STYLES
from utils.formatters import Formatters


# Маппинг типов выплат.
# ВАЖНО: должен соответствовать CHECK-ограничению salaries.payment_type
# в схеме БД ('salary', 'bonus', 'advance'). Тип 'compensation' исключён:
# попытка сохранения приводила к нарушению CHECK и откату транзакции.
PAYMENT_TYPE_MAP = {
    'salary': 'Зарплата',
    'bonus': 'Премия',
    'advance': 'Аванс'
}


class SalariesTab(BaseTab):
    """Вкладка управления зарплатами.
    
    Использует:
    - SalaryService для бизнес-логики
    - BaseTab для общего функционала
    """
    
    BUTTON_PERMISSIONS = {
        'btn_add': Permission.CREATE_SALARY,
        'btn_edit': Permission.EDIT_SALARY,
        'btn_delete': Permission.DELETE_SALARY,
        'btn_export_excel': Permission.EXPORT_DATA,
        'btn_export_pdf': Permission.EXPORT_DATA,
    }

    def __init__(
        self, 
        salary_service: SalaryService,
        employee_service: EmployeeService,
        user: dict
    ):
        """
        Args:
            salary_service: Сервис работы с зарплатами
            employee_service: Сервис работы с сотрудниками
            user: Данные текущего пользователя
        """
        super().__init__(salary_service, user)
        self.salary_service = salary_service
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
        
        # Панель итогов
        totals_panel = self._create_totals_panel()
        
        # Нижняя панель
        bottom_panel = self._create_bottom_panel()

        # Сборка
        main_layout.addLayout(control_panel)
        main_layout.addLayout(search_panel)
        main_layout.addWidget(self.main_table)
        main_layout.addLayout(totals_panel)
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
        
        self.employee_combo = QComboBox()
        self._load_employees()
        
        self.type_combo = QComboBox()
        self.type_combo.addItem("Все типы", None)
        for type_key, type_name in PAYMENT_TYPE_MAP.items():
            self.type_combo.addItem(type_name, type_key)
        
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        # Широкий период по умолчанию (10 лет). Раньше стоял 1 год: сиды в
        # db/empls_db.sql создаются с датами до 3+ лет назад относительно даты
        # заливки БД, поэтому вся вкладка выглядела пустой — фильтр скрывал
        # все существующие записи.
        self.date_from.setDate(QDate.currentDate().addYears(-10))
        
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        
        panel.addWidget(QLabel("Сотрудник:"))
        panel.addWidget(self.employee_combo)
        panel.addWidget(QLabel("Тип:"))
        panel.addWidget(self.type_combo)
        panel.addWidget(QLabel("С:"))
        panel.addWidget(self.date_from)
        panel.addWidget(QLabel("По:"))
        panel.addWidget(self.date_to)
        panel.addStretch()
        
        return panel

    def _create_table(self) -> QTableWidget:
        """Создает таблицу зарплат."""
        table = QTableWidget()
        
        columns = ["ID", "Сотрудник", "Отдел", "Тип выплаты", 
                   "Сумма", "Дата выплаты", "Комментарий"]
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
        table.setMinimumHeight(350)
        table.setShowGrid(True)
        
        return table
    
    def _create_totals_panel(self) -> QHBoxLayout:
        """Создает панель с итогами."""
        panel = QHBoxLayout()
        
        self.total_label = QLabel("Итого: 0.00 ₽")
        self.total_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        self.count_label = QLabel("Записей: 0")
        
        panel.addStretch()
        panel.addWidget(self.count_label)
        panel.addWidget(QLabel(" | "))
        panel.addWidget(self.total_label)
        
        return panel

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
        self.btn_add.clicked.connect(self.add_salary)
        self.btn_edit.clicked.connect(self.edit_salary)
        self.btn_delete.clicked.connect(self.delete_salary)
        # Кнопка обновления — перезагружает и справочники, и данные
        self.btn_refresh.clicked.connect(self.refresh_all)
        
        self.btn_export_excel.clicked.connect(self.export_to_excel)
        self.btn_export_pdf.clicked.connect(self.export_to_pdf)
        
        self.employee_combo.currentIndexChanged.connect(self.trigger_search)
        self.type_combo.currentIndexChanged.connect(self.trigger_search)
        self.date_from.dateChanged.connect(self.trigger_search)
        self.date_to.dateChanged.connect(self.trigger_search)
        
        self.main_table.doubleClicked.connect(self.edit_salary)

    def _load_employees(self):
        """Загружает сотрудников в комбобокс.
        
        Обновление элементов QComboBox испускает currentIndexChanged,
        который связан с trigger_search() → timer → load_data(). Без
        блокировки сигналов перезаполнение комбобокса из load_data()
        порождало бесконечный цикл самообновления каждые 300 мс.
        """
        try:
            # Блокируем сигналы на время перезаполнения — разрываем петлю
            with QSignalBlocker(self.employee_combo):
                self.employee_combo.clear()
                self.employee_combo.addItem("Все сотрудники", None)
                
                employees = self.employee_service.get_employees(self.user, {})
                for emp in employees:
                    name = f"{emp.last_name} {emp.first_name}"
                    self.employee_combo.addItem(name, emp.employee_id)
        except Exception as e:
            logging.error(f"Ошибка загрузки сотрудников: {e}")

    def refresh_all(self):
        """Явное обновление по кнопке: справочник сотрудников + данные."""
        self._load_employees()
        self.load_data()

    def load_data(self):
        """Загружает список зарплатных записей из сервиса.
        
        Note:
            Не перечитывает справочник сотрудников: перезаполнение
            комбобокса здесь замыкало цикл currentIndexChanged →
            trigger_search → load_data. Справочник обновляется один раз
            при инициализации и явно — кнопкой "Обновить" (refresh_all).
        """
        try:
            # Собираем фильтры
            filters = {}
            
            emp_id = self.employee_combo.currentData()
            if emp_id:
                filters['employee_id'] = emp_id
            
            payment_type = self.type_combo.currentData()
            if payment_type:
                filters['payment_type'] = payment_type
            
            date_from = self.date_from.date()
            filters['date_from'] = date(date_from.year(), date_from.month(), date_from.day())
            
            date_to = self.date_to.date()
            filters['date_to'] = date(date_to.year(), date_to.month(), date_to.day())
            
            # Получаем данные через сервис
            salaries = self.salary_service.get_salaries(self.user, filters)
            try:
                sample_ids = [s.salary_id for s in salaries[:5]]
            except Exception:
                sample_ids = None
            self.logger.debug(f"Получено {len(salaries)} выплат, filters={filters}, sample_ids={sample_ids}")

            # Заполняем таблицу
            self._populate_table(salaries)

            # Обновляем итоги
            self._update_totals(salaries)
            
        except PermissionDeniedError as e:
            self.show_error("Доступ запрещен", str(e))
        except Exception as e:
            logging.error(f"Ошибка загрузки зарплат: {e}", exc_info=True)
            self.show_error("Ошибка", f"Не удалось загрузить список выплат:\n{e}")

    def _populate_table(self, salaries: List[Salary]):
        """Заполняет таблицу данными."""
        self.main_table.setRowCount(len(salaries))
        
        for row, sal in enumerate(salaries):
            self.main_table.setItem(row, 0, QTableWidgetItem(str(sal.salary_id)))
            self.main_table.setItem(row, 1, QTableWidgetItem(sal.employee_name or ""))
            self.main_table.setItem(row, 2, QTableWidgetItem(sal.department_name or ""))
            self.main_table.setItem(row, 3, QTableWidgetItem(
                PAYMENT_TYPE_MAP.get(sal.payment_type, sal.payment_type)
            ))
            # Сумма и дата — используем поля модели Salary: salary_amount, effective_date
            amount_text = getattr(sal, 'formatted_amount', None) or (f"{getattr(sal, 'salary_amount', 0):,.2f} ₽")
            self.main_table.setItem(row, 4, QTableWidgetItem(amount_text))
            self.main_table.setItem(row, 5, QTableWidgetItem(
                Formatters.format_date(getattr(sal, 'effective_date', None))
            ))
            self.main_table.setItem(row, 6, QTableWidgetItem(sal.description or ""))
            
            # Центрирование
            for col in range(self.main_table.columnCount()):
                item = self.main_table.item(row, col)
                if item:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    
    def _update_totals(self, salaries: List[Salary]):
        """Обновляет итоговые показатели."""
        total = sum(getattr(sal, 'salary_amount', 0) for sal in salaries)
        self.total_label.setText(f"Итого: {total:,.2f} ₽")
        self.count_label.setText(f"Записей: {len(salaries)}")

    def add_salary(self):
        """Открывает диалог добавления записи о зарплате."""
        dialog = SalaryDialog(self, self.employee_service, self.user)
        dialog.setWindowTitle("Добавить выплату")
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                data = dialog.get_data()
                salary_id = self.salary_service.create_salary(self.user, data)
                self.show_info("Успех", f"Запись добавлена (ID: {salary_id})")
                self.load_data()
            except ValidationError as e:
                self.show_error("Ошибка валидации", e.message)
            except PermissionDeniedError as e:
                self.show_error("Доступ запрещен", str(e))
            except Exception as e:
                logging.error(f"Ошибка добавления: {e}", exc_info=True)
                self.show_error("Ошибка", f"Не удалось добавить запись:\n{e}")

    def edit_salary(self):
        """Открывает диалог редактирования записи о зарплате."""
        salary_id = self.get_selected_row_id()
        if not salary_id:
            return
        
        try:
            salary = self.salary_service.get_salary_by_id(self.user, salary_id)
            if not salary:
                self.show_error("Ошибка", "Запись не найдена")
                return
            
            dialog = SalaryDialog(self, self.employee_service, self.user, salary)
            dialog.setWindowTitle("Редактировать выплату")
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                data = dialog.get_data()
                self.salary_service.update_salary(self.user, salary_id, data)
                self.show_info("Успех", "Данные обновлены")
                self.load_data()
                
        except ValidationError as e:
            self.show_error("Ошибка валидации", e.message)
        except Exception as e:
            logging.error(f"Ошибка редактирования: {e}", exc_info=True)
            self.show_error("Ошибка", f"Не удалось обновить данные:\n{e}")

    def delete_salary(self):
        """Удаляет выбранную запись о зарплате."""
        salary_id = self.get_selected_row_id()
        if not salary_id:
            return
        
        if not self.confirm_action(
            "Подтверждение",
            f"Вы уверены, что хотите удалить запись с ID {salary_id}?"
        ):
            return
        
        try:
            self.salary_service.delete_salary(self.user, salary_id)
            self.show_info("Успех", "Запись удалена")
            self.load_data()
        except EntityNotFoundError:
            self.show_error("Ошибка", "Запись не найдена")
        except PermissionDeniedError as e:
            self.show_error("Доступ запрещен", str(e))
        except Exception as e:
            logging.error(f"Ошибка удаления: {e}", exc_info=True)
            self.show_error("Ошибка", f"Не удалось удалить запись:\n{e}")

    def _get_export_filename(self, extension: str) -> str:
        return f"salaries.{extension}"

    def _get_export_title(self) -> str:
        return "Зарплатные выплаты"


class SalaryDialog(QDialog):
    """Диалог добавления/редактирования записи о зарплате."""
    
    def __init__(
        self, 
        parent, 
        employee_service: EmployeeService,
        user: dict,
        salary: Optional[Salary] = None
    ):
        super().__init__(parent)
        self.employee_service = employee_service
        self.user = user
        self.salary = salary
        
        self.setMinimumWidth(400)
        self.init_ui()
        
        if salary:
            self._load_data()
    
    def init_ui(self):
        """Инициализирует интерфейс диалога."""
        layout = QFormLayout()
        
        self.employee_combo = QComboBox()
        self._load_employees()
        
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0.01, 999999999.99)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setSuffix(" ₽")
        self.amount_spin.setValue(50000.00)
        
        self.type_combo = QComboBox()
        for type_key, type_name in PAYMENT_TYPE_MAP.items():
            self.type_combo.addItem(type_name, type_key)
        
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("Комментарий к выплате")
        self.description_edit.setMaximumHeight(80)
        
        layout.addRow("Сотрудник*:", self.employee_combo)
        layout.addRow("Сумма*:", self.amount_spin)
        layout.addRow("Тип выплаты:", self.type_combo)
        layout.addRow("Дата выплаты:", self.date_edit)
        layout.addRow("Комментарий:", self.description_edit)
        
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
    
    def _load_employees(self):
        """Загружает список сотрудников."""
        self.employee_combo.clear()
        
        try:
            employees = self.employee_service.get_employees(self.user, {})
            for emp in employees:
                name = f"{emp.last_name} {emp.first_name}"
                self.employee_combo.addItem(name, emp.employee_id)
        except Exception as e:
            logging.error(f"Ошибка загрузки сотрудников: {e}")
    
    def _load_data(self):
        """Загружает данные записи в форму."""
        if self.salary:
            # Сотрудник
            index = self.employee_combo.findData(self.salary.employee_id)
            if index >= 0:
                self.employee_combo.setCurrentIndex(index)
            
            # Сумма
            self.amount_spin.setValue(float(self.salary.salary_amount))
            
            # Тип выплаты
            index = self.type_combo.findData(self.salary.payment_type)
            if index >= 0:
                self.type_combo.setCurrentIndex(index)
            
            # Дата
            if self.salary.effective_date:
                self.date_edit.setDate(QDate(
                    self.salary.effective_date.year,
                    self.salary.effective_date.month,
                    self.salary.effective_date.day
                ))
            
            # Описание
            self.description_edit.setPlainText(self.salary.description or "")
    
    def get_data(self) -> dict:
        """Возвращает данные из формы."""
        effective_date = self.date_edit.date()
        
        return {
            # Ключ 'amount' — контракт SalaryService.create_salary;
            # раньше сюда уходил 'salary_amount', из-за чего создание
            # записи всегда падало с ValidationError "Сумма обязательна"
            'employee_id': self.employee_combo.currentData(),
            'amount': self.amount_spin.value(),
            'payment_type': self.type_combo.currentData(),
            'effective_date': date(effective_date.year(), effective_date.month(), effective_date.day()),
            'description': self.description_edit.toPlainText().strip() or None
        }
