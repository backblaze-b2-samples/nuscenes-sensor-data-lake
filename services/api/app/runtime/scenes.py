"""Scene routes (thin) — the primary-entity surface for the AV data lake.

Handlers are sync `def` on purpose: the whole chain is blocking (boto3 + the
devkit), so Starlette runs them in its threadpool instead of stalling the event
loop. All business logic lives in service/scenes.py.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.service.scenes import (
    SceneError,
    create_scene,
    delete_scene,
    get_lake_stats,
    get_scene,
    list_scenes,
    serve_frame,
    update_scene,
)
from app.types.scenes import (
    FrameManifest,
    LakeStats,
    SceneCreateRequest,
    SceneDeleteResponse,
    SceneDetail,
    SceneSummary,
    SceneUpdateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# SECURITY: these routes are intentionally UNAUTHENTICATED and single-tenant
# (see docs/SECURITY.md). Every scene lives under its own B2 prefix; deletes are
# scoped to that prefix only. A multi-tenant clone must add auth AND scope scene
# listing/reads to the caller.


def _handle(exc: SceneError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=exc.detail)


@router.get("/scenes", response_model=list[SceneSummary])
def list_scenes_endpoint():
    return list_scenes()


@router.post("/scenes", response_model=SceneSummary)
def create_scene_endpoint(req: SceneCreateRequest):
    try:
        return create_scene(req)
    except SceneError as e:
        raise _handle(e) from None


# Declared before /scenes/{token} so "stats" is never captured as a token.
@router.get("/scenes/stats", response_model=LakeStats)
def lake_stats_endpoint():
    return get_lake_stats()


@router.get("/scenes/{token}", response_model=SceneDetail)
def get_scene_endpoint(token: str):
    try:
        return get_scene(token)
    except SceneError as e:
        raise _handle(e) from None


@router.post("/scenes/{token}", response_model=SceneSummary)
def update_scene_endpoint(token: str, req: SceneUpdateRequest):
    try:
        return update_scene(token, req)
    except SceneError as e:
        raise _handle(e) from None


@router.delete("/scenes/{token}", response_model=SceneDeleteResponse)
def delete_scene_endpoint(token: str):
    try:
        removed = delete_scene(token)
    except SceneError as e:
        raise _handle(e) from None
    logger.info("Scene deleted: token=%s objects=%s", token, removed)
    return SceneDeleteResponse(deleted=True, token=token, objects_removed=removed)


@router.post("/scenes/{token}/frame", response_model=FrameManifest)
def serve_frame_endpoint(token: str, keyframe: int = 0):
    try:
        return serve_frame(token, keyframe_index=keyframe)
    except SceneError as e:
        raise _handle(e) from None
    except FileNotFoundError as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    except Exception as e:  # devkit build/resolve failure -> actionable 502
        logger.exception("Serve frame failed for token=%s", token)
        raise HTTPException(
            status_code=502, detail=f"Failed to index scene: {e}"
        ) from None
