import click
import requests
import functools
from urllib.parse import urljoin
from logging import getLogger
from .cli_utils import verbose_option, SizeType, output_format
from .version import VERSION

_log = getLogger(__name__)


class VERequest(requests.Session):
    def __init__(self, baseurl: str):
        super().__init__()
        self.baseurl = baseurl

    def request(self, method, path, *args, **kwargs):
        url = urljoin(self.baseurl.removesuffix("/") + "/", path.removeprefix("/"))
        _log.debug("request: method=%s url=%s args=%s", method, url, kwargs.get("json") or kwargs.get("data"))
        res = super().request(method, url, *args, **kwargs)
        try:
            _log.debug(
                "response(json): elapsed=%s method=%s url=%s code=%s, body=%s",
                res.elapsed,
                method,
                url,
                res.status_code,
                res.json(),
            )
        except Exception:
            _log.debug(
                "response(text): elapsed=%s method=%s url=%s code=%s, body=%s",
                res.elapsed,
                method,
                url,
                res.status_code,
                res.text,
            )
        return res


def client_option(func):
    @functools.wraps(func)
    def wrap(endpoint, *args, **kwargs):
        req = VERequest(endpoint)
        return func(req=req, *args, **kwargs)

    return click.option(
        "--endpoint", envvar="VOLEXP_ENDPOINT", default="http://localhost:8000", show_default=True, show_envvar=True
    )(wrap)


@click.version_option(version=VERSION, prog_name="volexport-client")
@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
@verbose_option
@client_option
@output_format
def volume_list(req):
    """list volumes"""
    res = req.get("/volume")
    res.raise_for_status()
    return res.json()


@cli.command()
@verbose_option
@client_option
@output_format
def volume_stats(req):
    """show volume stats"""
    res = req.get("/stats/volume")
    res.raise_for_status()
    return res.json()


@cli.command()
@verbose_option
@client_option
@output_format
@click.option("--name", required=True, help="volume name")
@click.option("--size", type=SizeType(), help="volume size", required=True)
def volume_create(req, name, size):
    """create new volume"""
    res = req.post("/volume", json={"name": name, "size": size})
    res.raise_for_status()
    return res.json()


@cli.command()
@verbose_option
@client_option
@output_format
@click.option("--name", required=True, help="volume name")
def volume_read(req, name):
    """show volume info"""
    res = req.get(f"/volume/{name}")
    res.raise_for_status()
    return res.json()


@cli.command()
@verbose_option
@client_option
@output_format
@click.option("--name", required=True, help="volume name")
@click.option("--readonly/--readwrite", help="ro/rw", default=True, show_default=True)
def volume_readonly(req, name, readonly):
    """set volume readonly/readwrite"""
    res = req.post(f"/volume/{name}", json={"readonly": readonly})
    res.raise_for_status()
    return res.json()


@cli.command()
@verbose_option
@client_option
@output_format
@click.option("--name", required=True, help="volume name")
@click.option("--size", type=SizeType(), help="volume size", required=True)
def volume_resize(req, name, size):
    """resize volume"""
    res = req.post(f"/volume/{name}", json={"size": size})
    res.raise_for_status()
    return res.json()


@cli.command()
@verbose_option
@client_option
@output_format
@click.option("--name", required=True, help="volume name")
def volume_delete(req, name):
    """delete volume"""
    res = req.delete(f"/volume/{name}")
    res.raise_for_status()
    return res.json()


@cli.command()
@verbose_option
@client_option
@output_format
def export_list(req):
    """list exports"""
    res = req.get("/export")
    res.raise_for_status()
    return res.json()


@cli.command()
@verbose_option
@client_option
@output_format
def export_stats(req):
    """show export stats"""
    res = req.get("/stats/export")
    res.raise_for_status()
    return res.json()


@cli.command()
@verbose_option
@client_option
@output_format
@click.option("--name", required=True, help="volume name")
@click.option("--show-command/--no-command", default=True, show_default=True)
@click.option("--acl", multiple=True, help="access control list")
def export_create(req, name, acl, show_command):
    """create new export"""
    res = req.post("/export", json={"volname": name, "acl": list(acl)})
    res.raise_for_status()
    if show_command:
        data = res.json()
        click.echo(f"""
iscsiadm -m discovery -t st -p {data["addresses"][0]}
iscsiadm -m node -T {data["targetname"]} -o update -n node.session.auth.authmethod -v CHAP
iscsiadm -m node -T {data["targetname"]} -o update -n node.session.auth.username -v {data["user"]}
iscsiadm -m node -T {data["targetname"]} -o update -n node.session.auth.password -v {data["passwd"]}
iscsiadm -m node -T {data["targetname"]} -l
""")
    return res.json()


@cli.command()
@verbose_option
@client_option
@output_format
@click.option("--targetname", required=True, help="target name")
def export_read(req, targetname):
    """show export info"""
    res = req.get(f"/export/{targetname}")
    res.raise_for_status()
    return res.json()


@cli.command()
@verbose_option
@client_option
@output_format
@click.option("--targetname", required=True, help="target name")
def export_delete(req, targetname):
    """delete export"""
    res = req.delete(f"/export/{targetname}")
    res.raise_for_status()
    return res.json()


@cli.command()
@verbose_option
@client_option
@output_format
def address(req):
    """show address"""
    res = req.get("/address")
    res.raise_for_status()
    return res.json()


@cli.command()
@verbose_option
@client_option
@output_format
def backup_list(req):
    """show backups"""
    res = req.get("/mgmt/backup")
    res.raise_for_status()
    return res.json()


@cli.command()
@verbose_option
@client_option
@output_format
def backup_create(req):
    """create backups"""
    res = req.post("/mgmt/backup")
    res.raise_for_status()
    return res.json()


@cli.command()
@verbose_option
@client_option
@click.option("--name", required=True, help="name of backup")
def backup_read(req, name):
    """read backups"""
    res = req.get(f"/mgmt/backup/{name}")
    res.raise_for_status()
    click.echo(res.text, nl=False)


@cli.command()
@verbose_option
@client_option
@output_format
@click.option("--name", required=True, help="name of backup")
def backup_restore(req, name):
    """read backups"""
    res = req.post(f"/mgmt/backup/{name}")
    res.raise_for_status()
    return res.json()


@cli.command()
@verbose_option
@client_option
@output_format
@click.option("--name", required=True, help="name of backup")
@click.option("--input", type=click.File("r"))
def backup_put(req, name, input):
    """put saved backups"""
    res = req.put(f"/mgmt/backup/{name}", data=input.read())
    res.raise_for_status()
    return res.json()


@cli.command()
@verbose_option
@client_option
@output_format
@click.option("--keep", type=int, default=2, show_default=True)
def backup_forget(req, keep):
    """forget old backups"""
    res = req.delete("/mgmt/backup", params={"keep": keep})
    res.raise_for_status()
    return res.json()


@cli.command()
@verbose_option
@client_option
@output_format
@click.option("--name", required=True, help="name of backup")
def backup_delete(req, name):
    """delete old backups"""
    res = req.delete(f"/mgmt/backup/{name}")
    res.raise_for_status()
    return res.json()


if __name__ == "__main__":
    cli()
