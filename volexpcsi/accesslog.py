import grpc
import functools
import time
import urllib.parse
import inspect
from typing import Callable, Type
from google.protobuf.message import Message
from google.protobuf.json_format import MessageToJson
from logging import getLogger
from requests.exceptions import HTTPError, Timeout

_log = getLogger(__name__)


def accesslog(f: Callable):
    def _m2j(msg: Message) -> str:
        return MessageToJson(msg, preserving_proto_field_name=True, indent=None, ensure_ascii=False)

    @functools.wraps(f)
    def _(self, request: Message, context: grpc.ServicerContext):
        client = urllib.parse.unquote(context.peer())
        funcname = f.__qualname__
        _log.info("start %s -> %s: %s", client, funcname, _m2j(request))
        start = time.time()
        try:
            res = f(self, request, context)
            finish = time.time()
            _log.info("finish(OK) %s <- %s(%.3f sec): %s", client, funcname, finish - start, _m2j(res))
            return res
        except PermissionError as e:
            finish = time.time()
            _log.error("finish(permission) %s <- %s(%.3f sec): %s", client, funcname, finish - start, e, exc_info=e)
            context.abort(code=grpc.StatusCode.PERMISSION_DENIED, details=f"{type(e).__qualname__}: {e}")
        except ValueError as e:
            finish = time.time()
            _log.error("finish(value) %s <- %s(%.3f sec): %s", client, funcname, finish - start, e, exc_info=e)
            context.abort(code=grpc.StatusCode.INVALID_ARGUMENT, details=f"{type(e).__qualname__}: {e}")
        except NotImplementedError as e:
            finish = time.time()
            _log.error(
                "finish(not implemented) %s <- %s(%.3f sec): %s", client, funcname, finish - start, e, exc_info=e
            )
            context.abort(code=grpc.StatusCode.UNIMPLEMENTED, details=f"{type(e).__qualname__}: {e}")
        except FileExistsError as e:
            finish = time.time()
            _log.error("finish(exists) %s <- %s(%.3f sec): %s", client, funcname, finish - start, e, exc_info=e)
            context.abort(code=grpc.StatusCode.ALREADY_EXISTS, details=f"{type(e).__qualname__}: {e}")
        except FileNotFoundError as e:
            finish = time.time()
            _log.error("finish(not found) %s <- %s(%.3f sec): %s", client, funcname, finish - start, e, exc_info=e)
            context.abort(code=grpc.StatusCode.NOT_FOUND, details=f"{type(e).__qualname__}: {e}")
        except (Timeout, TimeoutError) as e:
            finish = time.time()
            _log.error("finish(timeout) %s <- %s(%.3f sec): %s", client, funcname, finish - start, e, exc_info=e)
            context.abort(code=grpc.StatusCode.DEADLINE_EXCEEDED, details=f"{type(e).__qualname__}: {e}")
        except AssertionError as e:
            finish = time.time()
            _log.error("finish(abort) %s <- %s(%.3f sec): %s", client, funcname, finish - start, e, exc_info=e)
            context.abort(code=grpc.StatusCode.ABORTED, details=f"{type(e).__qualname__}: {e}")
        except HTTPError as e:
            finish = time.time()
            _log.error(
                "finish(http %s) %s <- %s(%.3f sec): %s",
                e.response.status_code,
                client,
                funcname,
                finish - start,
                e,
                exc_info=e,
            )
            codemap: dict[int, grpc.StatusCode] = {
                400: grpc.StatusCode.INVALID_ARGUMENT,
                401: grpc.StatusCode.UNAUTHENTICATED,
                403: grpc.StatusCode.PERMISSION_DENIED,
                404: grpc.StatusCode.NOT_FOUND,
                408: grpc.StatusCode.DEADLINE_EXCEEDED,
                409: grpc.StatusCode.ALREADY_EXISTS,
                429: grpc.StatusCode.RESOURCE_EXHAUSTED,
                499: grpc.StatusCode.CANCELLED,
                500: grpc.StatusCode.INTERNAL,
                501: grpc.StatusCode.UNIMPLEMENTED,
                503: grpc.StatusCode.UNAVAILABLE,
                504: grpc.StatusCode.DEADLINE_EXCEEDED,
            }
            context.abort(
                code=codemap.get(e.response.status_code, grpc.StatusCode.UNKNOWN),
                details=f"{type(e).__qualname__}: {e}",
            )
        except Exception as e:
            finish = time.time()
            _log.error("finish(other error) %s <- %s(%.3f sec): %s", client, funcname, finish - start, e, exc_info=e)
            context.abort(code=grpc.StatusCode.INTERNAL, details=f"{type(e).__qualname__}: {e}")

    return _


def servicer_accesslog(cls: Type):
    names = {n for n, fn in inspect.getmembers(cls.mro()[1]) if not n.startswith("__") and callable(fn)}
    _log.info("decorate names: %s", names)
    for name, fn in inspect.getmembers(cls):
        if name in names:
            _log.debug("update method: %s", name)
            setattr(cls, name, accesslog(fn))
    return cls
