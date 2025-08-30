import os
from pathlib import Path
from typing_extensions import Annotated
from pydantic import AfterValidator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

HomePath = Annotated[Path, AfterValidator(lambda v: v.expanduser())]


class ConfigServer(BaseSettings):
    """Configuration settings for the volexport application. (no default value)"""

    model_config = SettingsConfigDict(env_prefix="VOLEXP_", env_file=os.getenv("VOLEXP_ENV_FILE"))
    VG: str = Field(description="Volume Group name")
    NICS: list[str] = Field(description="List of network interfaces to use")


config2 = ConfigServer()  # type: ignore
