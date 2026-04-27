import argparse
import getpass

from .app.auth import hash_password
from .app.config import settings
from .app.user_store import UserRole, UserStore, normalize_username


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or update a TeleAI BFF user.")
    parser.add_argument("--username", required=True, help="Login username")
    parser.add_argument("--role", choices=("admin", "user"), default="user", help="User role")
    parser.add_argument("--password", default="", help="Password; if omitted, prompt securely")
    parser.add_argument("--disabled", action="store_true", help="Create or update the account in disabled state")
    return parser.parse_args()


def read_password(raw_password: str) -> str:
    if raw_password:
        return raw_password
    first = getpass.getpass("Password: ")
    second = getpass.getpass("Confirm password: ")
    if first != second:
        raise SystemExit("passwords do not match")
    if not first:
        raise SystemExit("password must not be empty")
    return first


def main() -> None:
    args = parse_args()
    username = normalize_username(args.username)
    password = read_password(args.password)
    role: UserRole = args.role

    store = UserStore(settings.auth_users_file)
    password_hash = hash_password(password, iterations=settings.password_hash_iterations)
    user = store.upsert(username=username, password_hash=password_hash, role=role, enabled=not args.disabled)
    print(
        f"saved user username={user.username} role={user.role} enabled={user.enabled} "
        f"users_file={settings.auth_users_file}"
    )


if __name__ == "__main__":
    main()
