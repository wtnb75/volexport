import click
import json
import yaml
import pprint
import functools
from decimal import Decimal
from typing import Optional
from logging import getLogger

_log = getLogger(__name__)


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
    """set log level:

    - --verbose -> DEBUG
    - --quiet -> WARNING
    - (no option) -> INFO
    """

    @functools.wraps(func)
    def wrap(verbose, *args, **kwargs):
        set_verbose(verbose)
        return func(*args, **kwargs)

    return click.option("--verbose/--quiet", default=None, help="log level")(wrap)


def output_format(func):
    """set output format:

    - --format json   -> JSON
    - --format pjson  -> indented JSON
    - --format yaml   -> YAML
    - --format pprint -> python pprint.pprint()
    """

    @click.option("--format", type=click.Choice(["json", "pjson", "yaml", "pprint"]), default="json", show_default=True)
    @functools.wraps(func)
    def wrap(format, *args, **kwargs):
        res = func(*args, **kwargs)
        if format == "json":
            click.echo(json.dumps(res, ensure_ascii=False))
        elif format == "pjson":
            click.echo(json.dumps(res, indent=2, ensure_ascii=False))
        elif format == "yaml":
            click.echo(yaml.dump(res, allow_unicode=True, encoding="utf-8"))
        elif format == "pprint":
            click.echo(pprint.pformat(res))
        else:
            raise NotImplementedError(f"unknown format: {format}")

    return wrap


class SizeType(click.ParamType):
    """size parameter

    - xxxS (sector) -> x512
    - xxxK (kilo)   -> x1024
    - xxxM (mega)   -> x1024x1024
    - xxxG (giga)   -> x1024x1024x1024
    - xxxT (tera)   -> x1024x1024x1024x1024
    - xxxP (peta)   -> x1024x1024x1024x1024x1024
    - xxxE (exa)    -> x1024x1024x1024x1024x1024x1024
    """

    name = "size"

    def convert(self, value: str, param, ctx):
        factor = Decimal(1)
        if value.endswith("S"):
            factor = Decimal(512)  # sector
            value = value.removesuffix("S")
        if value.endswith("K"):
            factor = factor * Decimal(1024)
            value = value.removesuffix("K")
        elif value.endswith("M"):
            factor = factor * Decimal(1024 * 1024)
            value = value.removesuffix("M")
        elif value.endswith("G"):
            factor = factor * Decimal(1024 * 1024 * 1024)
            value = value.removesuffix("G")
        elif value.endswith("T"):
            factor = factor * Decimal(1024 * 1024 * 1024 * 1204)
            value = value.removesuffix("T")
        elif value.endswith("P"):
            factor = factor * Decimal(1024 * 1024 * 1024 * 1204 * 1024)
            value = value.removesuffix("P")
        elif value.endswith("E"):
            factor = factor * Decimal(1024 * 1024 * 1024 * 1204 * 1024 * 1024)
            value = value.removesuffix("E")
        return int(Decimal(value) * factor)
