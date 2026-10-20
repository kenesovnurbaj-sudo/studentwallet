import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
import jwt

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 часа

# bcrypt учитывает только первые 72 БАЙТА пароля, а новые версии библиотеки
# на более длинном пароле бросают ValueError (это и давало 500).
# Кириллица занимает 2 байта на символ, поэтому ограничиваем именно байты.
BCRYPT_MAX_BYTES = 72

# Файл, куда сохраняется сгенерированный ключ, если SECRET_KEY не задан.
SECRET_KEY_FILE = Path(os.getenv("SECRET_KEY_FILE", Path(__file__).resolve().parent.parent / ".secret_key"))


def _load_secret_key() -> str:
    """Ключ подписи JWT.

    Раньше по умолчанию был ключ "dev-secret-change-me" из публичного репозитория:
    с ним любой мог подписать токен с чужим user_id. Теперь:
    1) берём SECRET_KEY из окружения (так надо делать на сервере);
    2) иначе читаем локальный файл .secret_key (он в .gitignore);
    3) иначе генерируем случайный ключ и сохраняем его в этот файл,
       чтобы токены не слетали после перезапуска.
    """
    env_key = os.getenv("SECRET_KEY")
    if env_key:
        if len(env_key) < 32:
            logger.warning("SECRET_KEY is shorter than 32 characters; use a long random value")
        return env_key

    try:
        saved = SECRET_KEY_FILE.read_text(encoding="utf-8").strip()
        if saved:
            return saved
    except FileNotFoundError:
        pass

    key = secrets.token_urlsafe(64)
    try:
        SECRET_KEY_FILE.write_text(key, encoding="utf-8")
        os.chmod(SECRET_KEY_FILE, 0o600)
        logger.warning("SECRET_KEY is not set; generated a random key in %s", SECRET_KEY_FILE)
    except OSError:
        # Нет прав на запись: работаем с ключом только в памяти (токены сбросятся при перезапуске).
        logger.warning("SECRET_KEY is not set and %s is not writable; using a temporary key", SECRET_KEY_FILE)
    return key


SECRET_KEY = _load_secret_key()


def password_too_long(password: str) -> bool:
    return len(password.encode("utf-8")) > BCRYPT_MAX_BYTES


def hash_password(password: str) -> str:
    if password_too_long(password):
        raise ValueError("Password is longer than 72 bytes")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    # Такой пароль не мог пройти регистрацию, значит он точно неверный. Не отдаём его в bcrypt.
    if password_too_long(password):
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Повреждённый хеш в базе: считаем пароль неверным, а не падаем с 500.
        return False


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
