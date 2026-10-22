from typing import Optional, List
from datetime import date
import logging

from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QLineEdit,
    QComboBox,
    QLabel,
    QMessageBox,
    QDialog,
    QFormLayout,
    QDialogButtonBox,
    QHeaderView,
    QDateEdit,
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QIcon

from ui.base_tab import BaseTab
from services.employee_service import EmployeeService
from services.department_service import DepartmentService
from core.permissions import Permission
from core.exceptions import ValidationError, EntityNotFoundError, PermissionDeniedError
from models.employees import Employee
from styles import TABLE_STYLES, BUTTON_STYLES
from utils.formatters import Formatters


class EmployeeDialog(QDialog):
    """Диалог добавления/редактирования сотрудника.
    
    Поля ИНН/СНИЛС/Паспорт доступны для просмотра и редактирования только
    при наличии права Permission.VIEW_CONFIDENTIAL (роль admin).
    Без этого права поля показываются замаскированными и только для чтения,
    а их значения исключаются из результата get_data(), чтобы замаскированные
    строки не перезаписали реальные данные в БД.
    """

    def __init__(self, parent, departments, employee: Optional[Employee] = None,
                 can_view_confidential: bool = False):
        super().__init__(parent)
        self.can_view_confidential = can_view_confidential
        self.setWindowTitle("Добавить сотрудника" if not employee else "Редактировать сотрудника")
        self.layout = QFormLayout(self)

        self.first_name = QLineEdit()
        self.last_name = QLineEdit()

        # Даты — QDateEdit с календарём. Раньше это были свободные текстовые
        # поля: неверный формат или пустое значение молча превращались в NULL,
        # и INSERT падал с нарушением NOT NULL без понятного сообщения.
        self.date_of_birth = QDateEdit()
        self.date_of_birth.setCalendarPopup(True)
        self.date_of_birth.setDisplayFormat("dd.MM.yyyy")
        self.date_of_birth.setDate(QDate(1990, 1, 1))
        self.date_of_birth.setMaximumDate(QDate.currentDate())

        self.gender = QComboBox()
        self.gender.addItems(["М", "Ж"])

        self.hire_date = QDateEdit()
        self.hire_date.setCalendarPopup(True)
        self.hire_date.setDisplayFormat("dd.MM.yyyy")
        self.hire_date.setDate(QDate.currentDate())
        self.department = QComboBox()
        self.department.addItem("Не указан", None)
        for d_id, d_name in departments:
            self.department.addItem(d_name, d_id)
            
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.inn = QLineEdit()
        self.snils = QLineEdit()
        self.passport = QLineEdit()
        
        # Персональные данные: только для чтения без права VIEW_CONFIDENTIAL
        if not self.can_view_confidential:
            for field in (self.inn, self.snils, self.passport):
                field.setReadOnly(True)
                field.setPlaceholderText("Нет права просмотра")

        self.layout.addRow("Имя:", self.first_name)
        self.layout.addRow("Фамилия:", self.last_name)
        self.layout.addRow("Дата рождения:", self.date_of_birth)
        self.layout.addRow("Пол:", self.gender)
        self.layout.addRow("Дата приема:", self.hire_date)
        self.layout.addRow("Отдел:", self.department)
        self.layout.addRow("Телефон:", self.phone)
        self.layout.addRow("Email:", self.email)
        self.layout.addRow("ИНН:", self.inn)
        self.layout.addRow("СНИЛС:", self.snils)
        self.layout.addRow("Паспорт:", self.passport)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.layout.addRow(buttons)

        if employee:
            self._load_data(employee)

    @staticmethod
    def _to_qdate(value) -> QDate:
        """datetime.date | None -> QDate (None -> текущая дата)."""
        if isinstance(value, date):
            return QDate(value.year, value.month, value.day)
        return QDate.currentDate()

    def _load_data(self, emp: Employee):
        self.first_name.setText(emp.first_name)
        self.last_name.setText(emp.last_name)
        self.date_of_birth.setDate(self._to_qdate(emp.date_of_birth))
        self.gender.setCurrentText(emp.gender or "М")
        self.hire_date.setDate(self._to_qdate(emp.hire_date))
        if emp.department_id:
            for i in range(self.department.count()):
                if self.department.itemData(i) == emp.department_id:
                    self.department.setCurrentIndex(i)
                    break
        self.phone.setText(emp.phone or "")
        # ИЗМЕНЕНИЕ (HF-6): email раньше не заполнялся вообще — при открытии
        # диалога поле было пустым даже при наличии email в БД, а повторное
        # сохранение стирало существующий адрес (get_data() отдавал None).
        self.email.setText(emp.email or "")
        # Конфиденциальные поля: без права VIEW_CONFIDENTIAL показываем маску
        # (значения в диалог приходят уже замаскированными из сервиса)
        if self.can_view_confidential:
            self.inn.setText(emp.inn or "")
            self.snils.setText(emp.snils or "")
            self.passport.setText(emp.passport or "")
        else:
            self.inn.setText(Formatters.mask_confidential(emp.inn))
            self.snils.setText(Formatters.mask_confidential(emp.snils))
            self.passport.setText(Formatters.mask_confidential(emp.passport))

    def get_data(self):
        data = {
            'first_name': self.first_name.text().strip(),
            'last_name': self.last_name.text().strip(),
            'gender': self.gender.currentText(),
            'department_id': self.department.currentData(),
            'phone': self.phone.text().strip() or None,
            'email': self.email.text().strip() or None,
        }
        # Без права VIEW_CONFIDENTIAL ПДн не включаем в результат:
        # в полях может быть маска, и она не должна уйти в БД.
        # Отсутствие ключей сохранит прежние значения (setattr по hasattr).
        if self.can_view_confidential:
            data['inn'] = self.inn.text().strip() or None
            data['snils'] = self.snils.text().strip() or None
            data['passport'] = self.passport.text().strip() or None

        # Даты включаются ВСЕГДА (QDateEdit не даёт ввести пустоту/мусор):
        # date_of_birth NOT NULL в БД, раньше пустое поле молча давало NULL
        # и SQL-ошибку без объяснения.
        dob = self.date_of_birth.date()
        data['date_of_birth'] = date(dob.year(), dob.month(), dob.day())
        hd = self.hire_date.date()
        data['hire_date'] = date(hd.year(), hd.month(), hd.day())
        return data


class EmployeesTabNew(BaseTab):
    DELETE_ACTION_TEXT = "Уволить"
    DELETE_CONFIRM_TITLE = "Увольнение сотрудника"
    DELETE_CONFIRM_MESSAGE = "Вы уверены, что хотите уволить сотрудника с ID {id}?\nЗапись будет помечена как уволенная и скрыта из списка."

    BUTTON_PERMISSIONS = {
        'btn_add': Permission.CREATE_EMPLOYEE,
        'btn_edit': Permission.EDIT_EMPLOYEE,
        'btn_delete': Permission.DELETE_EMPLOYEE, # Привязка права к кнопке "Уволить"
        'btn_export_excel': Permission.EXPORT_DATA,
        'btn_export_pdf': Permission.EXPORT_DATA,
    }

    def __init__(self, employee_service: EmployeeService, department_service: DepartmentService, user: dict):
        super().__init__(employee_service, user)
        self.employee_service = employee_service
        self.department_service = department_service
        
        self.init_ui()
        self.setup_access_control()
        self.load_data()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.addLayout(self._create_control_panel())
        main_layout.addLayout(self._create_search_panel())
        self.main_table = self._create_table()
        main_layout.addWidget(self.main_table)
        main_layout.addLayout(self._create_bottom_panel())
        self.setLayout(main_layout)
        self._connect_signals()

    def _create_control_panel(self) -> QHBoxLayout:
        panel = QHBoxLayout()
        self.btn_add = QPushButton("Добавить")
        self.btn_edit = QPushButton("Редактировать")
        self.btn_delete = QPushButton(self.DELETE_ACTION_TEXT)
        
        self.btn_add.setStyleSheet(BUTTON_STYLES.get("primary", ""))
        self.btn_edit.setStyleSheet(BUTTON_STYLES.get("secondary", ""))
        self.btn_delete.setStyleSheet(BUTTON_STYLES.get("danger", "")) # Красная кнопка для увольнения
        
        panel.addWidget(self.btn_add)
        panel.addWidget(self.btn_edit)
        panel.addWidget(self.btn_delete)
        panel.addStretch()
        return panel

    def _create_search_panel(self) -> QHBoxLayout:
        panel = QHBoxLayout()
        self.search_first_name = QLineEdit()
        self.search_first_name.setPlaceholderText("Имя")
        self.search_last_name = QLineEdit()
        self.search_last_name.setPlaceholderText("Фамилия")
        self.department_combo = QComboBox()
        self._load_departments()
        panel.addWidget(QLabel("Фильтры:"))
        panel.addWidget(self.search_first_name)
        panel.addWidget(self.search_last_name)
        panel.addWidget(self.department_combo)
        panel.addStretch()
        return panel

    def _create_table(self) -> QTableWidget:
        table = QTableWidget()
        # ИЗМЕНЕНИЕ (HF-6): добавлены колонки Телефон/Email/ИНН/СНИЛС/Паспорт.
        # ПДн приходят из сервиса уже замаскированными для ролей без
        # VIEW_CONFIDENTIAL (см. EmployeeService._mask_confidential).
        columns = ["ID", "Имя", "Фамилия", "Дата рождения", "Пол", "Дата приема",
                   "Отдел", "Телефон", "Email", "ИНН", "СНИЛС", "Паспорт", "Статус"]
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)

        # Равномерное растяжение всех колонок по ширине таблицы,
        # кроме ID — фиксированная узкая колонка.
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, 50)

        table.setStyleSheet(TABLE_STYLES.get("base", ""))
        header.setStyleSheet(TABLE_STYLES.get("header", ""))
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setMinimumHeight(400)
        return table

    def _create_bottom_panel(self) -> QHBoxLayout:
        panel = QHBoxLayout()
        self.btn_refresh = QPushButton()
        self.btn_refresh.setIcon(QIcon.fromTheme("view-refresh"))
        self.btn_refresh.setToolTip("Обновить данные")
        self.btn_refresh.setFixedSize(32, 32)
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
        self.btn_add.clicked.connect(self.add_employee)
        self.btn_edit.clicked.connect(self.edit_employee)
        self.btn_delete.clicked.connect(self.delete_employee)
        self.btn_refresh.clicked.connect(self.load_data)
        self.btn_export_excel.clicked.connect(self.export_to_excel)
        self.btn_export_pdf.clicked.connect(self.export_to_pdf)
        self.search_first_name.textChanged.connect(self.trigger_search)
        self.search_last_name.textChanged.connect(self.trigger_search)
        self.department_combo.currentIndexChanged.connect(self.trigger_search)
        self.main_table.doubleClicked.connect(self.show_employee_details)

    def _load_departments(self):
        try:
            departments = self.department_service.get_departments_for_dropdown()
            self.department_combo.clear()
            self.department_combo.addItem("Все отделы", None)
            for dept_id, dept_name in departments:
                self.department_combo.addItem(dept_name, dept_id)
        except Exception as e:
            logging.error(f"Ошибка загрузки отделов: {e}")

    def load_data(self):
        filters = {}
        if self.search_first_name.text().strip(): filters['first_name'] = self.search_first_name.text().strip()
        if self.search_last_name.text().strip(): filters['last_name'] = self.search_last_name.text().strip()
        if self.department_combo.currentData(): filters['department_id'] = self.department_combo.currentData()

        def fetch_task():
            return self.employee_service.get_employees(self.user, filters)

        def on_success(employees):
            self._populate_table(employees)

        self.run_in_background(fetch_task, on_success)

    def _populate_table(self, employees: List[Employee]):
        self.main_table.setRowCount(len(employees))
        for row, emp in enumerate(employees):
            self.main_table.setItem(row, 0, QTableWidgetItem(str(emp.employee_id)))
            self.main_table.setItem(row, 1, QTableWidgetItem(emp.first_name))
            self.main_table.setItem(row, 2, QTableWidgetItem(emp.last_name))
            self.main_table.setItem(row, 3, QTableWidgetItem(Formatters.format_date(emp.date_of_birth)))
            self.main_table.setItem(row, 4, QTableWidgetItem(emp.gender))
            self.main_table.setItem(row, 5, QTableWidgetItem(Formatters.format_date(emp.hire_date)))
            self.main_table.setItem(row, 6, QTableWidgetItem(emp.department_name or ""))
            # HF-6: контакты и ПДн (для не-админа — замаскированные сервисом)
            self.main_table.setItem(row, 7, QTableWidgetItem(emp.phone or ""))
            self.main_table.setItem(row, 8, QTableWidgetItem(emp.email or ""))
            self.main_table.setItem(row, 9, QTableWidgetItem(emp.inn or ""))
            self.main_table.setItem(row, 10, QTableWidgetItem(emp.snils or ""))
            self.main_table.setItem(row, 11, QTableWidgetItem(emp.passport or ""))
            self.main_table.setItem(row, 12, QTableWidgetItem(Formatters.format_status(emp.status)))
            for col in range(self.main_table.columnCount()):
                item = self.main_table.item(row, col)
                if item: item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def add_employee(self):
        try:
            departments = self.department_service.get_departments_for_dropdown()
            can_view_confidential = self.permission_manager.has_permission(
                Permission.VIEW_CONFIDENTIAL
            )
            dialog = EmployeeDialog(
                self, departments,
                can_view_confidential=can_view_confidential
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                data = dialog.get_data()
                employee_id = self.employee_service.create_employee(self.user, data)
                self.show_info("Успех", f"Сотрудник добавлен (ID: {employee_id})")
                self.load_data()
        except ValidationError as e:
            self.show_error("Ошибка валидации", e.message)
        except PermissionDeniedError as e:
            self.show_error("Доступ запрещен", str(e))
        except Exception as e:
            logging.error(f"Ошибка добавления: {e}", exc_info=True)
            # Показываем причину: без неё «Не удалось добавить» не даёт
            # понять, что не так (например, нет IDENTITY у employee_id в БД).
            self.show_error("Ошибка", f"Не удалось добавить сотрудника:\n{e}")

    def edit_employee(self):
        employee_id = self.get_selected_row_id()
        if not employee_id: return
        try:
            employee = self.employee_service.get_employee_by_id(self.user, employee_id)
            if not employee:
                self.show_error("Ошибка", "Сотрудник не найден")
                return
            departments = self.department_service.get_departments_for_dropdown()
            can_view_confidential = self.permission_manager.has_permission(
                Permission.VIEW_CONFIDENTIAL
            )
            dialog = EmployeeDialog(
                self, departments, employee=employee,
                can_view_confidential=can_view_confidential
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                data = dialog.get_data()
                self.employee_service.update_employee(self.user, employee_id, data)
                self.show_info("Успех", "Данные сотрудника обновлены")
                self.load_data()
        except ValidationError as e:
            self.show_error("Ошибка валидации", e.message)
        except Exception as e:
            logging.error(f"Ошибка редактирования: {e}", exc_info=True)
            self.show_error("Ошибка", f"Не удалось обновить данные:\n{e}")

    def delete_employee(self):
        employee_id = self.get_selected_row_id()
        if not employee_id: return
        
        if not self.confirm_delete(employee_id): return
        
        try:
            # Сервис вызывает repository.delete(), 
            # а репозиторий меняет статус на 'fired'
            self.employee_service.delete_employee(self.user, employee_id)
            self.show_info("Успех", "Сотрудник уволен")
            self.load_data()
        except EntityNotFoundError:
            self.show_error("Ошибка", "Сотрудник не найден")
        except PermissionDeniedError as e:
            self.show_error("Доступ запрещен", str(e))
        except Exception as e:
            logging.error(f"Ошибка увольнения: {e}", exc_info=True)
            self.show_error("Ошибка", f"Не удалось уволить сотрудника:\n{e}")

    def show_employee_details(self):
        employee_id = self.get_selected_row_id()
        if not employee_id: return
        try:
            employee = self.employee_service.get_employee_by_id(self.user, employee_id)
            if employee:
                # HF-6: в карточке теперь видны контакты и ПДн
                # (для ролей без VIEW_CONFIDENTIAL — замаскированные)
                details = (
                    f"<b>ID:</b> {employee.employee_id}<br>"
                    f"<b>Имя:</b> {employee.first_name}<br>"
                    f"<b>Фамилия:</b> {employee.last_name}<br>"
                    f"<b>Дата рождения:</b> {Formatters.format_date(employee.date_of_birth)}<br>"
                    f"<b>Пол:</b> {employee.gender}<br>"
                    f"<b>Дата приема:</b> {Formatters.format_date(employee.hire_date)}<br>"
                    f"<b>Отдел:</b> {employee.department_name or ''}<br>"
                    f"<b>Телефон:</b> {employee.phone or '—'}<br>"
                    f"<b>Email:</b> {employee.email or '—'}<br>"
                    f"<b>ИНН:</b> {employee.inn or '—'}<br>"
                    f"<b>СНИЛС:</b> {employee.snils or '—'}<br>"
                    f"<b>Паспорт:</b> {employee.passport or '—'}<br>"
                    f"<b>Статус:</b> {Formatters.format_status(employee.status)}<br>"
                )
                QMessageBox.information(self, "Детали сотрудника", details)
        except Exception as e:
            logging.error(f"Ошибка просмотра: {e}")

    def _get_export_filename(self, extension: str) -> str: 
        return f"employees.{extension}"
    def _get_export_title(self) -> str: 
        return "Список сотрудников"