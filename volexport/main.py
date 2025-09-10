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
@click.option("--lvm-thinpool", help="LVM thin pool")
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


@cli.command()
@verbose_option
@click.option("--endpoint", required=True, help="volexport endpoint")
@click.option("--node-id", required=True, help="node id")
@click.option(
    "--hostport", default="127.0.0.1:9999", show_default=True, help="listen host:port, unix socket: unix://(path)"
)
@click.option("--private-key", type=click.File("r"), help="private key .pem file for TLS")
@click.option("--cert", type=click.File("r"), help="certificate .pem file for TLS")
@click.option("--rootcert", type=click.File("r"), help="ca cert for TLS/mTLS")
@click.option("--use-mtls/--no-mtls", default=False, show_default=True, help="use client auth")
@click.option("--max-workers", type=int, help="# of workers")
def csiserver(hostport, endpoint, node_id, private_key, cert, rootcert, use_mtls, max_workers):
    """Run the CSI driver service"""
    from pathlib import Path
    from volexpcsi.server import boot_server

    _log.info("starting server: %s", hostport)
    conf = dict(endpoint=endpoint, nodeid=node_id, max_workers=max_workers)
    if private_key and cert:
        import grpc

        pkey = Path(private_key).read_bytes()
        chain = Path(cert).read_bytes()
        root = None
        if rootcert:
            root = Path(rootcert).read_bytes()
        cred = grpc.ssl_server_credentials(
            [(pkey, chain)],
            root,
            require_client_auth=use_mtls,
        )
        port, srv = boot_server(hostport=hostport, config=conf, cred=cred)
    else:
        port, srv = boot_server(hostport=hostport, config=conf)
    _log.info("server started: port=%s", port)
    exit = srv.wait_for_termination()
    _log.info("server finished: timeout=%s", exit)


if __name__ == "__main__":
    cli()
