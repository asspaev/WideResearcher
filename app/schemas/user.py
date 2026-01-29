from datetime import datetime

from pydantic import BaseModel


class UserCookie(BaseModel):
    """Модель User из Cookie из токена access_token"""

    user_id: int
    user_login: str
    meta_created_at: datetime
