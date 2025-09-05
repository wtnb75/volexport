from logging import getLogger
from subprocess import SubprocessError
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from .api_export import router as export_router
from .api_volume import router as volume_router
from .api_mgmt import router as mgmt_router
from .exceptions import InvalidArgument

_log = getLogger(__name__)
api = FastAPI()
api.include_router(export_router)
api.include_router(volume_router)
api.include_router(mgmt_router)


@api.exception_handler(FileNotFoundError)
def notfound(request: Request, exc: FileNotFoundError):
    """FileNotFoundError to 404 Not Found"""
    _log.info("not found: request=%s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=404, content=dict(detail="\n".join(exc.args)))


@api.exception_handler(FileExistsError)
def inuse(request: Request, exc: FileExistsError):
    """FileExistsError to 400 Bad Request"""
    _log.info("file exists: request=%s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=400, content=dict(detail="\n".join(exc.args)))


@api.exception_handler(NotImplementedError)
def notimplemented(request: Request, exc: NotImplementedError):
    """NotImplementedError to 501 Not Implemented"""
    _log.info("not implemented: request=%s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=501, content=dict(detail=str(exc)))


@api.exception_handler(SubprocessError)
def commanderror(request: Request, exc: SubprocessError):
    """SubprocessError to 500 Internal Server Error"""
    _log.info("command error: request=%s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content=dict(detail="internal error"))


@api.exception_handler(InvalidArgument)
def badrequest(request: Request, exc: InvalidArgument):
    """InvalidArgument to 400 Bad Request"""
    _log.info("invalid argument: request=%s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=400, content=dict(detail="\n".join(exc.args)))


@api.exception_handler(ValueError)
def valueerror(request: Request, exc: ValueError):
    """ValueError to 400 Bad Request"""
    _log.info("invalid argument: request=%s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=400, content=dict(detail="\n".join(exc.args)))


@api.exception_handler(TypeError)
def typeerror(request: Request, exc: TypeError):
    """TypeError to 500 Internal Server Error"""
    _log.info("internal error: request=%s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content=dict(detail="internal error"))


@api.exception_handler(AssertionError)
def asserterror(request: Request, exc: AssertionError):
    """AssertionError to 500 Internal Server Error"""
    _log.info("internal error: request=%s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content=dict(detail="internal error"))


@api.get("/health", description="Health check endpoint")
def health():
    return {"status": "OK"}
