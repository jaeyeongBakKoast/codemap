CREATE TABLE departments (
    id BIGINT PRIMARY KEY,
    name VARCHAR(255) NOT NULL
);

COMMENT ON TABLE departments IS '부서 관리';
COMMENT ON COLUMN departments.id IS '부서 고유번호';
COMMENT ON COLUMN departments.name IS '부서명';

CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    dept_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_users_dept FOREIGN KEY (dept_id) REFERENCES departments(id)
);

COMMENT ON TABLE users IS '사용자 관리';
COMMENT ON COLUMN users.id IS '사용자 고유번호';
COMMENT ON COLUMN users.email IS '이메일 주소';
COMMENT ON COLUMN users.dept_id IS '소속 부서 ID';
COMMENT ON COLUMN users.created_at IS '가입일';

CREATE UNIQUE INDEX idx_users_email ON users(email);
