import os
import click
import uvicorn
import functools
from typing import Optional
from logging import getLogger
from .version import VERSION

_log = getLogger(__name__)


@click.version_option(version=VERSION, prog_name="volexport")
@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def set_verbose(verbose: Optional[bool]):
    from logging import basicConfig

    fmt = "%(asctime)s %(levelname)s %(name)s %(message)s"
    level = "INFO"
    if verbose:
        level = "DEBUG"
    elif verbose is not None:
        level = "WARNING"
    basicConfig(level=level, format=fmt)


def verbose_option(func):
    @functools.wraps(func)
    def wrap(verbose, *args, **kwargs):
        set_verbose(verbose)
        return func(*args, **kwargs)

    return click.option("--verbose/--quiet", help="log level")(wrap)


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
@click.option("--host", default="127.0.0.1", help="listen host")
@click.option("--port", default=8080, type=int, help="listen port")
@click.option("--log-config", type=click.Path(), help="uvicorn log config")
@click.option("--cmd-timeout", type=float, help="command execution timeout")
def server(host, port, log_config, **kwargs):
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

    _log.debug("config: %s", config)
    if log_config is None:
        getLogger("uvicorn").setLevel("INFO")

    uvicorn.run(api, host=host, port=port, log_config=log_config)


@cli.command()
@click.option("--format", type=click.Choice(["yaml", "json"]), default="yaml", show_default=True)
def apispec(format):
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
