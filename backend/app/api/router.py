from fastapi import APIRouter

from app.api.routes import (
    admin,
    ai,
    ai_account,
    usage_reports,
    auth,
    mfa,
    curriculum,
    community,
    dashboard,
    documents,
    exams,
    mvp_flow,
    question_bank,
    rag,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(mfa.router)
api_router.include_router(admin.router)
api_router.include_router(dashboard.router)
api_router.include_router(ai.router)
api_router.include_router(ai_account.router)
api_router.include_router(usage_reports.router)
api_router.include_router(curriculum.router)
api_router.include_router(community.router)
api_router.include_router(mvp_flow.router)
api_router.include_router(documents.router)
api_router.include_router(question_bank.router)
api_router.include_router(rag.router)
api_router.include_router(exams.router, prefix="/exams", tags=["exams"])
