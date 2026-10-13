"""
Миграция для PostgreSQL (идемпотентная — можно запускать повторно).

Шаги:
1. Колонка avatar в таблице users
2. Таблица dogs
3. UNIQUE(user_id, event_id) в event_registrations — защита от двойной записи
4. Таблицы курса дрессировки: courses, course_sections, exercises, section_progress
5. Таблица course_enrollments — зачисление пользователей на курс (доступ)

Запуск из корня проекта:
  python3 migrate.py
"""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

# Путь к .env — абсолютный (рядом с этим файлом): без аргумента python-dotenv
# определяет файл через разбор стека вызовов, что на новых версиях Python
# срабатывает не всегда, а относительный путь ломается при запуске не из корня.
load_dotenv(Path(__file__).resolve().parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")


def parse_pg_url(url: str) -> str:
    """
    Парсит формат SQLAlchemy postgresql+psycopg://user:pass@host:port/db
    в формат psycopg postgresql://user:pass@host:port/db
    """
    # Убираем +psycopg (оставляем только postgresql://)
    if "+psycopg" in url:
        url = url.replace("+psycopg", "")
    return url


def migrate():
    if not DATABASE_URL:
        print("❌ DATABASE_URL не найден в .env")
        return

    clean_url = parse_pg_url(DATABASE_URL)

    print("🔌 Подключение к PostgreSQL...")
    try:
        conn = psycopg.connect(clean_url)
    except Exception as e:
        print(f"❌ Не удалось подключиться: {e}")
        return

    print("✅ Подключено")

    with conn.cursor() as cur:
        # 1. Добавляем колонку avatar
        print("\n📋 Шаг 1: Добавляем колонку avatar в users...")
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'avatar'
              AND table_schema = current_schema()
        """)
        if cur.fetchone():
            print("  ✓ колонка avatar уже существует")
        else:
            cur.execute("ALTER TABLE users ADD COLUMN avatar VARCHAR(255)")
            print("  ✓ колонка avatar добавлена")

        # 2. Создаём таблицу dogs
        print("\n📋 Шаг 2: Создаём таблицу dogs...")
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'dogs' AND table_schema = current_schema()
        """)
        if cur.fetchone():
            print("  ✓ таблица dogs уже существует")
        else:
            cur.execute("""
                CREATE TABLE dogs (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    breed VARCHAR(100) NOT NULL,
                    age INTEGER NOT NULL,
                    owner_id INTEGER NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            print("  ✓ таблица dogs создана")

        # 3. Уникальность пары (user_id, event_id) — один пользователь
        #    записывается на событие не более одного раза на уровне БД.
        print("\n📋 Шаг 3: Уникальность пары (user_id, event_id) в event_registrations...")
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'event_registrations' AND table_schema = current_schema()
        """)
        if not cur.fetchone():
            print("  ⚠ таблица event_registrations ещё не создана — пропускаем")
        else:
            cur.execute("""
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_event_registration_user_event'
                  AND conrelid = 'event_registrations'::regclass
            """)
            if cur.fetchone():
                print("  ✓ ограничение уже существует")
            else:
                # В старой базе могли остаться дубли. Без чистки ALTER TABLE упадёт,
                # поэтому оставляем самую раннюю запись, остальные удаляем.
                cur.execute("""
                    DELETE FROM event_registrations a
                    USING event_registrations b
                    WHERE a.id > b.id
                      AND a.user_id = b.user_id
                      AND a.event_id = b.event_id
                """)
                removed = cur.rowcount
                if removed:
                    print(f"  ✓ удалено дублирующих записей: {removed}")
                cur.execute("""
                    ALTER TABLE event_registrations
                    ADD CONSTRAINT uq_event_registration_user_event
                    UNIQUE (user_id, event_id)
                """)
                print("  ✓ ограничение добавлено")


        # 4-7. Курс дрессировки: курс → секции (прогулка) → упражнения,
        #      плюс отметки пользователей о пройденных секциях.
        print("\n📋 Шаг 4: Создаём таблицу courses...")
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'courses' AND table_schema = current_schema()
        """)
        if cur.fetchone():
            print("  ✓ таблица courses уже существует")
        else:
            cur.execute("""
                CREATE TABLE courses (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    description TEXT DEFAULT '',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    author_id INTEGER NOT NULL,
                    FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            print("  ✓ таблица courses создана")

        print("\n📋 Шаг 5: Создаём таблицу course_sections...")
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'course_sections' AND table_schema = current_schema()
        """)
        if cur.fetchone():
            print("  ✓ таблица course_sections уже существует")
        else:
            cur.execute("""
                CREATE TABLE course_sections (
                    id SERIAL PRIMARY KEY,
                    course_id INTEGER NOT NULL,
                    order_index INTEGER NOT NULL DEFAULT 0,
                    title VARCHAR(255) NOT NULL,
                    description TEXT DEFAULT '',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
                )
            """)
            print("  ✓ таблица course_sections создана")

        print("\n📋 Шаг 6: Создаём таблицу exercises...")
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'exercises' AND table_schema = current_schema()
        """)
        if cur.fetchone():
            print("  ✓ таблица exercises уже существует")
        else:
            cur.execute("""
                CREATE TABLE exercises (
                    id SERIAL PRIMARY KEY,
                    section_id INTEGER NOT NULL,
                    order_index INTEGER NOT NULL DEFAULT 0,
                    title VARCHAR(255) NOT NULL,
                    description TEXT DEFAULT '',
                    repetitions VARCHAR(100) DEFAULT '',
                    duration_minutes INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (section_id) REFERENCES course_sections(id) ON DELETE CASCADE
                )
            """)
            print("  ✓ таблица exercises создана")

        print("\n📋 Шаг 7: Создаём таблицу section_progress...")
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'section_progress' AND table_schema = current_schema()
        """)
        if cur.fetchone():
            print("  ✓ таблица section_progress уже существует")
        else:
            cur.execute("""
                CREATE TABLE section_progress (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    section_id INTEGER NOT NULL,
                    completed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (section_id) REFERENCES course_sections(id) ON DELETE CASCADE,
                    CONSTRAINT uq_section_progress_user_section UNIQUE (user_id, section_id)
                )
            """)
            print("  ✓ таблица section_progress создана")

        # 8. Зачисление пользователей на курс (доступ к прохождению).
        print("\n📋 Шаг 8: Создаём таблицу course_enrollments...")
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'course_enrollments' AND table_schema = current_schema()
        """)
        if cur.fetchone():
            print("  ✓ таблица course_enrollments уже существует")
        else:
            cur.execute("""
                CREATE TABLE course_enrollments (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    course_id INTEGER NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
                    CONSTRAINT uq_course_enrollment_user_course UNIQUE (user_id, course_id)
                )
            """)
            print("  ✓ таблица course_enrollments создана")

    conn.commit()
    conn.close()
    print("\n🎉 Миграция завершена!")


if __name__ == "__main__":
    migrate()
