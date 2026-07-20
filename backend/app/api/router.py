from fastapi import APIRouter
from app.api.endpoints import diagnosis, auth, admin, audio, pilot, consent

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(diagnosis.router, prefix="/diagnosis", tags=["diagnosis"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(pilot.router, prefix="/admin/pilot", tags=["pilot"])
api_router.include_router(consent.router, prefix="/admin/consents", tags=["consent"])
api_router.include_router(audio.router, prefix="/audio", tags=["audio"])

# TODO: 추후 추가
# api_router.include_router(prescription.router, prefix="/prescription", tags=["prescription"])
# api_router.include_router(report.router, prefix="/report", tags=["report"])
