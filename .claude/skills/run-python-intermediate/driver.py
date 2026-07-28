#!/usr/bin/env python3
"""Драйвер для запуска и прогона python-intermediate.

Запуск: uv run python .claude/skills/run-python-intermediate/driver.py <команда>
Команды: up | smoke | token | down | reset | logs
"""

import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[3]
BASE_URL = os.environ.get("DRIVER_BASE_URL", "http://127.0.0.1:8010")
REST = f"{BASE_URL}/v1/api"
GQL = f"{BASE_URL}/v1/gql"

# Драйвер не полагается на .env — переменные передаются явно, чтобы работать
# на машине, где .env ещё не заполнен.
HOST_DB_ENV = {
    "SYNC_DATABASE_URL": "postgresql+psycopg2://postgres:password@localhost:5432/mydatabase",
    "ASYNC_DATABASE_URL": "postgresql+asyncpg://postgres:password@localhost:5432/mydatabase",
    "TEST_DATABASE_URL": "postgresql+asyncpg://postgres:password@localhost:5432/testdatabase",
}

passed = 0
failed = 0


def run(command, **kwargs):
    print(f"$ {' '.join(command)}")
    return subprocess.run(command, cwd=ROOT, check=True, **kwargs)


def check(label, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  OK   {label}")
        return True
    failed += 1
    print(f"  FAIL {label}{f' — {detail}' if detail else ''}")
    return False


def wait_for_app(timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(f"{BASE_URL}/docs", timeout=2).status_code == 200:
                print(f"приложение отвечает на {BASE_URL}")
                return True
        except httpx.HTTPError:
            pass
        time.sleep(1)
    print(f"приложение не поднялось за {timeout}с", file=sys.stderr)
    return False


def migrate():
    env = {**os.environ, **HOST_DB_ENV}
    run(["uv", "run", "alembic", "upgrade", "head"], env=env)


def cmd_up():
    run(["docker", "compose", "up", "-d", "--build"])
    if not wait_for_app():
        sys.exit(1)
    # Без миграций приложение стартует, но любая запись падает 500.
    migrate()
    print("готово: стек поднят, схема накатана")


def cmd_down():
    run(["docker", "compose", "down"])


def cmd_reset():
    run(["docker", "compose", "down", "-v"])
    cmd_up()


def cmd_logs():
    run(["docker", "compose", "logs", "--tail", "50", "web_app"])


def register(client, username, password, email, is_admin=False, permissions=None):
    body = {"username": username, "password": password, "email": email, "is_admin": is_admin}
    if permissions is not None:
        body["permissions"] = permissions
    return client.post(f"{REST}/users", json=body)


def login(client, username, password):
    """Логин — GET с query-параметрами, не POST с телом."""
    return client.get(f"{REST}/users/login", params={"username": username, "password": password})


def auth(token):
    """Токен идёт в Authorization голым, без префикса Bearer (APIKeyHeader)."""
    return {"Authorization": token}


def gql(client, query, token=None, variables=None):
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    return client.post(GQL, json=payload, headers=auth(token) if token else {})


def cmd_smoke():
    if not wait_for_app(timeout=10):
        print("сначала подними стек: driver.py up", file=sys.stderr)
        sys.exit(1)

    # Уникальный суффикс: username/email уникальны в БД, имя файла — на диске,
    # и то и другое переживает перезапуск стека.
    tag = uuid.uuid4().hex[:8]
    admin, regular = f"admin_{tag}", f"regular_{tag}"
    password = "pass"

    with httpx.Client(timeout=15) as client:
        print("\n[1] регистрация через тело запроса")
        response = register(client, admin, password, f"{admin}@example.com", is_admin=True)
        check("админ создан", response.status_code == 200, f"{response.status_code} {response.text}")
        response = register(client, regular, password, f"{regular}@example.com", permissions=["view_product"])
        check("обычный пользователь создан", response.status_code == 200, response.text)
        response = register(client, admin, password, f"{admin}@example.com")
        check("дубликат отбит 400", response.status_code == 400, str(response.status_code))

        print("\n[2] аутентификация")
        response = login(client, admin, password)
        check("логин отдал пару токенов", response.status_code == 200, response.text)
        tokens = response.json()
        admin_token, refresh = tokens["access_token"], tokens["refresh_token"]
        regular_token = login(client, regular, password).json()["access_token"]

        response = client.get(f"{REST}/users/me", headers=auth(admin_token))
        check("/users/me узнаёт админа", response.json().get("message") == f"Hello, {admin}!", response.text)
        response = client.get(f"{REST}/users/refresh", params={"token": refresh})
        check("refresh обменян на access", "access_token" in response.json(), response.text)
        response = client.get(f"{REST}/users/me", headers=auth(refresh))
        check("refresh не проходит как access (401)", response.status_code == 401, str(response.status_code))
        response = client.get(f"{REST}/users/me", headers=auth("garbage"))
        check("мусорный токен → 401", response.status_code == 401, str(response.status_code))

        print("\n[3] права")
        response = client.get(f"{REST}/users", headers=auth(admin_token))
        check("админ видит список пользователей", response.status_code == 200, response.text)
        usernames = [user["username"] for user in response.json()]
        check("оба пользователя в БД", admin in usernames and regular in usernames)
        response = client.get(f"{REST}/users", headers=auth(regular_token))
        check("обычному список закрыт (403)", response.status_code == 403, str(response.status_code))

        print("\n[4] товары (хранятся в памяти процесса)")
        product_id = int(tag[:6], 16)
        product = {"id": product_id, "name": "Book", "price": 10.0, "quantity": 1}
        response = client.post(f"{REST}/products", json=product, headers=auth(admin_token))
        check("админ создал товар", response.status_code == 200, response.text)
        response = client.get(f"{REST}/products/{product_id}", headers=auth(regular_token))
        check("обычный читает товар по праву view_product", response.status_code == 200, response.text)
        response = client.post(f"{REST}/products", json=product, headers=auth(regular_token))
        check("обычному создание закрыто (403)", response.status_code == 403, str(response.status_code))
        response = client.get(f"{REST}/products/999999", headers=auth(admin_token))
        check("несуществующий товар → 404", response.status_code == 404, str(response.status_code))

        print("\n[5] GraphQL")
        gql_user = f"gql_{tag}"
        response = gql(
            client,
            'mutation { register(username: "%s", password: "%s", email: "%s@example.com") { username email } }'
            % (gql_user, password, gql_user),
        )
        check(
            "мутация register",
            response.json().get("data", {}).get("register", {}).get("username") == gql_user,
            response.text,
        )
        response = gql(client, "{ allUsers(limit: 100) { items { username } total } }", token=admin_token)
        check("allUsers с токеном админа", "errors" not in response.json(), response.text)
        response = gql(client, "{ allUsers { total } }")
        errors = response.json().get("errors", [])
        check(
            "allUsers без токена → Authentication required (HTTP 200!)",
            response.status_code == 200 and errors and errors[0]["message"] == "Authentication required",
            response.text,
        )

        print("\n[6] загрузка файла (GraphQL multipart) и раздача /media")
        filename = f"driver_{tag}.txt"
        content = b"uploaded by driver\n"
        operations = json.dumps(
            {
                "query": "mutation($file: Upload!) { uploadFile(file: $file) { filename url } }",
                "variables": {"file": None},
            }
        )
        response = client.post(
            GQL,
            headers=auth(admin_token),
            data={"operations": operations, "map": json.dumps({"0": ["variables.file"]})},
            files={"0": (filename, content, "text/plain")},
        )
        uploaded = response.json().get("data", {}).get("uploadFile") or {}
        check("файл загружен", uploaded.get("filename") == filename, response.text)
        if uploaded.get("url"):
            response = client.get(f"{BASE_URL}{uploaded['url']}")
            check("файл раздаётся по /media", response.content == content, response.text)
        response = gql(client, "{ files(limit: 100) { total } }", token=admin_token)
        check(
            "files виден в query", response.json().get("data", {}).get("files", {}).get("total", 0) >= 1, response.text
        )

    print(f"\n=== пройдено {passed}, провалено {failed} ===")
    sys.exit(1 if failed else 0)


def cmd_token():
    username = sys.argv[2] if len(sys.argv) > 2 else "admin"
    password = sys.argv[3] if len(sys.argv) > 3 else "pass"
    with httpx.Client(timeout=15) as client:
        response = login(client, username, password)
        if response.status_code != 200:
            print(f"логин не прошёл: {response.status_code} {response.text}", file=sys.stderr)
            sys.exit(1)
        print(response.json()["access_token"])


COMMANDS = {
    "up": cmd_up,
    "smoke": cmd_smoke,
    "down": cmd_down,
    "reset": cmd_reset,
    "logs": cmd_logs,
    "token": cmd_token,
}

if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command not in COMMANDS:
        print(f"использование: driver.py [{' | '.join(COMMANDS)}]", file=sys.stderr)
        sys.exit(2)
    COMMANDS[command]()
