"""The administrator's functions (§4.2.2). Every route needs an admin session."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import Store, admin_user
from app.api.schemas.admin import (
    AdminSummary,
    CheckQuestion,
    CheckQuestionCreate,
    CheckQuestionPage,
    CheckQuestionPatch,
    GlossaryCreate,
    GlossaryEntry,
    GlossaryPage,
    GlossaryPatch,
    PrimitiveAdmin,
    PrimitivePatch,
    RenderJobDetail,
    RenderJobPage,
    RenderJobStatus,
    StudentAdmin,
    StudentPage,
    StudentPatch,
)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(admin_user)])

PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.get("/summary", response_model=AdminSummary)
async def summary(store: Store) -> AdminSummary:
    return store.admin_summary()


@router.get("/primitives", response_model=list[PrimitiveAdmin])
async def primitives(store: Store) -> list[PrimitiveAdmin]:
    return store.list_primitives()


@router.patch("/primitives/{primitive_id}", response_model=PrimitiveAdmin)
async def patch_primitive(primitive_id: str, body: PrimitivePatch, store: Store) -> PrimitiveAdmin:
    return store.patch_primitive(primitive_id, body)


@router.get("/glossary", response_model=GlossaryPage)
async def glossary(
    store: Store,
    page: PageNo = 1,
    page_size: PageSize = 20,
    search: str | None = None,
    concept_id: int | None = None,
) -> GlossaryPage:
    return store.list_glossary(search, concept_id, page, page_size)


@router.post("/glossary", response_model=GlossaryEntry, status_code=201)
async def create_glossary(body: GlossaryCreate, store: Store) -> GlossaryEntry:
    return store.create_glossary(body)


@router.patch("/glossary/{term_id}", response_model=GlossaryEntry)
async def patch_glossary(term_id: int, body: GlossaryPatch, store: Store) -> GlossaryEntry:
    return store.patch_glossary(term_id, body)


@router.delete("/glossary/{term_id}", status_code=204)
async def delete_glossary(term_id: int, store: Store) -> None:
    store.delete_glossary(term_id)


@router.get("/check-questions", response_model=CheckQuestionPage)
async def check_questions(
    store: Store, page: PageNo = 1, page_size: PageSize = 20, concept_id: int | None = None
) -> CheckQuestionPage:
    return store.list_items(concept_id, page, page_size)


@router.post("/check-questions", response_model=CheckQuestion, status_code=201)
async def create_check_question(body: CheckQuestionCreate, store: Store) -> CheckQuestion:
    return store.create_item(body)


@router.patch("/check-questions/{item_id}", response_model=CheckQuestion)
async def patch_check_question(
    item_id: int, body: CheckQuestionPatch, store: Store
) -> CheckQuestion:
    return store.patch_item(item_id, body)


@router.delete("/check-questions/{item_id}", status_code=204)
async def delete_check_question(item_id: int, store: Store) -> None:
    store.delete_item(item_id)


@router.get("/render-jobs", response_model=RenderJobPage)
async def render_jobs(
    store: Store, page: PageNo = 1, page_size: PageSize = 20, status: RenderJobStatus | None = None
) -> RenderJobPage:
    return store.list_render_jobs(status, page, page_size)


@router.get("/render-jobs/{job_id}", response_model=RenderJobDetail)
async def render_job(job_id: int, store: Store) -> RenderJobDetail:
    return store.render_job(job_id)


@router.get("/students", response_model=StudentPage)
async def students(
    store: Store, page: PageNo = 1, page_size: PageSize = 20, search: str | None = None
) -> StudentPage:
    return store.list_students(search, page, page_size)


@router.get("/students/{student_id}", response_model=StudentAdmin)
async def student(student_id: int, store: Store) -> StudentAdmin:
    return store.student(student_id)


@router.patch("/students/{student_id}", response_model=StudentAdmin)
async def patch_student(student_id: int, body: StudentPatch, store: Store) -> StudentAdmin:
    return store.set_disabled(student_id, body.disabled)


@router.delete("/students/{student_id}", status_code=204)
async def delete_student(student_id: int, store: Store) -> None:
    store.delete_student(student_id)
