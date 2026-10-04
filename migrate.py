"""
Миграция для PostgreSQL:
1. Добавляем колонку avatar в таблицу users
2. Создаём таблицу dogs

Запуск:
  python3 migrate.py
"""
import os
from dotenv import load_dotenv
import psycopg

load_dotenv()

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
            WHERE table_name = 'dogs'
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

    conn.commit()
    conn.close()
    print("\n🎉 Миграция завершена!")


if __name__ == "__main__":
    migrate()
