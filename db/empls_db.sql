-- 1. Создание таблиц
 CREATE TABLE IF NOT EXISTS departments (
     department_id SERIAL PRIMARY KEY,
     department_name TEXT NOT NULL,
     description TEXT, -- Описание отдела (читается экраном «Отделы»)
     manager_id INTEGER, -- Внешний ключ на employees, но employees ещё не создана
     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        
 );

 CREATE TABLE IF NOT EXISTS users (
     id SERIAL PRIMARY KEY,
     username VARCHAR(50) NOT NULL UNIQUE,
     password_hash VARCHAR(255) NOT NULL,
     role VARCHAR(20) DEFAULT 'employee' CHECK (role IN ('admin', 'manager', 'employee')),
     department_id INTEGER,
     is_active BOOLEAN DEFAULT TRUE,
     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
     last_login TIMESTAMP,
     FOREIGN KEY (department_id)
         REFERENCES departments(department_id)
         ON DELETE SET NULL ON UPDATE CASCADE
 );

 CREATE TABLE IF NOT EXISTS employees (
     employee_id SERIAL PRIMARY KEY,
     first_name TEXT NOT NULL,
     last_name TEXT NOT NULL,
     date_of_birth DATE NOT NULL,
     gender CHAR(1) CHECK (gender IN ('М', 'Ж')),
     hire_date DATE NOT NULL,
     department_id INTEGER,
     phone VARCHAR(20),
     email VARCHAR(100),
     inn VARCHAR(12),
     snils VARCHAR(14),
     passport VARCHAR(20),
     status VARCHAR(10) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'fired')),
     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
     FOREIGN KEY (department_id)
         REFERENCES departments(department_id)
         ON DELETE SET NULL ON UPDATE CASCADE
 );

 -- добавляем внешний ключ manager_id в таблицу departments.

 ALTER TABLE departments
 ADD CONSTRAINT fk_manager
 FOREIGN KEY (manager_id)
 REFERENCES employees(employee_id)
 ON DELETE SET NULL ON UPDATE CASCADE;

 CREATE TABLE IF NOT EXISTS salaries (
     salary_id SERIAL PRIMARY KEY,
     employee_id INTEGER NOT NULL,
     salary_amount NUMERIC(10, 2) CHECK (salary_amount >= 0),
     effective_date DATE NOT NULL,
     payment_type VARCHAR(20) DEFAULT 'salary'
         CHECK (payment_type IN ('salary', 'bonus', 'advance')),
     description TEXT,
     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
     FOREIGN KEY (employee_id)
         REFERENCES employees(employee_id)
         ON DELETE CASCADE ON UPDATE CASCADE
 );
                
 CREATE TABLE IF NOT EXISTS projects (
     project_id SERIAL PRIMARY KEY,
     project_name TEXT NOT NULL,
     description TEXT,
     start_date DATE NOT NULL,
     end_date DATE NOT NULL,
     status VARCHAR(20) DEFAULT 'planning' CHECK (status IN ('planning', 'in_progress', 'on_hold', 'completed', 'cancelled')),
     budget NUMERIC(12, 2) CHECK (budget >= 0),
     department_id INTEGER NOT NULL,
     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
     FOREIGN KEY (department_id)
         REFERENCES departments(department_id)
         ON DELETE CASCADE ON UPDATE CASCADE
 );

 --  2. Добавление данных
 -- Заполнение departments (30 отделов)

 INSERT INTO departments (department_id, department_name) VALUES
 (1, 'Отдел разработки программного обеспечения'),
 (2, 'Финансовый отдел'),
 (3, 'Отдел маркетинга'),
 (4, 'Отдел продаж'),
 (5, 'Отдел кадров (HR)'),
 (6, 'Техническая поддержка'),
 (7, 'Отдел контроля качества'),
 (8, 'Отдел логистики'),
 (9, 'Юридический отдел'),
 (10, 'Отдел аналитики'),
 (11, 'Отдел исследований и разработок'),
 (12, 'Отдел закупок'),
 (13, 'Отдел безопасности'),
 (14, 'Отдел дизайна'),
 (15, 'Отдел обучения и развития'),
 (16, 'Отдел PR и коммуникаций'),
 (17, 'Отдел бухгалтерии'),
 (18, 'Производственный отдел'),
 (19, 'Отдел экспорта'),
 (20, 'Отдел импорта'),
 (21, 'Отдел клиентского сервиса'),
 (22, 'Отдел мобильной разработки'),
 (23, 'Отдел веб-разработки'),
 (24, 'Отдел искусственного интеллекта'),
 (25, 'Отдел Big Data'),
 (26, 'Отдел IoT'),
 (27, 'Отдел облачных технологий'),
 (28, 'Отдел кибербезопасности'),
 (29, 'Административный отдел'),
 (30, 'Отдел стратегического планирования');

-- Добавление сотрудников, минимум 150


INSERT INTO employees (employee_id, first_name, last_name, date_of_birth, gender, hire_date, department_id)
 SELECT
     id,
     CASE
         WHEN gender_code = 'М' THEN
             (ARRAY['Александр','Дмитрий','Максим','Сергей','Андрей','Алексей','Артем','Илья','Кирилл','Михаил'])[ceil(random()*10)]
         ELSE
             (ARRAY['Екатерина','Мария','Анна','Ольга','Ирина','Наталья','Елена','Татьяна','Светлана','Юлия'])[ceil(random()*10)]
     END,
     CASE
         WHEN gender_code = 'М' THEN
             (ARRAY['Иванов','Петров','Сидоров','Смирнов','Кузнецов','Попов','Васильев','Павлов','Семенов','Голубев'])[ceil(random()*10)]
         ELSE
             (ARRAY['Иванова','Петрова','Сидорова','Смирнова','Кузнецова','Попова','Васильева','Павлова','Семенова','Голубева'])[ceil(random()*10)]
     END,
     current_date - (18*365 + (random()*40*365)::int) * INTERVAL '1 day',
     gender_code,
     current_date - (random()*3650)::int * INTERVAL '1 day',
     (random()*29 + 1)::int
 FROM
     (
         SELECT
             id,
             CASE WHEN row_number() OVER (ORDER BY random()) <= 75 THEN 'М' ELSE 'Ж' END AS gender_code
         FROM generate_series(1, 150) AS id
     ) AS employees_data
        ORDER BY id;



 -- Обновляем таблицу department, добавляем менеджера

 UPDATE departments d
 SET manager_id = (
   SELECT employee_id
   FROM employees
   WHERE department_id = d.department_id
   ORDER BY random()
   LIMIT 1
 );

 -- Заполняем таблицу зарплаты
 -- (salary_id объявлен SERIAL выше — автогенерация уже включена)

 INSERT INTO salaries (employee_id, salary_amount, effective_date)
 SELECT
     e.employee_id,
     (30000 + (random() * 120000))::numeric(10,2),
     current_date - (random() * 1095 || ' days')::interval - (seq * 180 || ' days')::interval
 FROM
     employees e
 CROSS JOIN
     generate_series(1, 2 + (random() * 1)::int) AS seq;

 -- Заполняем таблицу проекты

 INSERT INTO projects (project_id, project_name, start_date, end_date, department_id)
 SELECT
     id,
     'Проект ' || substring(md5(random()::text), 1, 6), -- уникальное название
     current_date - (random() * 730 || ' days')::interval, -- начало: последние 2 года
     current_date - (random() * 730 || ' days')::interval +
     (random() * 365 || ' days')::interval, -- длительность: 0-365 дней
     (random() * 29 + 1)::int -- случайный department_id (1-30)
 FROM generate_series(1, 30) AS id;

 --     Выбора всех сотрудников с зарплатой выше определенной суммы

 SELECT
     e.employee_id,
     e.first_name,
     e.last_name,
     s.salary_amount AS current_salary,
     s.effective_date
 FROM employees e
 JOIN (
     SELECT
         employee_id,
         salary_amount,
         effective_date
     FROM salaries
     WHERE (employee_id, effective_date) IN (
         SELECT
             employee_id,
             MAX(effective_date)
         FROM salaries
         GROUP BY employee_id
     )
 ) s ON e.employee_id = s.employee_id
 WHERE s.salary_amount > 50000
 ORDER BY current_salary DESC;

 -- Выбор всех проектов, которые выполняются в определенном отделе

 SELECT
     p.project_id,
     p.project_name,
     p.start_date,
     p.end_date,
     d.department_name
 FROM projects p
 JOIN departments d ON p.department_id = d.department_id
 WHERE p.department_id = 5; --  id надо менять что бы узнать какой проект выполняет отдел

 -- Выбор сотрудников, которые не участвуют в проектах

 SELECT
     e.employee_id,
     e.first_name,
     e.last_name,
     e.department_id
 FROM employees e
 LEFT JOIN departments d
     ON e.department_id = d.department_id
 LEFT JOIN projects p
     ON d.department_id = p.department_id
 WHERE p.project_id IS NULL;

 -- Выбор сотрудников, которые участвуют в проектах

SELECT 
     e.employee_id,
     e.first_name,
     e.last_name,
     p.project_id,
     p.project_name AS project_name
 FROM
     employees e
 JOIN
     projects p ON e.department_id = p.department_id
 ORDER BY
     e.employee_id,
     p.project_id;


 -- Вывод средней зарплаты сотрудника по всем отделам

 WITH LatestSalaries AS (
     SELECT
         s.employee_id,
         s.salary_amount,
         ROW_NUMBER() OVER (
             PARTITION BY s.employee_id
             ORDER BY s.effective_date DESC
         ) AS rn
     FROM salaries s
 )
 SELECT
     d.department_id,
     d.department_name,
     COUNT(DISTINCT e.employee_id) AS employees_count,
     ROUND(AVG(ls.salary_amount), 2) AS avg_salary
 FROM departments d
 LEFT JOIN employees e ON d.department_id = e.department_id
 LEFT JOIN LatestSalaries ls
     ON e.employee_id = ls.employee_id
     AND ls.rn = 1
 GROUP BY d.department_id, d.department_name
 ORDER BY avg_salary DESC;

 -- 3: Индексы
 -- Создание индексов
 -- Создайте индекс на поле employee_id в таблице salaries для ускорения запросов, связанных с поиском зарплат по сотруднику.

 CREATE INDEX idx_salaries_employee_id
 ON salaries (employee_id);

 --Создайте индекс на поле department_id в таблице employees для ускорения поиска сотрудников по отделу.

 CREATE INDEX idx_employees_department_id
 ON employees (department_id);

 -- Часть 4: Транзакции
 -- Реализация транзакций
 -- Реализуйте транзакцию для добавления нового сотрудника и назначения ему зарплаты:
 -- ●   Добавьте нового сотрудника в таблицу employees.
 -- ●   Добавьте запись о зарплате для сотрудника в таблицу salaries.
 -- ●   Если хотя бы одна из операций неудачна, транзакция должна быть отменена.
 -- Сценарии для транзакций
 -- ●   Добавление сотрудника и зарплаты, где один из внешних ключей некорректен.
 -- ●   Добавление сотрудника, но с ошибкой при добавлении зарплаты.
 -- Обработка ошибок
 -- ●   Напишите запрос с использованием BEGIN, COMMIT и ROLLBACK для контроля транзакций
 -- Корректный ввод

-- Пример добавления сотрудника и зарплаты
-- Добавляем сотрудника
BEGIN;

INSERT INTO employees (
    employee_id,
    first_name,
    last_name,
    date_of_birth,
    gender,
    hire_date,
    department_id
) VALUES (
    151,
    'Андрей',
    'Соколов',
    '1995-08-20',
    'М',  -- Исправлено на кириллический символ
    CURRENT_DATE,
    5
 );

INSERT INTO salaries (
    employee_id,
    salary_amount,
    effective_date
) VALUES (
    151,
    85000.00,
    CURRENT_DATE
);

COMMIT;

-- Часть 5: Функции (PL/pgSQL)
-- Функция для вычисления средней зарплаты
-- Напишите функцию, которая будет принимать employee_id и возвращать среднюю зарплату этого сотрудника.

CREATE OR REPLACE FUNCTION get_employee_avg_salary(p_employee_id INTEGER)
RETURNS NUMERIC AS $$
DECLARE
    avg_salary NUMERIC;
BEGIN
    SELECT AVG(salary_amount) 
    INTO avg_salary
    FROM salaries
    WHERE employee_id = p_employee_id;

    RETURN COALESCE(avg_salary, 0);
END;
$$ LANGUAGE plpgsql;

-- Пример 
SELECT get_employee_avg_salary(123) AS average_salary;

-- Функция для обновления информации о сотруднике
-- Напишите функцию для обновления фамилии сотрудника по employee_id. Функция должна проверять, существует ли сотрудник.

CREATE OR REPLACE FUNCTION update_employee_last_name(
    p_employee_id INTEGER,
    p_new_last_name TEXT
) RETURNS employees AS $$
DECLARE
    updated_employee employees%ROWTYPE;
BEGIN
    -- Проверка существования сотрудника
    IF NOT EXISTS (SELECT 1 FROM employees WHERE employee_id = p_employee_id) THEN
        RAISE EXCEPTION 'Сотрудник с ID % не найден', p_employee_id;
    END IF;

    -- Валидация новой фамилии
    IF p_new_last_name IS NULL OR TRIM(p_new_last_name) = '' THEN
        RAISE EXCEPTION 'Новая фамилия не может быть пустой';
    END IF;

    -- Основное обновление
    UPDATE employees
    SET 
        last_name = p_new_last_name,
        updated_at = CURRENT_TIMESTAMP
    WHERE employee_id = p_employee_id
    RETURNING * INTO updated_employee;

    RETURN updated_employee;
END;
$$ LANGUAGE plpgsql VOLATILE;

-- Пример (HF-7: вызов закомментирован — в сидовых данных нет сотрудника
-- с ID 200, функция RAISE-ила исключение и обрывала выполнение всего дампа
-- на свежей БД; в pgAdmin из-за этого не выполнялись и сиды пользователей,
-- и setval-блок, находящиеся ниже по файлу).
-- SELECT * FROM update_employee_last_name(200, 'Петров');

-- Функция для подсчета количества сотрудников в отделе
-- Напишите функцию, которая будет принимать department_id и возвращать количество сотрудников в этом отделе

CREATE OR REPLACE FUNCTION get_department_employee_count(
    p_department_id INTEGER
) RETURNS INTEGER AS $$
DECLARE
    department_exists BOOLEAN;
    employee_count INTEGER;
BEGIN
    -- Проверка существования отдела
    SELECT EXISTS(
        SELECT 1 
        FROM departments 
        WHERE department_id = p_department_id
    ) INTO department_exists;

    IF NOT department_exists THEN
        RAISE EXCEPTION 'Отдел с ID % не существует', p_department_id;
    END IF;

    -- Подсчёт сотрудников
    SELECT COUNT(*) 
    INTO employee_count
    FROM employees
    WHERE department_id = p_department_id;

    RETURN employee_count;
END;
$$ LANGUAGE plpgsql STABLE;

-- Пример
SELECT get_department_employee_count(13) AS employees_count;

-- Пример

SELECT get_department_employee_count(5) AS employees_count;


-- Часть 6: Процедуры

-- Процедура для обновления статуса сотрудника
-- Напишите процедуру, которая будет обновлять статус сотрудника (например, "активен", "уволен") в зависимости от его участия в проектах.

-- I. Поле статуса объявлено в CREATE TABLE employees выше
--    (status VARCHAR(10) DEFAULT 'active' CHECK IN ('active','inactive','fired')).
--    Русские статусы ('активен'/'неактивен'/'уволен') добавлять НЕЛЬЗЯ:
--    приложение пишет только английские значения, русская CHECK-блокировала
--    бы добавление и редактирование сотрудников.
--    Учебная процедура ниже переведена на английские эквиваленты.

-- II. Создаем процедуру обновления статусов
CREATE OR REPLACE PROCEDURE update_employees_status()
LANGUAGE plpgsql
AS $$
BEGIN
    -- Обновляем статус для активных в проектах
    UPDATE employees e
    SET status = 'active'
    WHERE EXISTS (
        SELECT 1
        FROM projects p
        WHERE p.department_id = e.department_id
        AND CURRENT_DATE BETWEEN p.start_date AND p.end_date
    )
    AND status <> 'уволен';

    -- Обновляем статус для неактивных
    UPDATE employees e
    SET status = 'inactive'
    WHERE NOT EXISTS (
        SELECT 1
        FROM projects p
        WHERE p.department_id = e.department_id
        AND CURRENT_DATE BETWEEN p.start_date AND p.end_date
    )
    AND status NOT IN ('fired', 'inactive');
END;
$$;

-- Проверка статусов
SELECT employee_id, first_name, last_name, status 
FROM employees
WHERE department_id = 5;

-- Процедура для назначения сотрудника на проект
-- Напишите процедуру для назначения сотрудника на проект. Процедура должна проверять, что сотрудник и проект существуют.

-- I. перед созданием процедуры, нужно создать таблицу employee_projects.
CREATE TABLE IF NOT EXISTS employee_projects (
    employee_id INTEGER REFERENCES employees(employee_id) ON DELETE CASCADE,
    project_id INTEGER REFERENCES projects(project_id) ON DELETE CASCADE,
    assigned_date DATE DEFAULT CURRENT_DATE,
    PRIMARY KEY (employee_id, project_id)
);

-- II. процедура
CREATE OR REPLACE PROCEDURE assign_employee_to_project(
    p_employee_id INTEGER,
    p_project_id INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_employee_dept INTEGER;
    v_project_dept INTEGER;
BEGIN
    -- Проверка существования сотрудника
    PERFORM 1 FROM employees WHERE employee_id = p_employee_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Сотрудник с ID % не существует', p_employee_id;
    END IF;

    -- Проверка существования проекта
    PERFORM 1 FROM projects WHERE project_id = p_project_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Проект с ID % не существует', p_project_id;
    END IF;

    -- Проверка принадлежности к одному отделу
    SELECT department_id INTO v_employee_dept 
    FROM employees 
    WHERE employee_id = p_employee_id;

    SELECT department_id INTO v_project_dept 
    FROM projects 
    WHERE project_id = p_project_id;

    IF v_employee_dept != v_project_dept THEN
        RAISE EXCEPTION 'Сотрудник из отдела % не может быть назначен на проект отдела %',
                      v_employee_dept, v_project_dept;
    END IF;

    -- Проверка дублирующего назначения
    PERFORM 1 
    FROM employee_projects 
    WHERE employee_id = p_employee_id 
      AND project_id = p_project_id;
    
    IF FOUND THEN
        RAISE NOTICE 'Сотрудник уже назначен на этот проект';
        RETURN;
    END IF;

    -- Назначение сотрудника
    INSERT INTO employee_projects (employee_id, project_id)
    VALUES (p_employee_id, p_project_id);

    -- Обновление времени модификации проекта
    UPDATE projects
    SET updated_at = CURRENT_TIMESTAMP
    WHERE project_id = p_project_id;

    RAISE NOTICE 'Сотрудник % успешно назначен на проект %', 
               p_employee_id, p_project_id;
END;
$$;

-- Пример (HF-7: закомментирован — при сидах с random() сотрудник и проект
-- могут оказаться в разных отделах, процедура RAISE-ит и обрывает дамп).
-- CALL assign_employee_to_project(7, 10);

CREATE OR REPLACE PROCEDURE update_department_salaries(
    p_department_id INTEGER,
    p_percent NUMERIC(5,2) DEFAULT 10.00
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_department_exists BOOLEAN;
    v_employee_record RECORD;
    v_current_salary NUMERIC(10,2);
    v_effective_date DATE;
BEGIN
    -- Проверка существования отдела
    PERFORM 1 FROM departments WHERE department_id = p_department_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Отдел с ID % не существует', p_department_id;
    END IF;

    -- Проверка допустимости процента
    IF p_percent <= 0 THEN
        RAISE EXCEPTION 'Процент повышения должен быть положительным числом';
    END IF;

    -- Основная логика без явного управления транзакциями
    FOR v_employee_record IN 
        SELECT employee_id 
        FROM employees 
        WHERE department_id = p_department_id
    LOOP
        -- Получение последней зарплаты
        SELECT salary_amount, effective_date 
        INTO v_current_salary, v_effective_date
        FROM salaries
        WHERE employee_id = v_employee_record.employee_id
        ORDER BY effective_date DESC
        LIMIT 1;

        IF v_current_salary IS NOT NULL THEN
            -- Вставка новой записи о зарплате
            INSERT INTO salaries (
                employee_id, 
                salary_amount, 
                effective_date
            ) VALUES (
                v_employee_record.employee_id,
                ROUND(v_current_salary * (1 + p_percent/100), 2),
                CURRENT_DATE
            );

            -- Обновление времени изменения сотрудника
            UPDATE employees
            SET updated_at = CURRENT_TIMESTAMP
            WHERE employee_id = v_employee_record.employee_id;
        ELSE
            RAISE NOTICE 'Сотрудник % не имеет записей о зарплате', 
                        v_employee_record.employee_id;
        END IF;
    END LOOP;

    -- Обновление времени изменения отдела
    UPDATE departments
    SET updated_at = CURRENT_TIMESTAMP
    WHERE department_id = p_department_id;

EXCEPTION
    WHEN OTHERS THEN
        RAISE; -- Автоматический откат транзакции при ошибке
END;
$$;

-- Примеры (HF-7: демо-вызовы закомментированы — они МОДИФИЦИРУЮТ зарплаты
-- сидов при каждой установке БД; последний к тому же падает на
-- несуществующем отделе 200 и обрывает выполнение дампа).
-- Повышение на 10% для отдела 5
-- CALL update_department_salaries(5);

-- Повышение на 15.5% для отдела 7
-- CALL update_department_salaries(7, 15.5);

-- Попытка обновления несуществующего отдела
-- CALL update_department_salaries(200);

-- Проверка повышения з/п для отдела 5
SELECT 
    e.employee_id AS "ID сотрудника",
    e.first_name AS "Имя",
    e.last_name AS "Фамилия",
    s.salary_amount AS "Текущая зарплата",
    s.effective_date AS "Дата вступления в силу"
FROM employees e
JOIN (
    SELECT 
        employee_id,
        salary_amount,
        effective_date,
        ROW_NUMBER() OVER (PARTITION BY employee_id ORDER BY effective_date DESC) AS rn
    FROM salaries
) s ON e.employee_id = s.employee_id AND s.rn = 1
WHERE e.department_id = 5
ORDER BY s.salary_amount DESC, e.last_name;

-- Часть 7: Триггеры

-- Триггер для автоматического обновления таблицы salaries
-- Напишите триггер, который будет автоматически обновлять таблицу salaries, если сотрудник получает зарплату выше определенной суммы.

-- 1. Создаём таблицу для аудита
CREATE TABLE IF NOT EXISTS high_salary_audit (
    audit_id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL,
    salary_amount NUMERIC(10,2) NOT NULL,
    effective_date DATE NOT NULL,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_employee
        FOREIGN KEY(employee_id) 
        REFERENCES employees(employee_id)
);

-- 2. Создаём триггерную функцию
CREATE OR REPLACE FUNCTION check_high_salary()
RETURNS TRIGGER AS $$
DECLARE
    salary_threshold NUMERIC := 100000; -- Пороговая сумма
BEGIN
    IF NEW.salary_amount > salary_threshold THEN
        INSERT INTO high_salary_audit (
            employee_id, 
            salary_amount, 
            effective_date
        ) VALUES (
            NEW.employee_id,
            NEW.salary_amount,
            NEW.effective_date
        );
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 3. Создаём триггер
CREATE TRIGGER salary_threshold_trigger
AFTER INSERT OR UPDATE ON salaries
FOR EACH ROW
EXECUTE FUNCTION check_high_salary();

-- Добавляем зарплату ниже порога
INSERT INTO salaries (employee_id, salary_amount, effective_date)
VALUES (123, 85000, '2024-01-15'); -- Не попадёт в аудит

-- Добавляем зарплату выше порога
INSERT INTO salaries (employee_id, salary_amount, effective_date)
VALUES (126, 120000, '2024-01-15'); -- Запишется в high_salary_audit

-- Триггер для проверки уникальности записи
-- Напишите триггер, который будет проверять, что одна и та же зарплата не может быть назначена одному сотруднику дважды.

-- 1. Создаём триггерную функцию
CREATE OR REPLACE FUNCTION prevent_duplicate_salary()
RETURNS TRIGGER AS $$
BEGIN
    -- Проверяем существование записи с такой же зарплатой для этого сотрудника
    IF EXISTS (
        SELECT 1 
        FROM salaries 
        WHERE employee_id = NEW.employee_id 
          AND salary_amount = NEW.salary_amount 
          AND salary_id <> COALESCE(NEW.salary_id, -1) -- Исключаем текущую запись при UPDATE
    ) THEN
        RAISE EXCEPTION 
            'Сотрудник ID % уже имеет зарплату в размере %. Повторное назначение запрещено.',
            NEW.employee_id, NEW.salary_amount;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 2. Создаём триггер
CREATE TRIGGER trg_prevent_duplicate_salary
BEFORE INSERT OR UPDATE OF salary_amount ON salaries
FOR EACH ROW EXECUTE FUNCTION prevent_duplicate_salary();

-- Триггер для автоматического обновления даты последнего обновления
-- Напишите триггер, который будет автоматически обновлять поле updated_at в таблице employees, departments, salaries и projects, каждый раз когда запись изменяется

-- 1. Создаём общую триггерную функцию
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 2. Создаём триггеры для каждой таблицы
-- Для employees
CREATE TRIGGER update_employees_modtime
BEFORE UPDATE ON employees
FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- Для departments
CREATE TRIGGER update_departments_modtime
BEFORE UPDATE ON departments
FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- Для salaries
CREATE TRIGGER update_salaries_modtime
BEFORE UPDATE ON salaries
FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- Для projects
CREATE TRIGGER update_projects_modtime
BEFORE UPDATE ON projects
FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- Часть 8
-- DO-блок для выполнения анонимного кода
-- Напишите DO-блок, который будет создавать нового сотрудника и назначать его на несколько проектов

DO $$
DECLARE
    new_employee_id INTEGER;
    valid_projects INTEGER[];
BEGIN
    -- Создание нового сотрудника
    INSERT INTO employees (
        employee_id, 
        first_name, 
        last_name, 
        date_of_birth, 
        gender, 
        hire_date, 
        department_id
    ) VALUES (
        (SELECT COALESCE(MAX(employee_id), 0) + 1 FROM employees),
        'Иван',
        'Петров',
        '1990-05-15'::DATE,
        'М',
        CURRENT_DATE,
        (SELECT department_id FROM departments ORDER BY RANDOM() LIMIT 1)
    )
    RETURNING employee_id INTO new_employee_id;

    -- Получение списка проектов
    SELECT ARRAY(
        SELECT project_id 
        FROM projects 
        WHERE project_id IN (7, 12, 25) 
          AND end_date > CURRENT_DATE
    ) 
    INTO valid_projects;

    -- Проверка наличия проектов
    IF valid_projects IS NULL OR array_length(valid_projects, 1) = 0 THEN
        RAISE EXCEPTION 'Нет доступных проектов для назначения';
    END IF;

    -- Назначение на проекты
    INSERT INTO employee_projects (employee_id, project_id)
    SELECT new_employee_id, UNNEST(valid_projects);

    RAISE NOTICE 'Сотрудник ID % успешно создан и назначен на проекты: %', 
               new_employee_id, valid_projects;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(100) NOT NULL,
    role VARCHAR(20) CHECK (role IN ('admin', 'manager', 'employee')) NOT NULL,
    department_id INT REFERENCES departments(department_id),
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    action_type VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW(),
    details TEXT
);


-- Синхронизация sequence первичных ключей после сидов с явными ID.
-- Без этого первый INSERT из приложения получил бы ID = 1 и упал бы
-- с конфликтом первичного ключа.
SELECT setval(pg_get_serial_sequence('employees', 'employee_id'),
              COALESCE((SELECT MAX(employee_id) FROM employees), 0) + 1, false);
SELECT setval(pg_get_serial_sequence('departments', 'department_id'),
              COALESCE((SELECT MAX(department_id) FROM departments), 0) + 1, false);
SELECT setval(pg_get_serial_sequence('projects', 'project_id'),
              COALESCE((SELECT MAX(project_id) FROM projects), 0) + 1, false);
SELECT setval(pg_get_serial_sequence('salaries', 'salary_id'),
              COALESCE((SELECT MAX(salary_id) FROM salaries), 0) + 1, false);

-- Сиды пользователей: пароли хешируются bcrypt. Открытые пароли '111'/'222'/'333'
-- нарушали парольную политику (utils/validators.py) и работали только через
-- legacy-fallback в AuthService._verify_password — заменены на bcrypt-хеши.
-- Пароли: admin / Admin123!, manager / Manager123!, employee / Employee123!
-- (сменить после первого входа).
INSERT INTO users (username, password_hash, role)
VALUES ('admin', '$2b$12$jJYvp7Nr4kxqTIfAKyNx3u1umE1sSgqNadKJo1Zh/11N5pzseZGAS', 'admin');

INSERT INTO users (username, password_hash, role, department_id)
VALUES ('manager', '$2b$12$Z.8RuZ.TDS7bp4iTe.9eaeTiiy4UFkTDhUuFbz/kYoxmE3WyY2aFC', 'manager', '5');

INSERT INTO users (username, password_hash, role, department_id)
VALUES ('employee', '$2b$12$9YzxiRZB7u.KaqagTeJkxuMOvboRDyDXEFxZAK8u25y/z5OT9Y.la', 'employee', '5');

-- Добавление новых колонок
 ALTER TABLE employees
 ADD COLUMN IF NOT EXISTS phone VARCHAR(20),
 ADD COLUMN IF NOT EXISTS email VARCHAR(100),
 ADD COLUMN IF NOT EXISTS inn VARCHAR(12),
 ADD COLUMN IF NOT EXISTS snils VARCHAR(14),
 ADD COLUMN IF NOT EXISTS passport VARCHAR(20);


 UPDATE employees SET
     phone = '+7 (907) 123-45-62',
     email = 'golubeva@company.com',
     inn = '123456789012',
     passport = '4510 123456'
 WHERE employee_id = 1;

-- (закомментировано: 'user' — зарезервированное слово, запрос падал с
-- синтаксической ошибкой; пароль '123' нарушает политику приложения)
-- UPDATE users SET
--     password_hash = '123'
-- WHERE id = 9;

-- Добавляем флаг активности для отделов
ALTER TABLE departments ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

-- Добавляем флаг активности для зарплат (финансовые данные нельзя удалять никогда)
ALTER TABLE salaries ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

-- добавить is_active для удобства, если нужно скрывать завершенные проекты.
ALTER TABLE projects ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;