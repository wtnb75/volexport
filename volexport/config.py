import os
from pathlib import Path
from typing_extensions import Annotated
from pydantic import AfterValidator
from pydantic_settings import BaseSettings, SettingsConfigDict

HomePath = Annotated[Path, AfterValidator(lambda v: v.expanduser())]


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VOLEXP_", env_file=os.getenv("VOLEXP_ENV_FILE"))
    VG: str
    BECOME_METHOD: str = "sudo"
    TGTADM_BIN: str = "tgtadm"
    TGT_BSTYPE: str = "rdwr"
    TGT_BSOPTS: str | None = None
    TGT_BSOFLAGS: str | None = None
    LVM_BIN: str | None = None
    NICS: list[str]
    IQN_BASE: str = "iqn.2025-08.com.github.wtnb75"
    CMD_TIMEOUT: float = 10.0


config = Config()  # type: ignore
