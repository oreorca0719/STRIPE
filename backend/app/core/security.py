import secrets
import string
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from app.core.config import settings

# 임시 비밀번호 문자셋 — 사람이 눈으로 읽고 종이에 옮겨 적는 값이라
# 혼동되는 글자(0/O, 1/l/I)를 뺐다. 파일럿에서 아동이 잘못 입력해 로그인에
# 실패하면 진단 자체가 시작되지 않는다.
_TEMP_PW_ALPHABET = (
    "".join(c for c in string.ascii_lowercase if c not in "l")
    + "".join(c for c in string.ascii_uppercase if c not in "IO")
    + "".join(c for c in string.digits if c not in "01")
)
TEMP_PASSWORD_LENGTH = 10


def generate_temp_password(length: int = TEMP_PASSWORD_LENGTH) -> str:
    """계정 발급·비밀번호 초기화용 임시 비밀번호.

    관리자가 직접 정하게 두면 파일럿에서 여러 계정에 같은 값을 쓰기 쉬워
    서버가 매번 난수로 만든다. 평문은 응답으로 1회만 나가고 저장되지 않는다.
    """
    return "".join(secrets.choice(_TEMP_PW_ALPHABET) for _ in range(length))


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        return None
