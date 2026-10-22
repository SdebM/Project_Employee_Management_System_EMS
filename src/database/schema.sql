-- ============================================
-- EMS: Каноничная схема базы данных PostgreSQL
-- ============================================
-- ПРИМЕЧАНИЕ: это основная схема проекта (в отличие от db/empls_db.sql).
-- Колонки is_active в departments/salaries/projects добавлены явно:
-- репозитории (BaseRepository.soft_delete_column) используют мягкое
-- удаление и выполняют UPDATE ... SET is_active = FALSE, поэтому
-- без этих колонок любое удаление отдела/зарплаты/проекта падало бы
-- с UndefinedColumn.

-- Порядок создания учитывает зависимости FK

-- 1. Отделы
CREATE TABLE IF NOT EXISTS departments (
    department_id SERIAL PRIMARY KEY,
    department_name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,                            -- Описание отдела
    manager_id INTEGER,                          -- FK добавляется после создания employees
    is_active BOOLEAN NOT NULL DEFAULT TRUE,     -- мягкое удаление (BaseRepository)
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 2. Пользователи (аутентификация)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'employee'
        CHECK (role IN ('admin', 'manager', 'employee')),
    department_id INTEGER REFERENCES departments(department_id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_login TIMESTAMP
);

-- 3. Сотрудники
CREATE TABLE IF NOT EXISTS employees (
    employee_id SERIAL PRIMARY KEY,
    first_name VARCHAR(255) NOT NULL,
    last_name VARCHAR(255) NOT NULL,
    date_of_birth DATE NOT NULL,
    gender CHAR(1) NOT NULL CHECK (gender IN ('М', 'Ж')),
    hire_date DATE NOT NULL,
    department_id INTEGER REFERENCES departments(department_id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    phone VARCHAR(20),
    email VARCHAR(100),
    inn VARCHAR(12),
    snils VARCHAR(14),
    passport VARCHAR(20),
    status VARCHAR(10) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'fired')),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- FK: руководитель отдела → сотрудник
ALTER TABLE departments
    ADD CONSTRAINT fk_departments_manager
    FOREIGN KEY (manager_id) REFERENCES employees(employee_id)
    ON DELETE SET NULL ON UPDATE CASCADE;

-- 4. Зарплаты (финансовые записи никогда не удаляются физически —
--     мягкое удаление через is_active)
CREATE TABLE IF NOT EXISTS salaries (
    salary_id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    salary_amount NUMERIC(12, 2) NOT NULL CHECK (salary_amount >= 0),
    effective_date DATE NOT NULL,
    payment_type VARCHAR(20) NOT NULL DEFAULT 'salary'
        CHECK (payment_type IN ('salary', 'bonus', 'advance')),
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,     -- мягкое удаление (BaseRepository)
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 5. Проекты
CREATE TABLE IF NOT EXISTS projects (
    project_id SERIAL PRIMARY KEY,
    project_name VARCHAR(255) NOT NULL,
    description TEXT,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'planning'
        CHECK (status IN ('planning', 'in_progress', 'on_hold', 'completed', 'cancelled')),
    budget NUMERIC(12, 2) CHECK (budget >= 0),
    department_id INTEGER NOT NULL REFERENCES departments(department_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,     -- мягкое удаление (BaseRepository)
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 6. Связь сотрудников и проектов (M:N)
CREATE TABLE IF NOT EXISTS employee_projects (
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(project_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    assigned_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (employee_id, project_id)
);

-- 7. Журнал аудита
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    action_type VARCHAR(50) NOT NULL,
    details TEXT,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================
-- Индексы
-- ============================================

CREATE INDEX IF NOT EXISTS idx_employees_department   ON employees(department_id);
CREATE INDEX IF NOT EXISTS idx_employees_status        ON employees(status);
CREATE INDEX IF NOT EXISTS idx_employees_last_name     ON employees(last_name);

CREATE INDEX IF NOT EXISTS idx_salaries_employee       ON salaries(employee_id);
CREATE INDEX IF NOT EXISTS idx_salaries_effective_date ON salaries(effective_date);

CREATE INDEX IF NOT EXISTS idx_projects_department     ON projects(department_id);
CREATE INDEX IF NOT EXISTS idx_projects_status         ON projects(status);

CREATE INDEX IF NOT EXISTS idx_audit_log_user          ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp     ON audit_log(timestamp);

CREATE INDEX IF NOT EXISTS idx_users_username          ON users(username);

-- ============================================
-- Триггер: автообновление updated_at
-- ============================================

CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_employees_updated
    BEFORE UPDATE ON employees
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER trg_departments_updated
    BEFORE UPDATE ON departments
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER trg_salaries_updated
    BEFORE UPDATE ON salaries
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER trg_projects_updated
    BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- ============================================
-- Начальные данные: администратор
-- Логин:  admin
-- Пароль: Admin123!  (ОБЯЗАТЕЛЬНО сменить после первого входа!
-- Хеш соответствует bcrypt и политике Validators.validate_password)
-- ============================================

INSERT INTO users (username, password_hash, role)
VALUES (
    'admin',
    '$2b$12$jJYvp7Nr4kxqTIfAKyNx3u1umE1sSgqNadKJo1Zh/11N5pzseZGAS',
    'admin'
) ON CONFLICT (username) DO NOTHING;
