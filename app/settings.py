from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    signnow_api_host: str = "https://api.signnow.com"
    signnow_api_basic_token: str = ""
    signnow_api_username: str = ""
    signnow_api_password: str = ""
    signnow_downloads_dir: str = "/tmp/signnow-downloads"
    sn_signer_email: str = "signer@signnow.com"


settings = Settings()
