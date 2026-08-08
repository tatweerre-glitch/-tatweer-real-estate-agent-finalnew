from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    company_name: str = "Tatweer Real Estate"
    default_language: str = "en"
    public_base_url: str = "http://127.0.0.1:8000"

    telegram_bot_token: str = ""
    admin_telegram_chat_id: str = ""

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""
    twilio_phone_number: str = ""
    admin_whatsapp_number: str = ""

    google_sheets_credentials_file: str = ""
    google_sheet_id: str = ""
    google_sheet_tab: str = "Appointments"


settings = Settings()
