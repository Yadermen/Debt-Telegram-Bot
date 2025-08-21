import os
from dataclasses import dataclass
from typing import List

@dataclass
class Config:
    bot_token: str
    admin_ids: List[int]
    db_path: str

def load_config() -> Config:
    return Config(
        bot_token=os.getenv("BOT_TOKEN"),
        admin_ids=[int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()],
        db_path=os.getenv("DB_PATH", "debts.db")
    )