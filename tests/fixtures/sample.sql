-- tests/fixtures/sample.sql
CREATE TABLE departments (
    id BIGINT PRIMARY KEY,
    name VARCHAR(255) NOT NULL
);

CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    dept_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_users_dept FOREIGN KEY (dept_id) REFERENCES departments(id)
);

CREATE UNIQUE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_dept ON users(dept_id);
