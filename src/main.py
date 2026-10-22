"""Главный модуль приложения - точка входа.

Этот модуль является точкой входа в приложение Employee Management System.
Он инициализирует Qt-приложение, выполняет аутентификацию пользователя
и запускает главное окно.

Пример запуска:
    ::
    
        python -m src.main

Модуль использует:
    - :class:`app.Application` - DI-контейнер приложения
    - :mod:`core.exceptions` - обработка ошибок
    - PyQt6 для графического интерфейса

См. также:
    - :mod:`app` - контейнер зависимостей
    - :mod:`core.database` - работа с БД
"""

import sys
import logging
from pathlib import Path
from datetime import datetime

# Добавляем пути проекта в sys.path для корректных импортов
# при запуске файла напрямую или как модуля.
SRC_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SRC_DIR.parent

for path in (PROJECT_ROOT, SRC_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QDialog,
    QMessageBox,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QTabWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QFormLayout,
)
from PyQt6.QtCore import Qt

# Новая архитектура
from src.app import Application
from src.core.exceptions import AuthenticationError, DatabaseError
from src.styles import TAB_STYLES


class LoginDialog(QDialog):
    """Диалог авторизации пользователя."""
    
    def __init__(self, auth_service):
        super().__init__()
        self.auth_service = auth_service
        self.user = None
        self._init_ui()
    
    def _init_ui(self):
        """Инициализация интерфейса."""
        self.setWindowTitle("Авторизация")
        self.setFixedSize(350, 180)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        
        layout = QVBoxLayout(self)
        
        # Форма
        form_layout = QFormLayout()
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Введите логин")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Введите пароль")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        form_layout.addRow("Логин:", self.username_input)
        form_layout.addRow("Пароль:", self.password_input)
        layout.addLayout(form_layout)
        
        # Кнопки
        btn_layout = QHBoxLayout()
        self.btn_login = QPushButton("Войти")
        self.btn_login.clicked.connect(self._on_login)
        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_login)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)
        
        # Enter для входа
        self.password_input.returnPressed.connect(self._on_login)
        self.username_input.returnPressed.connect(lambda: self.password_input.setFocus())
    
    def _on_login(self):
        """Обработка входа."""
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        if not username or not password:
            QMessageBox.warning(self, "Ошибка", "Введите логин и пароль")
            return
        
        try:
            self.user = self.auth_service.authenticate(username, password)
            self.accept()
        except AuthenticationError as e:
            QMessageBox.warning(self, "Ошибка авторизации", str(e.message))
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при авторизации: {str(e)}")


class MainWindow(QMainWindow):
    """Главное окно приложения."""
    
    def __init__(self, app: Application, user: dict):
        super().__init__()
        self.app = app
        self.user = user
        self._init_ui()
    
    def _init_ui(self):
        """Инициализация интерфейса."""
        # Маркер сборки: если его не видно в заголовке окна — запущены
        # старые исходники (без HF-6: email не подтягивался в диалог
        # редактирования и колонки Телефон/Email/ИНН/СНИЛС/Паспорт
        # отсутствовали в таблице).
        self.setWindowTitle(f"Employee Management System - {self.user.get('role', 'user')} | сборка 2.1")
        self.setMinimumSize(1200, 700)
        
        # Применяем общие стили к окну
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)
        
        # Центральный виджет
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Заголовок
        header = QLabel(f"Добро пожаловать! Пользователь: {self.user.get('username', '')} | Роль: {self.user.get('role', 'user')}")
        header.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                padding: 10px;
                background-color: #1976d2;
                color: white;
                border-radius: 4px;
            }
        """)
        layout.addWidget(header)
        
        # Вкладки
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(TAB_STYLES)
        layout.addWidget(self.tabs)
        
        # Добавляем вкладки в зависимости от роли
        self._create_tabs()
    
    def _create_tabs(self):
        """Создание вкладок на основе роли пользователя."""
        from src.ui.tabs import (
            EmployeesTabNew,
            DepartmentsTab,
            ProjectsTab,
            SalariesTab,
            AnalyticsTab,
        )
        
        role = self.user.get('role', 'employee')
        
        # Вкладка сотрудников (доступна всем)
        try:
            employees_tab = EmployeesTabNew(
                self.app.employee_service,
                self.app.department_service,
                self.user
            )
            self.tabs.addTab(employees_tab, "Сотрудники")
        except Exception as e:
            logging.error(f"Ошибка создания вкладки сотрудников: {e}", exc_info=True)
            placeholder = QLabel(f"Ошибка загрузки вкладки: {e}")
            placeholder.setStyleSheet("color: red; padding: 20px;")
            self.tabs.addTab(placeholder, "Сотрудники")
        
        # Вкладки для менеджеров и админов
        if role in ('admin', 'manager'):
            try:
                departments_tab = DepartmentsTab(
                    self.app.department_service,
                    self.app.employee_service,
                    self.user
                )
                self.tabs.addTab(departments_tab, "Отделы")
            except Exception as e:
                logging.error(f"Ошибка создания вкладки отделов: {e}", exc_info=True)
                self.tabs.addTab(QLabel(f"Ошибка: {e}"), "Отделы")
            
            try:
                projects_tab = ProjectsTab(
                    self.app.project_service,
                    self.app.department_service,
                    self.user
                )
                self.tabs.addTab(projects_tab, "Проекты")
            except Exception as e:
                logging.error(f"Ошибка создания вкладки проектов: {e}", exc_info=True)
                self.tabs.addTab(QLabel(f"Ошибка: {e}"), "Проекты")
        
        # Вкладки только для администраторов
        if role == 'admin':
            try:
                salaries_tab = SalariesTab(
                    self.app.salary_service,
                    self.app.employee_service,
                    self.user
                )
                self.tabs.addTab(salaries_tab, "Зарплаты")
            except Exception as e:
                logging.error(f"Ошибка создания вкладки зарплат: {e}", exc_info=True)
                self.tabs.addTab(QLabel(f"Ошибка: {e}"), "Зарплаты")
            
            try:
                analytics_tab = AnalyticsTab(
                    self.app.analytics_service,
                    self.user
                )
                self.tabs.addTab(analytics_tab, "Аналитика")
            except Exception as e:
                logging.error(f"Ошибка создания вкладки аналитики: {e}", exc_info=True)
                self.tabs.addTab(QLabel(f"Ошибка: {e}"), "Аналитика")
            
            # Вкладка пользователей
            users_placeholder = QLabel(
                "\n\nВкладка 'Пользователи' находится в разработке.\n"
                "Управление пользователями будет добавлено позже."
            )
            users_placeholder.setStyleSheet("font-size: 12px; color: #666; padding: 20px;")
            users_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabs.addTab(users_placeholder, "Пользователи")
    
    def closeEvent(self, event):
        """Обработка закрытия окна."""
        reply = QMessageBox.question(
            self, "Выход",
            "Вы уверены, что хотите выйти?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()


def setup_logging() -> None:
    """Настраивает систему логирования приложения."""
    logging.basicConfig(
        filename=f'app_errors_{datetime.now().strftime("%Y-%m-%d")}.log',
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )


def main() -> None:
    """Главная функция приложения."""
    try:
        qt_app = QApplication(sys.argv)
        
        app = Application.get_instance()
        app.initialize()
        
        login_dialog = LoginDialog(app.auth_service)
        
        if login_dialog.exec() != QDialog.DialogCode.Accepted:
            app.shutdown()
            sys.exit(0)
        
        user = login_dialog.user
        logging.info(f"Пользователь авторизован: role={user.get('role')}")
        
        window = MainWindow(app, user)
        window.show()
        
        exit_code = qt_app.exec()
        app.shutdown()
        sys.exit(exit_code)
        
    except DatabaseError as e:
        logging.critical(f"Database error: {e.message}", exc_info=True)
        QMessageBox.critical(None, "Ошибка БД", f"Не удалось подключиться:\n{e.message}")
        sys.exit(1)
    except AuthenticationError as e:
        logging.error(f"Auth error: {e.message}")
        sys.exit(1)
    except Exception as e:
        logging.critical(f"Fatal error: {str(e)}", exc_info=True)
        try:
            Application.get_instance().shutdown()
        except Exception:
            pass
        QMessageBox.critical(None, "Ошибка", f"Непредвиденная ошибка:\n{str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
