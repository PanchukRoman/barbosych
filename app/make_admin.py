"""Назначение/снятие роли администратора из командной строки.

Зачем так, а не HTTP-эндпоинтом: раньше был POST /auth/make-admin, который
разрешал ЛЮБОМУ авторизованному пользователю сделать администратором себя.
Повышение прав — операция уровня сервера, а не публичного API: теперь для неё
нужен доступ к машине и к базе, а не просто зарегистрированный аккаунт.

Запуск из корня проекта:
    python3 -m app.make_admin user@example.com
    python3 -m app.make_admin user@example.com --revoke
"""
import argparse
import sys

from .database import SessionLocal
from .models import User


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Назначить или снять роль администратора"
    )
    parser.add_argument("email", help="email пользователя")
    parser.add_argument(
        "--revoke",
        action="store_true",
        help="снять роль администратора (перевести в reader)",
    )
    args = parser.parse_args(argv)

    new_role = "reader" if args.revoke else "admin"

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == args.email).first()
        if user is None:
            print(f"❌ Пользователь {args.email} не найден")
            return 1

        # Та же защита, что и в API: не оставляем систему без администраторов
        if new_role == "reader" and user.role == "admin":
            admins_count = db.query(User).filter(User.role == "admin").count()
            if admins_count <= 1:
                print("❌ Это последний администратор — систему нельзя оставить без админов")
                return 1

        if user.role == new_role:
            print(f"ℹ️  У пользователя {args.email} уже роль {new_role}")
            return 0

        user.role = new_role
        db.commit()
        print(f"✅ {args.email}: роль изменена на {new_role}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
