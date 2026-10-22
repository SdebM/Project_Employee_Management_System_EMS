"""Утилиты форматирования данных.

Содержит класс :class:`Formatters` со статическими методами
для форматирования значений для отображения:

- :meth:`~Formatters.format_date` - дата ("01.02.2026")
- :meth:`~Formatters.format_datetime` - дата и время
- :meth:`~Formatters.format_money` - денежная сумма ("1 234.56 ₽")
- :meth:`~Formatters.format_phone` - телефон ("+7 (900) 123-45-67")
- :meth:`~Formatters.format_passport` - паспорт ("12 34 567890")
- :meth:`~Formatters.format_snils` - СНИЛС ("123-456-789 01")
- :meth:`~Formatters.format_status` - статус сотрудника
- :meth:`~Formatters.format_role` - роль пользователя

"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Union


class Formatters:
    """Класс с методами форматирования данных для отображения."""

    @staticmethod
    def format_date(
        value: Union[date, datetime, str, None],
        format_str: str = "%d.%m.%Y"
    ) -> str:
        """Форматирует дату для отображения.
        
        Args:
            value: Дата в любом формате
            format_str: Формат вывода
            
        Returns:
            Отформатированная строка или пустая строка
        """
        if not value:
            return ""
        
        if isinstance(value, str):
            try:
                # Пробуем распарсить ISO формат
                value = datetime.fromisoformat(value)
            except ValueError:
                return value
        
        if isinstance(value, (date, datetime)):
            return value.strftime(format_str)
        
        return str(value)

    @staticmethod
    def format_datetime(
        value: Union[datetime, str, None],
        format_str: str = "%d.%m.%Y %H:%M"
    ) -> str:
        """Форматирует дату и время."""
        return Formatters.format_date(value, format_str)

    @staticmethod
    def format_money(
        value: Union[Decimal, float, int, str, None],
        currency: str = "₽",
        decimals: int = 2
    ) -> str:
        """Форматирует денежную сумму.
        
        Args:
            value: Сумма
            currency: Символ валюты
            decimals: Количество знаков после запятой
            
        Returns:
            Отформатированная сумма (напр. "1 234 567.89 ₽")
        """
        if value is None:
            return ""
        
        try:
            num = float(value)
            # Форматирование с разделителями тысяч
            formatted = f"{num:,.{decimals}f}"
            # Заменяем запятую на пробел (русский формат)
            formatted = formatted.replace(",", " ")
            return f"{formatted} {currency}"
        except (ValueError, TypeError):
            return str(value)

    @staticmethod
    def format_phone(phone: Optional[str]) -> str:
        """Форматирует номер телефона.
        
        Преобразует "79001234567" в "+7 (900) 123-45-67"
        """
        if not phone:
            return ""
        
        # Убираем всё кроме цифр
        digits = ''.join(filter(str.isdigit, phone))
        
        if len(digits) == 11 and digits[0] in ('7', '8'):
            return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"
        elif len(digits) == 10:
            return f"+7 ({digits[0:3]}) {digits[3:6]}-{digits[6:8]}-{digits[8:10]}"
        
        return phone

    @staticmethod
    def format_passport(passport: Optional[str]) -> str:
        """Форматирует номер паспорта.
        
        Преобразует "1234567890" в "12 34 567890"
        """
        if not passport:
            return ""
        
        digits = ''.join(filter(str.isdigit, passport))
        
        if len(digits) == 10:
            return f"{digits[0:2]} {digits[2:4]} {digits[4:10]}"
        
        return passport

    @staticmethod
    def format_inn(inn: Optional[str]) -> str:
        """Форматирует ИНН с разделителями."""
        if not inn:
            return ""
        
        digits = ''.join(filter(str.isdigit, inn))
        
        if len(digits) == 12:
            return f"{digits[0:4]} {digits[4:8]} {digits[8:12]}"
        elif len(digits) == 10:
            return f"{digits[0:4]} {digits[4:10]}"
        
        return inn

    @staticmethod
    def format_snils(snils: Optional[str]) -> str:
        """Форматирует СНИЛС.
        
        Преобразует "12345678901" в "123-456-789 01"
        """
        if not snils:
            return ""
        
        digits = ''.join(filter(str.isdigit, snils))
        
        if len(digits) == 11:
            return f"{digits[0:3]}-{digits[3:6]}-{digits[6:9]} {digits[9:11]}"
        
        return snils

    @staticmethod
    def format_gender(gender: Optional[str]) -> str:
        """Преобразует код пола в полное название."""
        mapping = {
            'М': 'Мужской',
            'M': 'Мужской',  # Английская M
            'Ж': 'Женский',
            'F': 'Женский',
        }
        return mapping.get(gender, gender or "")

    @staticmethod
    def format_status(status: Optional[str]) -> str:
        """Преобразует код статуса в читаемый вид."""
        mapping = {
            # Английские коды
            'active': 'Активен',
            'inactive': 'Неактивен',
            'fired': 'Уволен',
            'planning': 'Планирование',
            'in_progress': 'В работе',
            'on_hold': 'Приостановлен',
            'completed': 'Завершен',
            'cancelled': 'Отменен',
            # Русские значения из БД
            'активен': 'Активен',
            'неактивен': 'Неактивен',
            'уволен': 'Уволен',
        }
        return mapping.get(status, status or "")

    @staticmethod
    def format_role(role: Optional[str]) -> str:
        """Преобразует код роли в читаемый вид."""
        mapping = {
            'admin': 'Администратор',
            'manager': 'Менеджер',
            'employee': 'Сотрудник',
        }
        return mapping.get(role, role or "")

    @staticmethod
    def mask_confidential(
        value: Optional[str],
        visible_tail: int = 2,
        mask_char: str = "•"
    ) -> str:
        """Маскирует конфиденциальную строку (ИНН, СНИЛС, паспорт).

        Показывает только последние ``visible_tail`` символов,
        всё остальное заменяется маской. Используется, когда у
        пользователя нет права Permission.VIEW_CONFIDENTIAL.

        Args:
            value: Исходная строка
            visible_tail: Сколько последних символов оставить открытыми
            mask_char: Символ маски

        Returns:
            Замаскированная строка, например "******67";
            пустая строка, если значение отсутствует.
        """
        if not value:
            return ""
        text = str(value)
        if len(text) <= visible_tail:
            return mask_char * len(text)
        return mask_char * (len(text) - visible_tail) + text[-visible_tail:]

    @staticmethod
    def truncate_text(text: Optional[str], max_length: int = 50) -> str:
        """Обрезает текст до указанной длины с многоточием."""
        if not text:
            return ""
        
        if len(text) <= max_length:
            return text
        
        return text[:max_length - 3] + "..."

    @staticmethod
    def format_full_name(first_name: str, last_name: str) -> str:
        """Форматирует полное имя."""
        parts = [last_name, first_name]
        return " ".join(filter(None, parts))
