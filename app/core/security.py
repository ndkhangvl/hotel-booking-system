from jose import jwt
from datetime import datetime, timedelta

SECRET_KEY = "ebf089601f786847849e7b39920150d83636f339b1a208f65609420653457049"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


def get_password_hash(password: str) -> str:
    """Không hash — trả về mật khẩu để lưu plain text."""
    return password


def verify_password(plain_password: str, stored_password: str) -> bool:
    """So sánh mật khẩu plain text."""
    if not plain_password or not stored_password:
        return False
    return plain_password == stored_password

def create_access_token(user_id: str, role: str = None) -> str:
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode = {
        "sub": str(user_id),
        "exp": expire
    }
    if role is not None:
        to_encode["role"] = role
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)