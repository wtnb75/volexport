import os
import click
import uvicorn
from logging import getLogger
from .cli_utils import verbose_option
from .version import VERSION

_log = getLogger(__name__)


@click.version_option(version=VERSION, prog_name="volexport")
@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
@verbose_option
@click.option("--become-method", help="sudo/doas/runas, etc...")
@click.option("--tgtadm-bin", help="tgtadm command")
@click.option("--tgt-bstype", help="backing store type")
@click.option("--tgt-bsopts", help="bs options")
@click.option("--tgt-bsoflags", help="bs open flags")
@click.option("--lvm-bin", help="lvm command")
@click.option("--nics", multiple=True, help="use interfaces")
@click.option("--iqn-base", help="iSCSI target basename")
@click.option("--vg", help="LVM volume group")
@click.option("--host", default="127.0.0.1", envvar="VOLEXP_HOST", help="listen host")
@click.option("--port", default=8080, type=int, envvar="VOLEXP_PORT", help="listen port")
@click.option("--log-config", type=click.Path(), help="uvicorn log config")
@click.option("--cmd-timeout", type=float, envvar="VOLEXP_CMD_TIMEOUT", help="command execution timeout")
@click.option("--check/--skip-check", default=True, help="pre-boot check")
def server(host, port, log_config, check, **kwargs):
    """Run the volexport server."""
    import json

    for k, v in kwargs.items():
        if k is None or v is None or (isinstance(v, tuple) and len(v) == 0):
            continue
        kk = f"VOLEXP_{k.upper()}"
        if isinstance(v, tuple):
            vv = json.dumps(list(v))
        else:
            vv = v
        os.environ[kk] = vv

    from .api import api
    from .config import config
    from .config2 import config2
    from .lvm2 import VG
    from .tgtd import Tgtd

    _log.debug("config: %s", config)
    if log_config is None:
        getLogger("uvicorn").setLevel("INFO")

    # pre-boot check
    if check:
        if os.getuid() == 0 and config.BECOME_METHOD:
            _log.info("you are already root. disable become_method")
            config.BECOME_METHOD = ""
        assert VG(config2.VG).get() is not None
        assert Tgtd().sys_show() is not None

    # start server
    uvicorn.run(api, host=host, port=port, log_config=log_config)


@cli.command()
@click.option("--format", type=click.Choice(["yaml", "json"]), default="yaml", show_default=True)
def apispec(format):
    """Generate OpenAPI specification for the volexport API."""
    import sys

    os.environ["VOLEXP_VG"] = "dummy"
    os.environ["VOLEXP_NICS"] = "[]"
    from .api import api

    if format == "yaml":
        import yaml

        yaml.dump(api.openapi(), stream=sys.stdout)
    elif format == "json":
        import json

        json.dump(api.openapi(), fp=sys.stdout)


if __name__ == "__main__":
    cli()
