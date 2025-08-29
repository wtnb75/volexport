import os
from pathlib import Path
from typing_extensions import Annotated
from pydantic import AfterValidator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

HomePath = Annotated[Path, AfterValidator(lambda v: v.expanduser())]


class Config(BaseSettings):
    """Configuration settings for the volexport application."""

    model_config = SettingsConfigDict(env_prefix="VOLEXP_", env_file=os.getenv("VOLEXP_ENV_FILE"))
    BECOME_METHOD: str = Field(default="sudo", description='Method to become root, e.g., "sudo" or "doas"')
    TGTADM_BIN: str = Field(default="tgtadm", description="Path to tgtadm binary")
    TGT_BSTYPE: str = Field(default="rdwr", description='Type of block storage, e.g., "rdwr" or "aio"')
    TGT_BSOPTS: str | None = Field(default=None, description="Additional options for block storage")
    TGT_BSOFLAGS: str | None = Field(default=None, description="Additional flags for block storage")
    LVM_BIN: str | None = Field(default=None, description="Path to lvm binary")
    IQN_BASE: str = Field(default="iqn.2025-08.com.github.wtnb75", description="Base IQN for iSCSI targets")
    CMD_TIMEOUT: float = Field(default=10.0, description="Timeout for commands in seconds")
    BACKUP_DIR: str = Field(default="/tmp", description="backup directory")


config = Config()  # type: ignore
