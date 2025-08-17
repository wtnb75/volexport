import subprocess
import shlex
from logging import getLogger
from .config import config

_log = getLogger(__name__)


def runcmd(cmd: list[str], root: bool = True):
    _log.info("run %s, root=%s", cmd, root)
    if root:
        if config.BECOME_METHOD == "su":
            cmd = ["su", "-c", shlex.join(cmd)]
        elif config.BECOME_METHOD.lower() not in ("none", "false"):
            cmd[0:0] = shlex.split(config.BECOME_METHOD)
    res = subprocess.run(
        cmd,
        capture_output=True,
        encoding="utf-8",
        timeout=config.CMD_TIMEOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    _log.info("returncode=%s, stdout=%s, stderr=%s", res.returncode, repr(res.stdout), repr(res.stderr))
    res.check_returncode()
    return res
