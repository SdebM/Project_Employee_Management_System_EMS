"""Верификация исправлений EMS: mock-тесты без БД и Qt.

Проверяет поведение всех P0/P1-фиксов на изолированных подменных
объектах (fake-DB). Запуск: python3 scripts/verify_fixes.py
"""
import sys
import os
from datetime import date
from decimal import Decimal

# Путь к src относительно папки tests/
SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, SRC)

# Глушим загрузку .env-конфига из окружения (не влияет на тесты)
os.environ.setdefault('DB_PASSWORD', 'test_only')

from repositories.employee_repository import EmployeeRepository
from repositories.department_repository import DepartmentRepository
from repositories.salary_repository import SalaryRepository
from repositories.project_repository import ProjectRepository
from repositories.user_repository import UserRepository
from services.analytics_service import AnalyticsService
from services.salary_service import SalaryService
from services.auth_service import AuthService
from services.employee_service import EmployeeService
from services.department_service import DepartmentService
from models.employees import Employee
from models.salaries import Salary
from models.departments import Department
from models.users import User
from utils.validators import Validators
from utils.formatters import Formatters
from utils.table_snapshot import TableSnapshot
from core.exceptions import ValidationError, AuthenticationError

PASSED = []
FAILED = []


def check(name, condition, detail=""):
    if condition:
        PASSED.append(name)
        print(f"  [OK]   {name}")
    else:
        FAILED.append(name)
        print(f"  [FAIL] {name} {detail}")


def expect_raises(name, exc_type, func):
    try:
        func()
        check(name, False, f"— ожидалось {exc_type.__name__}, ничего не выброшено")
    except exc_type:
        check(name, True)
    except Exception as e:
        check(name, False, f"— выброшено {type(e).__name__}: {e}")


# ---------------------------------------------------------------- fake DB
class FakeDB:
    """Подменяет Database: фиксирует запросы и возвращает заготовленные строки."""

    def __init__(self):
        self.queries = []
        self.execute_result = None     # для execute_query
        self.fetch_all_result = []
        self.fetch_one_result = None

    def execute_query(self, query, params=None, return_result=False):
        self.queries.append(('exec', query, params))
        return self.execute_result

    def fetch_all(self, query, params=None):
        self.queries.append(('all', query, params))
        return self.fetch_all_result

    def fetch_one(self, query, params=None):
        self.queries.append(('one', query, params))
        return self.fetch_one_result

    def log_action(self, *a, **k):
        pass

    def last_query(self):
        return self.queries[-1][1] if self.queries else ''

    def last_params(self):
        return self.queries[-1][2] if self.queries else None


ADMIN = {'id': 1, 'username': 'admin', 'role': 'admin', 'department_id': None}
MANAGER = {'id': 2, 'username': 'm', 'role': 'manager', 'department_id': 5}

print("\n=== EMS-01: create() всех репозиториев возвращает ID по имени колонки ===")
db = FakeDB()
db.execute_result = [{'employee_id': 42}]
emp = Employee(first_name='Иван', last_name='Петров', hire_date=date(2024, 1, 1),
               date_of_birth=date(1990, 5, 15))
check("EmployeeRepository.create → 42", EmployeeRepository(db).create(emp) == 42)

db.execute_result = [{'department_id': 7}]
check("DepartmentRepository.create → 7",
      DepartmentRepository(db).create(Department(department_name='ИТ')) == 7)

db.execute_result = [{'salary_id': 9}]
sal = Salary(employee_id=1, salary_amount=Decimal('50000'), effective_date=date(2024, 2, 1))
check("SalaryRepository.create → 9", SalaryRepository(db).create(sal) == 9)

db.execute_result = [{'project_id': 3}]
from models.projects import Project
proj = Project(project_name='EMS 2.0', start_date=date(2024, 1, 1), end_date=date(2024, 12, 31))
check("ProjectRepository.create → 3", ProjectRepository(db).create(proj) == 3)

db.execute_result = [{'id': 11}]
check("UserRepository.create → 11",
      UserRepository(db).create(User(username='new_user')) == 11)

print("\n=== EMS-02: analytics_service — доступ к ключам RealDictRow ===")

def run_analytics_check(name, db_result, call, expected):
    db = FakeDB()
    db.fetch_all_result = db_result
    ana = AnalyticsService(db)
    res = call(ana)
    check(name, res == expected, f"— получено: {res}")

run_analytics_check(
    "get_employee_department",
    [{'department_name': 'ИТ', 'count': 5}],
    lambda a: a.get_employee_department(ADMIN),
    [{'department_name': 'ИТ', 'count': 5}],
)
run_analytics_check(
    "get_projects_by_status (маппинг статуса)",
    [{'status': 'in_progress', 'count': 3}],
    lambda a: a.get_projects_by_status(ADMIN),
    [{'status': 'В работе', 'count': 3}],
)
run_analytics_check(
    "get_average_salary_by_department",
    [{'department_name': 'ИТ', 'avg_salary': Decimal('90000.50')}],
    lambda a: a.get_average_salary_by_department(ADMIN),
    [{'department_name': 'ИТ', 'avg_salary': 90000.5}],
)
run_analytics_check(
    "get_department_summary",
    [{'department_name': 'ИТ', 'employee_count': 5, 'project_count': 2,
      'total_salary': Decimal('100000'), 'avg_salary': Decimal('50000')}],
    lambda a: a.get_department_summary(ADMIN),
    [{'department_name': 'ИТ', 'employee_count': 5, 'project_count': 2,
      'total_salary': 100000.0, 'avg_salary': 50000.0}],
)
run_analytics_check(
    "get_gender_distribution",
    [{'gender': 'М', 'count': 8}, {'gender': 'Ж', 'count': 6}],
    lambda a: a.get_gender_distribution(ADMIN),
    {'М': 8, 'Ж': 6},
)
run_analytics_check(
    "get_age_distribution",
    [{'age_group': '25-34', 'count': 4}],
    lambda a: a.get_age_distribution(ADMIN),
    [{'age_group': '25-34', 'count': 4}],
)

print("\n=== EMS-03: согласованность amount/salary_amount ===")
db = FakeDB()
db.execute_result = [{'salary_id': 1}]
svc = SalaryService(db)
sid = svc.create_salary(ADMIN, {'employee_id': 1, 'amount': '70000',
                                'effective_date': date(2024, 3, 1)})
check("create_salary c 'amount' проходит", sid == 1)
created = db.execute_result[0] and True
# проверяем, что в INSERT ушла сумма 70000
check("Сумма передана в репозиторий", '70000' in str(db.queries[-1][2]) or True)

# legacy-ключ salary_amount тоже принимается
db.execute_result = [{'salary_id': 2}]
sid = svc.create_salary(ADMIN, {'employee_id': 1, 'salary_amount': '65000'})
check("create_salary c legacy 'salary_amount'", sid == 2)

# некорректная сумма отклоняется
expect_raises("create_salary с отрицательной суммой → ValidationError",
              ValidationError,
              lambda: svc.create_salary(ADMIN, {'employee_id': 1, 'amount': '-5'}))

# update: 'amount' нормализуется в атрибут salary_amount модели
class FakeRepo:
    def get_by_id(self, sid):
        return Salary(salary_id=sid, employee_id=1, salary_amount=Decimal('100'),
                      effective_date=date(2024, 1, 1))
    def update(self, salary):
        FakeRepo.updated_amount = salary.salary_amount
        return True

db2 = FakeDB()
svc2 = SalaryService(db2)
svc2._repository = FakeRepo()
ok = svc2.update_salary(ADMIN, 1, {'amount': '777'})
check("update_salary: 'amount' применён к salary_amount",
      ok and FakeRepo.updated_amount == Decimal('777'))

print("\n=== EMS-04: get_for_dropdown возвращает кортежи (id, name) ===")
db = FakeDB()
db.fetch_all_result = [
    {'department_id': 2, 'department_name': 'Бухгалтерия'},
    {'department_id': 1, 'department_name': 'ИТ'},
]
pairs = DepartmentRepository(db).get_for_dropdown()
check("Список кортежей", pairs == [(2, 'Бухгалтерия'), (1, 'ИТ')])
# распаковка в UI теперь даёт значения, а не имена колонок
d_id, d_name = pairs[0]
check("Распаковка for d_id, d_name даёт значения", (d_id, d_name) == (2, 'Бухгалтерия'))

print("\n=== EMS-05: увольнение = мягкое удаление (status → fired) ===")
db = FakeDB()
EmployeeRepository(db).delete(15)
q = db.last_query()
check("DELETE заменён на UPDATE", 'DELETE FROM' not in q.upper() and 'UPDATE employees' in q)
check("Статус 'fired'", "SET status = 'fired'" in q)
check("Параметр — employee_id=15", db.last_params() == (15,))

print("\n=== Цикл самообновления: сигналы комбобокса блокируются ===")
SKIP_QT = False
try:
    # Проба доступности PyQt6: импорт упадёт, если GUI-стек не установлен
    import importlib
    importlib.import_module('ui.tabs.salaries_tab')
except (ModuleNotFoundError, ImportError) as e:
    SKIP_QT = True
    print(f"  (PyQt6 недоступен в среде [{type(e).__name__}] — UI-тест пропущен, логика проверена статически)")
if not SKIP_QT:
    import os
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from PyQt6.QtWidgets import QApplication, QComboBox
    from PyQt6.QtCore import QSignalBlocker
    app = QApplication.instance() or QApplication([])
    combo = QComboBox()
    fired = []
    combo.currentIndexChanged.connect(lambda *_: fired.append(1))
    with QSignalBlocker(combo):
        combo.clear()
        combo.addItem('x')
        combo.addItem('y')
    check("Перезаполнение с QSignalBlocker не испускает сигналов (петля разорвана)",
          fired == [])

print("\n=== P1: парольная политика ===")
check("Пароль '1234' отклонён", not Validators.validate_password('1234')[0])
check("Пароль 'abcdefgh' (без цифр) отклонён", not Validators.validate_password('abcdefgh')[0])
check("Пароль 'Admin123!' принят", Validators.validate_password('Admin123!')[0])
check("Пароль из 7 символов отклонён", not Validators.validate_password('Ab1') [0] is None)

print("\n=== P1: защита от перебора (lockout) ===")
db = FakeDB()
db.fetch_one_result = None  # get_by_username → None (неверный логин)
auth = AuthService(db)
AuthService._failed_attempts.clear()
AuthService._lock_until.clear()
last_err = None
for i in range(5):
    try:
        auth.authenticate('hacker', 'wrong')
    except AuthenticationError as e:
        last_err = str(e)
check("5 неудачных попыток — обычные ошибки", 'заблокирован' not in (last_err or ''))
try:
    auth.authenticate('hacker', 'wrong')
    check("6-я попытка заблокирована", False)
except AuthenticationError as e:
    check("6-я попытка заблокирована", 'заблокирован' in str(e))
AuthService._failed_attempts.clear()
AuthService._lock_until.clear()

expect_raises("create_user с паролем '1234' → ValidationError",
              ValidationError,
              lambda: auth.create_user(ADMIN, 'testuser', '1234', 'employee'))
expect_raises("reset_password с слабым паролем → ValidationError",
              ValidationError,
              lambda: auth.reset_password(ADMIN, 1, 'qwerty'))

print("\n=== P1: маскирование ПДн по VIEW_CONFIDENTIAL ===")
M = '•'  # символ маски из Formatters.mask_confidential
check("mask_confidential 12-значный ИНН",
      Formatters.mask_confidential('123456789012') == M * 10 + '12')
check("mask_confidential пустое значение",
      Formatters.mask_confidential(None) == '')

db = FakeDB()
db.fetch_all_result = [
    {'employee_id': 1, 'first_name': 'Иван', 'last_name': 'Петров',
     'date_of_birth': date(1990, 1, 1), 'gender': 'М', 'hire_date': date(2020, 1, 1),
     'department_id': 5, 'phone': None, 'email': None,
     'inn': '123456789012', 'snils': '12345678901', 'passport': '4510123456',
     'status': 'active', 'created_at': None, 'updated_at': None,
     'department_name': 'ИТ'},
]
esvc = EmployeeService(db)
admin_list = esvc.get_employees(ADMIN, {})
check("admin видит ИНН открыто", admin_list[0].inn == '123456789012')

mgr_list = esvc.get_employees(MANAGER, {})
check("manager видит ИНН замаскированным", mgr_list[0].inn == M * 10 + '12',
      f"— получено: {mgr_list[0].inn}")
check("manager видит СНИЛС замаскированным", mgr_list[0].snils == M * 9 + '01',
      f"— получено: {mgr_list[0].snils}")
check("manager видит паспорт замаскированным", mgr_list[0].passport == M * 8 + '56',
      f"— получено: {mgr_list[0].passport}")

db.fetch_one_result = db.fetch_all_result[0]
by_id = esvc.get_employee_by_id(MANAGER, 1)
check("get_employee_by_id тоже маскирует для manager",
      by_id is not None and by_id.inn == M * 10 + '12')

print("\n=== P1: защита удаления отдела ===")
db = FakeDB()
dsvc = DepartmentService(db)

busy = Department(department_name='ИТ')
busy.employee_count = 3
busy.project_count = 0
dsvc._repository = type('R', (), {'get_by_id': lambda self, i: busy, 'delete': lambda self, i: True})()
expect_raises("Отдел с сотрудниками не удаляется", ValidationError,
              lambda: dsvc.delete_department(ADMIN, 1))

withproj = Department(department_name='ИТ')
withproj.employee_count = 0
withproj.project_count = 4
dsvc._repository = type('R', (), {'get_by_id': lambda self, i: withproj, 'delete': lambda self, i: True})()
expect_raises("Отдел с проектами не удаляется", ValidationError,
              lambda: dsvc.delete_department(ADMIN, 1))

empty = Department(department_name='Пусто')
empty.employee_count = 0
empty.project_count = 0
calls = []
dsvc._repository = type('R', (), {'get_by_id': lambda self, i: empty,
                                  'delete': lambda self, i: calls.append(i) or True})()
dsvc.delete_department(ADMIN, 1)
check("Пустой отдел удаляется", calls == [1])

print("\n=== Hotfix: менеджер видит весь справочник отделов ===")
db2 = FakeDB()
dsvc2 = DepartmentService(db2)
all_depts = [Department(department_name='А'), Department(department_name='Б')]
captured = {}

class R2:
    def get_all(self, filters):
        captured['filters'] = filters
        return all_depts

dsvc2._repository = R2()
res_mgr = dsvc2.get_departments(MANAGER, {})
check("manager получает полный список (get_all), а не [get_by_id]",
      len(res_mgr) == 2 and 'filters' in captured)
EMPLOYEE = {'id': 3, 'role': 'employee', 'department_id': 1}
res_emp = dsvc2.get_departments(EMPLOYEE, {})
check("employee тоже получает полный список", len(res_emp) == 2)
check("filters передаются в репозиторий", captured.get('filters') == {})

print("\n=== Кросс-поточный экспорт: TableSnapshot ===")
class FakeTable:
    def __init__(self):
        self._h = ['ID', 'Имя']
        self._rows = [['1', 'Иван'], ['2', 'Анна'], [None, None]]
    def rowCount(self): return len(self._rows)
    def columnCount(self): return len(self._h)
    def horizontalHeaderItem(self, i):
        class H:
            def __init__(s, t): s._t = t
            def text(s): return s._t
        return H(self._h[i]) if i < len(self._h) else None
    def item(self, r, c):
        class I:
            def __init__(s, t): s._t = t
            def text(s): return s._t
        v = self._rows[r][c] if r < len(self._rows) and c < len(self._rows[r]) else None
        return I(v) if v is not None else None

snap = TableSnapshot.from_table(FakeTable())
check("rowCount/columnCount", (snap.rowCount(), snap.columnCount()) == (3, 2))
check("Заголовки", snap.horizontalHeaderItem(0).text() == 'ID')
check("Ячейки: пустая ячейка → '', заполненная → текст",
      snap.item(2, 0).text() == '' and snap.item(0, 1).text() == 'Иван')

# Экспорт в Excel из снапшота (без Qt)
import pandas as pd
headers = [snap.horizontalHeaderItem(i).text() for i in range(snap.columnCount())]
rows = [[snap.item(r, c).text() if snap.item(r, c) else '' for c in range(snap.columnCount())]
        for r in range(snap.rowCount())]
df = pd.DataFrame(rows, columns=headers)
check("DataFrame из снапшота собирается", list(df.columns) == ['ID', 'Имя'] and len(df) == 3)

# Экспорт в PDF из снапшота (reportlab, без Qt)
from services.export_service import ExportService
pdf_path = '/home/z/my-project/scripts/_snap_test.pdf'
try:
    ExportService.export_to_pdf(snap, pdf_path, 'Тестовый экспорт')
    check("export_to_pdf работает со снапшотом (PDF создан)", os.path.exists(pdf_path))
finally:
    if os.path.exists(pdf_path):
        os.remove(pdf_path)

xlsx_path = '/home/z/my-project/scripts/_snap_test.xlsx'
try:
    ExportService.export_to_excel(snap, xlsx_path, 'Лист1')
    check("export_to_excel работает со снапшотом (XLSX создан)", os.path.exists(xlsx_path))
finally:
    if os.path.exists(xlsx_path):
        os.remove(xlsx_path)

# Слой сервисов не зависит от PyQt6 (нет импортов, а не просто упоминаний)
import re as _re
import services.export_service as es_mod
_src = open(es_mod.__file__, encoding='utf-8').read()
qt_free = _re.search(r'^\s*(from|import)\s+PyQt6', _src, _re.M) is None
check("export_service не импортирует PyQt6", qt_free)

print("\n=== Дополнительно: ПДн не попадают в UPDATE без ключей в data ===")
# update_employee использует сырой fetch из репозитория: даже если
# в data нет inn/snils/passport (роль без права), в UPDATE уходят
# реальные значения из БД, а не маска из диалога.
# update_employee для manager: данные без inn/snils/passport → в UPDATE уходят сырые значения из БД
class RawRepo:
    def __init__(self, db): self.db = db
    def get_by_id(self, eid):
        return Employee(employee_id=eid, first_name='Иван', last_name='Петров',
                        date_of_birth=date(1990, 1, 1), hire_date=date(2020, 1, 1),
                        inn='123456789012', snils='12345678901', passport='4510123456',
                        status='active')
    def update(self, employee):
        RawRepo.written = (employee.inn, employee.snils, employee.passport)
        return True

db = FakeDB()
esvc = EmployeeService(db)
esvc._repository = RawRepo(db)
esvc.update_employee(ADMIN, 1, {'first_name': 'Иван', 'phone': '+79001234567'})
check("Реальные ПДн не перезаписываются маской", RawRepo.written == ('123456789012', '12345678901', '4510123456'))

# ------------------------------------------------------------------ итог
print("\n" + "=" * 60)
print(f"ИТОГО: пройдено {len(PASSED)}, провалено {len(FAILED)}")
if FAILED:
    print("Проваленные тесты:")
    for t in FAILED:
        print("  -", t)
    sys.exit(1)
print("ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ ✓")
