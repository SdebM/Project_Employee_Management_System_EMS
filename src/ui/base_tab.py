from typing import Dict, Optional, Any
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QMessageBox,
    QApplication,
    QFileDialog,
)
from PyQt6.QtCore import QTimer, Qt, QThread

from core.permissions import PermissionManager, Permission
from services.export_service import ExportService
from utils.workers import BackgroundWorker
from utils.table_snapshot import TableSnapshot


class BaseTab(QWidget):
    """Базовый класс для всех вкладок приложения."""
    
    BUTTON_PERMISSIONS: Dict[str, str] = {
        'btn_add': Permission.CREATE_EMPLOYEE,
        'btn_edit': Permission.EDIT_EMPLOYEE,
        'btn_delete': Permission.DELETE_EMPLOYEE,
        'btn_export_excel': Permission.EXPORT_DATA,
        'btn_export_pdf': Permission.EXPORT_DATA,
    }

    DELETE_ACTION_TEXT = "Удалить"
    DELETE_CONFIRM_TITLE = "Подтверждение удаления"
    DELETE_CONFIRM_MESSAGE = "Вы уверены, что хотите удалить запись с ID {id}?\nЗапись будет помечена как неактивная."

    def __init__(self, service: Any, user: dict):
        super().__init__()
        self.service = service
        self.user = user
        self.permission_manager = PermissionManager(user)
        
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.load_data)
        
        self.main_table: Optional[QTableWidget] = None
        self.btn_add: Optional[QPushButton] = None
        self.btn_edit: Optional[QPushButton] = None
        self.btn_delete: Optional[QPushButton] = None
        self.btn_export_excel: Optional[QPushButton] = None
        self.btn_export_pdf: Optional[QPushButton] = None
        self.btn_refresh: Optional[QPushButton] = None

    def init_ui(self):
        raise NotImplementedError("Метод init_ui() должен быть реализован")

    def load_data(self):
        raise NotImplementedError("Метод load_data() должен быть реализован")

    def setup_access_control(self):
        for btn_name, permission in self.BUTTON_PERMISSIONS.items():
            button = getattr(self, btn_name, None)
            if button:
                has_permission = self.permission_manager.has_permission(permission)
                button.setVisible(has_permission)

    def trigger_search(self):
        self.search_timer.stop()
        self.search_timer.start(300)

    # --- Фоновые задачи (QThread) ---
    def run_in_background(self, task, on_success, on_error=None):
        """Запускает задачу в фоновом потоке и связывает с коллбэками."""
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.setEnabled(False)
        
        self._thread = QThread()
        self._worker = BackgroundWorker(task)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_task_finished(on_success))
        self._worker.error.connect(self._on_task_error(on_error))

        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def _on_task_finished(self, callback):
        def wrapper(result):
            QApplication.restoreOverrideCursor()
            self.setEnabled(True)
            callback(result)
        return wrapper

    def _on_task_error(self, callback=None):
        def wrapper(error_msg):
            QApplication.restoreOverrideCursor()
            self.setEnabled(True)
            if callback:
                callback(error_msg)
            else:
                self.show_error("Ошибка фонового процесса", error_msg)
        return wrapper

    # --- Экспорт в потоке ---
    def export_to_pdf(self):
        if not self.main_table: return
        default_name = self._get_export_filename('pdf')
        title = self._get_export_title()
        self._start_export('pdf', default_name, title)

    def export_to_excel(self):
        if not self.main_table: return
        default_name = self._get_export_filename('xlsx')
        sheet_name = self._get_export_title()
        self._start_export('excel', default_name, sheet_name)

    def _start_export(self, export_type, default_name, doc_title):
        if self.main_table.rowCount() == 0:
            self.show_warning("Внимание", "Нет данных для экспорта")
            return

        # ВАЖНО: снимаем данные таблицы В GUI-потоке. Передача QTableWidget
        # в фоновый QThread приводила к чтению виджета из другого потока —
        # это запрещено в Qt и вызывает недетерминированные падения.
        snapshot = TableSnapshot.from_table(self.main_table)

        if export_type == 'pdf':
            file_path, _ = QFileDialog.getSaveFileName(self, "Экспорт в PDF", default_name, "PDF Files (*.pdf)")
            if not file_path: return
            task = lambda: ExportService.export_to_pdf(snapshot, file_path, doc_title)
        else:
            file_path, _ = QFileDialog.getSaveFileName(self, "Экспорт в Excel", default_name, "Excel Files (*.xlsx)")
            if not file_path: return
            task = lambda: ExportService.export_to_excel(snapshot, file_path, doc_title)

        def on_success(_):
            self.show_info("Успех", f"Данные успешно экспортированы:\n{file_path}")

        def on_error(msg):
            if "Permission" in msg:
                self.show_error("Ошибка", "Нет прав для записи в выбранную директорию")
            else:
                self.show_error("Ошибка экспорта", msg)

        self.run_in_background(task, on_success, on_error)

    # --- Диалоги ---
    def show_error(self, title: str, message: str): QMessageBox.critical(self, title, message)
    def show_warning(self, title: str, message: str): QMessageBox.warning(self, title, message)
    def show_info(self, title: str, message: str): QMessageBox.information(self, title, message)

    def confirm_action(self, title: str, message: str) -> bool:
        reply = QMessageBox.question(self, title, message, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        return reply == QMessageBox.StandardButton.Yes

    def confirm_delete(self, entity_id: int) -> bool:
        msg = self.DELETE_CONFIRM_MESSAGE.format(id=entity_id)
        reply = QMessageBox.question(
            self, self.DELETE_CONFIRM_TITLE, msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes

    def get_selected_row_id(self, id_column: int = 0) -> Optional[int]:
        if not self.main_table: return None
        selected_row = self.main_table.currentRow()
        if selected_row == -1:
            self.show_warning("Внимание", "Выберите запись в таблице")
            return None
        item = self.main_table.item(selected_row, id_column)
        if item:
            try: return int(item.text())
            except ValueError: return None
        return None

    def _get_export_filename(self, extension: str) -> str: return f"export.{extension}"
    def _get_export_title(self) -> str: return "Экспорт данных"

    def _create_control_panel(self) -> QHBoxLayout:
        panel = QHBoxLayout()
        self.btn_add = QPushButton("Добавить")
        self.btn_edit = QPushButton("Редактировать")
        self.btn_delete = QPushButton(self.DELETE_ACTION_TEXT) # ИЗМЕНЕНИЕ: Используем переменную
        panel.addWidget(self.btn_add)
        panel.addWidget(self.btn_edit)
        panel.addWidget(self.btn_delete)
        panel.addStretch()
        return panel

    def _create_export_panel(self) -> QHBoxLayout:
        panel = QHBoxLayout()
        self.btn_export_excel = QPushButton("Экспорт в Excel")
        self.btn_export_pdf = QPushButton("Экспорт в PDF")
        panel.addStretch()
        panel.addWidget(self.btn_export_excel)
        panel.addWidget(self.btn_export_pdf)
        self.btn_export_excel.clicked.connect(self.export_to_excel)
        self.btn_export_pdf.clicked.connect(self.export_to_pdf)
        return panel