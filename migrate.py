"""
Миграция для PostgreSQL (идемпотентная — можно запускать повторно).

Шаги:
1. Колонка avatar в таблице users
2. Таблица dogs
3. UNIQUE(user_id, event_id) в event_registrations — защита от двойной записи
4. Таблицы курса дрессировки: courses, course_sections, exercises, section_progress
5. Таблица course_enrollments — зачисление пользователей на курс (доступ)
6. Колонка photo в таблице dogs — фотография собаки
7. Таблица exercise_progress — прогресс по отдельным упражнениям
8. Дневник прогулки в section_progress: dog_id, started_at, note, rating,
   weather, actual_minutes; completed_at допускает NULL (прогулка начата, но
   не завершена)
9. Медиа к упражнению: колонки media и media_type в exercises
10. Бэкфилл: упражнения уже зачтённых прогулок отмечаются выполненными

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


def _has_column(cur, table: str, column: str) -> bool:
    """Есть ли колонка в таблице текущей схемы."""
    cur.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s AND table_schema = current_schema()
        """,
        (table, column),
    )
    return cur.fetchone() is not None


def _has_table(cur, table: str) -> bool:
    """Есть ли таблица в текущей схеме."""
    cur.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_name = %s AND table_schema = current_schema()
        """,
        (table,),
    )
    return cur.fetchone() is not None


def _has_constraint(cur, table: str, name: str) -> bool:
    """Есть ли ограничение с таким именем на таблице."""
    cur.execute(
        "SELECT 1 FROM pg_constraint WHERE conname = %s AND conrelid = %s::regclass",
        (name, table),
    )
    return cur.fetchone() is not None


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

        # 9. Фотография собаки. Таблица dogs создаётся в шаге 2 (или уже
        # существует на боевой базе), поэтому колонку добавляем отдельным
        # ALTER — так же идемпотентно, как avatar у users.
        print("\n📋 Шаг 9: Добавляем колонку photo в dogs...")
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'dogs' AND column_name = 'photo'
              AND table_schema = current_schema()
        """)
        if cur.fetchone():
            print("  ✓ колонка photo уже существует")
        else:
            cur.execute("ALTER TABLE dogs ADD COLUMN photo VARCHAR(255)")
            print("  ✓ колонка photo добавлена")

        # 10. Прогресс по отдельным упражнениям: без него виден только факт
        # «прогулка пройдена», а не «3 из 5 упражнений выполнено».
        print("\n📋 Шаг 10: Создаём таблицу exercise_progress...")
        if _has_table(cur, "exercise_progress"):
            print("  ✓ таблица exercise_progress уже существует")
        else:
            cur.execute("""
                CREATE TABLE exercise_progress (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    exercise_id INTEGER NOT NULL,
                    actual_seconds INTEGER NOT NULL DEFAULT 0,
                    completed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (exercise_id) REFERENCES exercises(id) ON DELETE CASCADE,
                    CONSTRAINT uq_exercise_progress_user_exercise UNIQUE (user_id, exercise_id)
                )
            """)
            print("  ✓ таблица exercise_progress создана")

        # 11. Дневник прогулки: с какой собакой гуляли, заметка, оценка, погода
        # и фактическое время. completed_at теперь может быть NULL — прогулка
        # бывает начата, но не завершена.
        print("\n📋 Шаг 11: Дневник прогулки в section_progress...")
        if not _has_table(cur, "section_progress"):
            print("  ⚠ таблица section_progress ещё не создана — пропускаем")
        else:
            if not _has_column(cur, "section_progress", "dog_id"):
                cur.execute("ALTER TABLE section_progress ADD COLUMN dog_id INTEGER")
                print("  ✓ колонка dog_id добавлена")
            if not _has_constraint(cur, "section_progress", "fk_section_progress_dog"):
                cur.execute("""
                    ALTER TABLE section_progress
                    ADD CONSTRAINT fk_section_progress_dog
                    FOREIGN KEY (dog_id) REFERENCES dogs(id) ON DELETE SET NULL
                """)
                print("  ✓ внешний ключ dog_id → dogs(id) добавлен")

            if not _has_column(cur, "section_progress", "started_at"):
                # Сначала nullable, потом заполняем по completed_at и только
                # затем NOT NULL: иначе старым записям в started_at попал бы
                # момент миграции, а не дата прогулки.
                cur.execute(
                    "ALTER TABLE section_progress ADD COLUMN started_at TIMESTAMP WITH TIME ZONE"
                )
                cur.execute("""
                    UPDATE section_progress
                    SET started_at = COALESCE(completed_at, CURRENT_TIMESTAMP)
                    WHERE started_at IS NULL
                """)
                cur.execute(
                    "ALTER TABLE section_progress ALTER COLUMN started_at "
                    "SET DEFAULT CURRENT_TIMESTAMP"
                )
                cur.execute(
                    "ALTER TABLE section_progress ALTER COLUMN started_at SET NOT NULL"
                )
                print("  ✓ колонка started_at добавлена")

            # Прогулку можно начать и не завершить → completed_at допускает NULL.
            cur.execute("ALTER TABLE section_progress ALTER COLUMN completed_at DROP NOT NULL")
            cur.execute("ALTER TABLE section_progress ALTER COLUMN completed_at DROP DEFAULT")
            print("  ✓ completed_at допускает NULL (прогулка начата, но не завершена)")

            for column, ddl in (
                ("note", "ADD COLUMN note TEXT NOT NULL DEFAULT ''"),
                ("weather", "ADD COLUMN weather VARCHAR(50) NOT NULL DEFAULT ''"),
                ("actual_minutes", "ADD COLUMN actual_minutes INTEGER NOT NULL DEFAULT 0"),
                ("rating", "ADD COLUMN rating INTEGER"),
            ):
                if not _has_column(cur, "section_progress", column):
                    cur.execute(f"ALTER TABLE section_progress {ddl}")
                    print(f"  ✓ колонка {column} добавлена")

            if not _has_constraint(cur, "section_progress", "ck_section_progress_rating"):
                cur.execute("""
                    ALTER TABLE section_progress
                    ADD CONSTRAINT ck_section_progress_rating
                    CHECK (rating IS NULL OR (rating >= 1 AND rating <= 5))
                """)
                print("  ✓ ограничение оценки 1..5 добавлено")

        # 12. Медиа к упражнению: имя файла и его вид (image/video).
        print("\n📋 Шаг 12: Медиа в exercises...")
        if not _has_table(cur, "exercises"):
            print("  ⚠ таблица exercises ещё не создана — пропускаем")
        else:
            if not _has_column(cur, "exercises", "media"):
                cur.execute("ALTER TABLE exercises ADD COLUMN media VARCHAR(255)")
                print("  ✓ колонка media добавлена")
            if not _has_column(cur, "exercises", "media_type"):
                cur.execute(
                    "ALTER TABLE exercises ADD COLUMN media_type VARCHAR(20) "
                    "NOT NULL DEFAULT 'image'"
                )
                print("  ✓ колонка media_type добавлена")

        # 13. Бэкфилл: упражнения уже зачтённых прогулок помечаем выполненными,
        # чтобы прогресс существующих пользователей не «обнулился» после
        # перехода на прогресс по упражнениям. ON CONFLICT — идемпотентно.
        print("\n📋 Шаг 13: Бэкфилл прогресса упражнений по пройденным прогулкам...")
        if _has_table(cur, "exercise_progress") and _has_table(cur, "section_progress"):
            cur.execute("""
                INSERT INTO exercise_progress (user_id, exercise_id, completed_at)
                SELECT sp.user_id, e.id, sp.completed_at
                FROM section_progress sp
                JOIN exercises e ON e.section_id = sp.section_id
                WHERE sp.completed_at IS NOT NULL
                ON CONFLICT (user_id, exercise_id) DO NOTHING
            """)
            print(f"  ✓ отмечено упражнений: {cur.rowcount}")
        else:
            print("  ⚠ нужные таблицы отсутствуют — пропускаем")

    conn.commit()
    conn.close()
    print("\n🎉 Миграция завершена!")


if __name__ == "__main__":
    migrate()
