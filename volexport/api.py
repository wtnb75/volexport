from logging import getLogger
from subprocess import SubprocessError
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from .api_export import router as export_router
from .api_volume import router as volume_router

_log = getLogger(__name__)
api = FastAPI()
api.include_router(export_router)
api.include_router(volume_router)


@api.exception_handler(FileNotFoundError)
def notfound(request: Request, exc: FileNotFoundError):
    return JSONResponse(status_code=404, content=dict(detail="\n".join(exc.args)))


@api.exception_handler(FileExistsError)
def inuse(request: Request, exc: FileExistsError):
    return JSONResponse(status_code=400, content=dict(detail="\n".join(exc.args)))


@api.exception_handler(NotImplementedError)
def notimplemented(request: Request, exc: NotImplementedError):
    return JSONResponse(status_code=501, content=dict(detail=str(exc)))


@api.exception_handler(SubprocessError)
def commanderror(request: Request, exc: SubprocessError):
    return JSONResponse(status_code=500, content=dict(detail=str(exc)))


@api.get("/health")
def health():
    return {"status": "OK"}
