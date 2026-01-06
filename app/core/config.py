from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    app_title: str = "FocusFlight"
    db_path: str = "focusflight.db"

settings = Settings()
