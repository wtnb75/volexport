import click
import requests
import functools
from pathlib import Path
from urllib.parse import urljoin, urlparse
from logging import getLogger
from .cli_utils import verbose_option, SizeType, output_format
from .util import runcmd
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
            if res.status_code == requests.codes.unprocessable:
                errs = res.json().get("detail", [])
                for err in errs:
                    _log.warning("validation error at %s: %s", ".".join(err.get("loc", [])), err.get("msg"))
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
@click.option("--filesystem", default="ext4", help="filesystem")
@click.option("--label")
def volume_mkfs(req, name, filesystem, label):
    """mkfs volume"""
    res = req.post(f"/volume/{name}/mkfs", json={"filesystem": filesystem, "label": label})
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
def export_create(req: VERequest, name, acl, show_command):
    """create new export"""
    res = req.post("/export", json={"volname": name, "acl": list(acl)})
    res.raise_for_status()
    if show_command:
        data = res.json()
        addrs = data["addresses"]
        if addrs:
            addr = addrs[0]
        else:
            _log.warning("volexp returns no ip address.")
            addr = urlparse(req.baseurl).hostname
        click.echo(f"""
iscsiadm -m discovery -t st -p {addr}
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
@click.option("--force/--no-force", default=False, show_default=True, help="force delete export")
@click.option("--targetname", required=True, help="target name")
def export_delete(req: VERequest, targetname, force):
    """delete export"""
    param = {"force": "1"} if force else {}
    res = req.delete(f"/export/{targetname}", params=param)
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


def iscsiadm(**kwargs):
    arg = ["iscsiadm"]
    for k, v in kwargs.items():
        if len(k) == 1:
            arg.append(f"-{k}")
        else:
            arg.append(f"--{k}")
        if v is not None:
            arg.append(v)
    return runcmd(arg, root=True)


def find_device(name, wait: int = 0):
    import glob
    import time

    for _ in range(wait + 1):
        for model in glob.glob("/sys/block/sd*/device/model"):
            p = Path(model)
            if p.read_text().strip() == name and (p.parent / "vendor").read_text().strip() == "VOLEXP":
                devname = p.parent.parent.name
                return f"/dev/{devname}"
        else:
            _log.info("wait and retry")
            time.sleep(2)
    return None


@cli.command()
@verbose_option
@client_option
@click.option("--name", required=True, help="volume name")
@click.option("--format/--no-format", default=False, show_default=True)
@click.option("--mount")
def attach_volume(req: VERequest, name, format, mount):
    """attach volume"""
    import ifaddr

    if format:
        res = req.post(f"/volume/{name}/mkfs", json=dict(filesystem="ext4"))
        res.raise_for_status()

    addrs = []
    for ad in ifaddr.get_adapters():
        for ip in ad.ips:
            if isinstance(ip.ip, tuple):
                if ip.ip[2] != 0:
                    # scope id (is link local address)
                    continue
                addr = ip.ip[0]
            else:
                addr = ip.ip
            if addr:
                addrs.append(addr)
    res = req.post("/export", json={"volname": name, "acl": list(addrs)})
    res.raise_for_status()
    data = res.json()
    addrs: list[str] = data["addresses"]
    if addrs:
        tgtaddr = addrs[0]
    else:
        _log.warning("volexp returns no ip address.")
        tgtaddr = urlparse(req.baseurl).hostname
        assert tgtaddr is not None
    targetname: str = data["targetname"]
    iscsiadm(m="discovery", t="st", p=tgtaddr)
    iscsiadm(m="node", T=targetname, o="update", n="node.session.auth.authmethod", v="CHAP")
    iscsiadm(m="node", T=targetname, o="update", n="node.session.auth.username", v=data["user"])
    iscsiadm(m="node", T=targetname, o="update", n="node.session.auth.password", v=data["passwd"])
    iscsiadm(m="node", T=targetname, l=None)
    if mount:
        devname = find_device(name, 10)
        if devname is not None:
            runcmd(["mount", devname, mount], root=True)
        else:
            raise Exception(f"volume not found: {name=}")
    return


@cli.command()
@verbose_option
@client_option
@click.option("--name", help="volume name")
def detach_volume(req: VERequest, name):
    """detach volume"""

    devname = find_device(name)
    if devname is None:
        raise FileNotFoundError(f"volume not attached: {name=}")

    # find target
    res = req.get("/export")
    res.raise_for_status()
    for tgt in res.json():
        if tgt["volumes"] == [name]:
            targetname = tgt["targetname"]
            break
    else:
        raise FileNotFoundError(f"target not found: {name=}")

    # umount if mounted
    for line in Path("/proc/mounts").read_text().splitlines():
        words = line.split()
        if words[0] == devname:
            _log.info("device %s mounted %s", words[0], words[1])
            runcmd(["umount", words[0]], root=True)
            break

    res = iscsiadm(m="node", T=targetname, u=None)
    portal = None
    for line in res.stdout.splitlines():
        if line.endswith("successful."):
            portal = line.split("[", 1)[-1].split("]", 1)[0].rsplit(maxsplit=1)[-1]
            break
    if portal:
        iscsiadm(m="discoverydb", t="st", p=portal, o="delete")

    final_res = req.delete(f"/export/{targetname}", params={"force": "1"})
    return final_res.json()


if __name__ == "__main__":
    cli()
