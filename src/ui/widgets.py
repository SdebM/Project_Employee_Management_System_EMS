"""Переиспользуемые виджеты UI.

Содержит компоненты для построения интерфейса:

- :class:`DataTableWidget` - стилизованная таблица данных
- :class:`SearchPanel` - панель поиска с фильтрами
- :class:`ControlPanel` - панель кнопок управления
- :class:`ExportPanel` - панель экспорта
- :class:`RefreshButton` - кнопка обновления

Пример использования:
    ::
    
        # Создание таблицы
        table = DataTableWidget(['ID', 'Имя', 'Отдел'])
        table.populate(data_list)
        table.row_double_clicked.connect(self.on_edit)
        
        # Панель поиска
        search = SearchPanel()
        search.add_text_field('name', 'Имя')
        search.add_combo_field('dept', 'Отдел', departments)
        search.search_triggered.connect(self.load_data)

См. также:
    - :mod:`ui.base_tab` - базовый класс вкладки
"""

from typing import List, Optional
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLineEdit,
    QComboBox,
    QLabel,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon

from styles import TABLE_STYLES, BUTTON_STYLES


class DataTableWidget(QTableWidget):
    """Стилизованная таблица для отображения данных.
    
    Предоставляет:
    - Автоматическое применение стилей
    - Настройка растягивания колонок
    - Альтернативная окраска строк
    
    Пример:
        table = DataTableWidget(columns=['ID', 'Имя', 'Отдел'])
        table.populate(data_list)
    """
    
    row_double_clicked = pyqtSignal(int)  # Сигнал при двойном клике

    def __init__(self, columns: List[str], parent: QWidget = None):
        """
        Args:
            columns: Список названий колонок
            parent: Родительский виджет
        """
        super().__init__(parent)
        self.columns = columns
        self._setup_table()

    def _setup_table(self):
        """Настраивает таблицу."""
        self.setColumnCount(len(self.columns))
        self.setHorizontalHeaderLabels(self.columns)
        
        # Равномерное растягивание всех колонок
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # Стили
        self.setStyleSheet(TABLE_STYLES.get("base", ""))
        self.horizontalHeader().setStyleSheet(TABLE_STYLES.get("header", ""))
        
        # Настройки
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        # Сигнал двойного клика
        self.doubleClicked.connect(self._on_double_click)

    def populate(self, data: List[List[str]], id_column: int = 0):
        """Заполняет таблицу данными.
        
        Args:
            data: Список списков со значениями строк
            id_column: Индекс колонки с ID (для сортировки)
        """
        self.setRowCount(len(data))
        
        for row_idx, row_data in enumerate(data):
            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(str(value) if value is not None else "")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(row_idx, col_idx, item)

    def clear_data(self):
        """Очищает данные таблицы."""
        self.setRowCount(0)

    def get_selected_row_data(self) -> Optional[List[str]]:
        """Возвращает данные выбранной строки.
        
        Returns:
            Список значений строки или None
        """
        row = self.currentRow()
        if row == -1:
            return None
        
        return [
            self.item(row, col).text() if self.item(row, col) else ""
            for col in range(self.columnCount())
        ]

    def _on_double_click(self, index):
        """Обработчик двойного клика."""
        self.row_double_clicked.emit(index.row())


class SearchPanel(QWidget):
    """Панель поиска с полями фильтрации.
    
    Пример:
        search = SearchPanel()
        search.add_text_field('name', 'Имя')
        search.add_combo_field('department', 'Отдел', departments)
        search.search_triggered.connect(self.load_data)
    """
    
    search_triggered = pyqtSignal()  # Сигнал при изменении фильтров

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.fields = {}
        self._layout = QHBoxLayout()
        self._layout.addWidget(QLabel("Фильтры:"))
        self.setLayout(self._layout)

    def add_text_field(self, name: str, placeholder: str) -> QLineEdit:
        """Добавляет текстовое поле поиска.
        
        Args:
            name: Имя поля (для получения значения)
            placeholder: Текст-подсказка
            
        Returns:
            Созданное поле ввода
        """
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.textChanged.connect(lambda: self.search_triggered.emit())
        
        self.fields[name] = field
        self._layout.addWidget(field)
        return field

    def add_combo_field(
        self, 
        name: str, 
        label: str, 
        items: List[tuple]
    ) -> QComboBox:
        """Добавляет выпадающий список.
        
        Args:
            name: Имя поля
            label: Подпись
            items: Список кортежей (text, data)
            
        Returns:
            Созданный ComboBox
        """
        combo = QComboBox()
        combo.addItem("Все", None)
        for text, data in items:
            combo.addItem(text, data)
        combo.currentIndexChanged.connect(lambda: self.search_triggered.emit())
        
        self.fields[name] = combo
        self._layout.addWidget(QLabel(label + ":"))
        self._layout.addWidget(combo)
        return combo

    def get_filters(self) -> dict:
        """Возвращает словарь с текущими значениями фильтров.
        
        Returns:
            Словарь {name: value}
        """
        filters = {}
        for name, widget in self.fields.items():
            if isinstance(widget, QLineEdit):
                value = widget.text().strip()
                if value:
                    filters[name] = value
            elif isinstance(widget, QComboBox):
                data = widget.currentData()
                if data is not None:
                    filters[name] = data
        return filters

    def clear(self):
        """Очищает все поля фильтров."""
        for widget in self.fields.values():
            if isinstance(widget, QLineEdit):
                widget.clear()
            elif isinstance(widget, QComboBox):
                widget.setCurrentIndex(0)


class ExportPanel(QWidget):
    """Панель с кнопками экспорта.
    
    Пример:
        export = ExportPanel()
        export.excel_clicked.connect(self.export_excel)
        export.pdf_clicked.connect(self.export_pdf)
    """
    
    excel_clicked = pyqtSignal()
    pdf_clicked = pyqtSignal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_excel = QPushButton("Экспорт в Excel")
        self.btn_pdf = QPushButton("Экспорт в PDF")
        
        self.btn_excel.setStyleSheet(BUTTON_STYLES.get("export", ""))
        self.btn_pdf.setStyleSheet(BUTTON_STYLES.get("pdf", ""))
        
        self.btn_excel.clicked.connect(self.excel_clicked.emit)
        self.btn_pdf.clicked.connect(self.pdf_clicked.emit)
        
        layout.addStretch()
        layout.addWidget(self.btn_excel)
        layout.addWidget(self.btn_pdf)
        
        self.setLayout(layout)

    def set_visible(self, visible: bool):
        """Устанавливает видимость панели."""
        self.btn_excel.setVisible(visible)
        self.btn_pdf.setVisible(visible)


class RefreshButton(QPushButton):
    """Кнопка обновления данных."""
    
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setIcon(QIcon.fromTheme("view-refresh"))
        self.setToolTip("Обновить данные")
        self.setFixedSize(32, 32)


class ControlPanel(QWidget):
    """Панель управления с кнопками CRUD.
    
    Пример:
        panel = ControlPanel()
        panel.add_clicked.connect(self.add_item)
        panel.edit_clicked.connect(self.edit_item)
        panel.delete_clicked.connect(self.delete_item)
    """
    
    add_clicked = pyqtSignal()
    edit_clicked = pyqtSignal()
    delete_clicked = pyqtSignal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_add = QPushButton("Добавить")
        self.btn_edit = QPushButton("Редактировать")
        self.btn_delete = QPushButton("Удалить")
        
        self.btn_add.setStyleSheet(BUTTON_STYLES.get("primary", ""))
        self.btn_edit.setStyleSheet(BUTTON_STYLES.get("secondary", ""))
        self.btn_delete.setStyleSheet(BUTTON_STYLES.get("secondary", ""))
        
        self.btn_add.clicked.connect(self.add_clicked.emit)
        self.btn_edit.clicked.connect(self.edit_clicked.emit)
        self.btn_delete.clicked.connect(self.delete_clicked.emit)
        
        layout.addWidget(self.btn_add)
        layout.addWidget(self.btn_edit)
        layout.addWidget(self.btn_delete)
        layout.addStretch()
        
        self.setLayout(layout)

    def set_buttons_visible(self, add: bool = True, edit: bool = True, delete: bool = True):
        """Устанавливает видимость кнопок."""
        self.btn_add.setVisible(add)
        self.btn_edit.setVisible(edit)
        self.btn_delete.setVisible(delete)
