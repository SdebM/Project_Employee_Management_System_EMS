"""Утилиты валидации данных.

Содержит класс :class:`Validators` со статическими методами
для проверки корректности данных:

- :meth:`~Validators.validate_required` - обязательное поле
- :meth:`~Validators.validate_email` - формат email
- :meth:`~Validators.validate_phone` - формат телефона
- :meth:`~Validators.validate_inn` - ИНН физического лица (12 цифр)
- :meth:`~Validators.validate_passport` - паспорт (10 цифр)
- :meth:`~Validators.validate_snils` - СНИЛС (11 цифр с контрольной суммой)
- :meth:`~Validators.validate_age` - минимальный возраст
- :meth:`~Validators.validate_date_range` - диапазон дат

Все методы возвращают ``(is_valid: bool, error_message: str | None)``.


"""

import re
from datetime import date


class Validators:
    """Класс с методами валидации данных.
    
    Все методы статические и возвращают (is_valid, error_message).
    """

    @staticmethod
    def validate_required(value: str, field_name: str) -> tuple:
        """Проверяет обязательное поле.
        
        Returns:
            (True, None) или (False, error_message)
        """
        if not value or not value.strip():
            return False, f"Поле '{field_name}' обязательно для заполнения"
        return True, None

    @staticmethod
    def validate_email(email: str) -> tuple:
        """Проверяет формат email."""
        if not email:
            return True, None  # Пустое значение допустимо
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            return False, "Некорректный формат email"
        return True, None

    @staticmethod
    def validate_phone(phone: str) -> tuple:
        """Проверяет формат телефона."""
        if not phone:
            return True, None
        
        # Удаляем пробелы, тире, скобки
        cleaned = re.sub(r'[\s\-\(\)]', '', phone)
        
        # Проверяем что остались только цифры и опционально +
        if not re.match(r'^\+?\d{10,15}$', cleaned):
            return False, "Некорректный формат телефона"
        return True, None

    @staticmethod
    def validate_inn(inn: str) -> tuple:
        """Проверяет формат ИНН физического лица (12 цифр)."""
        if not inn:
            return True, None
        
        if not inn.isdigit():
            return False, "ИНН должен содержать только цифры"
        
        if len(inn) != 12:
            return False, "ИНН физического лица должен содержать 12 цифр"
        
        return True, None

    @staticmethod
    def validate_passport(passport: str) -> tuple:
        """Проверяет формат паспорта (серия номер)."""
        if not passport:
            return True, None
        
        # Удаляем пробелы
        cleaned = passport.replace(' ', '')
        
        if not cleaned.isdigit() or len(cleaned) != 10:
            return False, "Паспорт должен содержать 10 цифр (серия и номер)"
        
        return True, None

    @staticmethod
    def validate_age(birth_date: date, min_age: int = 18) -> tuple:
        """Проверяет минимальный возраст.
        
        Args:
            birth_date: Дата рождения
            min_age: Минимальный возраст (по умолчанию 18)
        """
        if not birth_date:
            return True, None
        
        today = date.today()
        age = today.year - birth_date.year
        
        if (today.month, today.day) < (birth_date.month, birth_date.day):
            age -= 1
        
        if age < min_age:
            return False, f"Возраст должен быть не менее {min_age} лет"
        
        return True, None

    @staticmethod
    def validate_date_range(
        start_date: date, 
        end_date: date,
        allow_same: bool = True
    ) -> tuple:
        """Проверяет корректность диапазона дат.
        
        Args:
            start_date: Начальная дата
            end_date: Конечная дата
            allow_same: Разрешать одинаковые даты
        """
        if not start_date or not end_date:
            return True, None
        
        if allow_same:
            if end_date < start_date:
                return False, "Дата окончания не может быть раньше даты начала"
        else:
            if end_date <= start_date:
                return False, "Дата окончания должна быть позже даты начала"
        
        return True, None

    @staticmethod
    def validate_snils(snils: str) -> tuple:
        """Проверяет формат СНИЛС (XXX-XXX-XXX XX).

        Алгоритм контрольной суммы:
            Каждая из первых 9 цифр умножается на свою позицию (9, 8, ..., 1),
            сумма произведений даёт контрольное число (последние 2 цифры).
        """
        if not snils:
            return True, None

        # Удаляем разделители
        cleaned = snils.replace('-', '').replace(' ', '')

        if not cleaned.isdigit() or len(cleaned) != 11:
            return False, "СНИЛС должен содержать 11 цифр (формат: XXX-XXX-XXX XX)"

        # Контрольная сумма
        digits = [int(d) for d in cleaned]
        checksum = sum(d * (9 - i) for i, d in enumerate(digits[:9]))

        if checksum > 101:
            checksum %= 101
        if checksum in (100, 101):
            checksum = 0

        if checksum != int(cleaned[9:]):
            return False, "Неверная контрольная сумма СНИЛС"

        return True, None

    @staticmethod
    def validate_password(password: str) -> tuple:
        """Проверяет пароль по политике безопасности.

        Требования:
            - длина не менее 8 символов;
            - хотя бы одна буква (латиница или кириллица);
            - хотя бы одна цифра.

        Ранее допускался пароль из 4 любых символов, что позволяло
        пароли вида '1234' — первый кандидат при переборе.

        Args:
            password: Пароль в открытом тексте

        Returns:
            (True, None) или (False, error_message)
        """
        if not password or len(password) < 8:
            return False, "Пароль должен содержать не менее 8 символов"

        if not re.search(r'[A-Za-zА-Яа-яЁё]', password):
            return False, "Пароль должен содержать хотя бы одну букву"

        if not re.search(r'\d', password):
            return False, "Пароль должен содержать хотя бы одну цифру"

        return True, None

    @staticmethod
    def validate_positive_number(value: float, field_name: str) -> tuple:
        """Проверяет что число положительное."""
        if value is None:
            return True, None
        
        try:
            num = float(value)
            if num <= 0:
                return False, f"Поле '{field_name}' должно быть положительным числом"
        except (ValueError, TypeError):
            return False, f"Поле '{field_name}' должно быть числом"
        
        return True, None

    @staticmethod
    def validate_length(
        value: str, 
        field_name: str,
        min_length: int = None,
        max_length: int = None
    ) -> tuple:
        """Проверяет длину строки."""
        if not value:
            return True, None
        
        length = len(value)
        
        if min_length and length < min_length:
            return False, f"Поле '{field_name}' должно содержать не менее {min_length} символов"
        
        if max_length and length > max_length:
            return False, f"Поле '{field_name}' должно содержать не более {max_length} символов"
        
        return True, None
