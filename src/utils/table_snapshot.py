"""Снимок QTableWidget для безопасного экспорта из фонового потока.

Модуль не зависит от PyQt6, поэтому импортируется из любого слоя
(в том числе из сервисов/экспортеров) без нарушения слоистой архитектуры.
"""

class _HeaderItem:
    """Минимальная имитация QTableWidgetItem для заголовка."""

    def __init__(self, text: str):
        self._text = text

    def text(self) -> str:
        return self._text


class _CellItem:
    """Минимальная имитация QTableWidgetItem для ячейки."""

    def __init__(self, text: str):
        self._text = text

    def text(self) -> str:
        return self._text


class TableSnapshot:
    """Неизменяемый снимок содержимого QTableWidget (заголовки + строки).

    Экспортеры (services.export_service) работают с таблицей через
    минимальный интерфейс QTableWidget: rowCount(), columnCount(),
    horizontalHeaderItem(i), item(row, col). Снимок реализует тот же
    интерфейс, поэтому экспорт можно выполнять в фоновом QThread без
    обращения к GUI-объектам: чтение виджетов из другого потока
    запрещено в Qt и приводило к недетерминированным падениям
    (QThread читал QTableWidget напрямую).

    Создавайте снимок ТОЛЬКО в GUI-потоке: TableSnapshot.from_table(table),
    после чего передавайте объект в фоновую задачу.
    """

    def __init__(self, headers, rows):
        self._headers = list(headers)
        self._rows = [list(r) for r in rows]

    @classmethod
    def from_table(cls, table) -> "TableSnapshot":
        """Снимает копию данных QTableWidget (вызывать в GUI-потоке!)."""
        headers = []
        for i in range(table.columnCount()):
            header = table.horizontalHeaderItem(i)
            headers.append(header.text() if header else "")

        rows = []
        for r in range(table.rowCount()):
            row_data = []
            for c in range(table.columnCount()):
                cell = table.item(r, c)
                row_data.append(cell.text() if cell else "")
            rows.append(row_data)

        return cls(headers, rows)

    # --- Интерфейс, совместимый с QTableWidget (для экспортеров) ---

    def rowCount(self) -> int:
        return len(self._rows)

    def columnCount(self) -> int:
        return len(self._headers)

    def horizontalHeaderItem(self, column: int):
        if 0 <= column < len(self._headers):
            return _HeaderItem(self._headers[column])
        return None

    def item(self, row: int, column: int):
        if 0 <= row < len(self._rows) and 0 <= column < len(self._rows[row]):
            return _CellItem(self._rows[row][column])
        return None
