"""Service endpoints: liveness probe and version / runtime-mode information."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from regista_core import __version__
from regista_core.config import RuntimeModes, Settings

router = APIRouter(tags=["system"])


class Health(BaseModel):
    """Liveness probe payload."""

    status: Literal["ok"] = "ok"


class VersionInfo(BaseModel):
    """What is running: service name, package version and runtime modes."""

    name: str
    version: str
    modes: RuntimeModes


def get_app_settings(request: Request) -> Settings:
    """Return the settings the running app was built with."""
    return request.app.state.settings


@router.get("/healthz")
async def healthz() -> Health:
    """Answer the liveness probe (Container Apps, CI, the web placeholder)."""
    return Health()


@router.get("/api/version")
async def version(settings: Annotated[Settings, Depends(get_app_settings)]) -> VersionInfo:
    """Report the package version and whether this process runs offline or on Azure."""
    return VersionInfo(name="regista-core", version=__version__, modes=settings.runtime_modes())
