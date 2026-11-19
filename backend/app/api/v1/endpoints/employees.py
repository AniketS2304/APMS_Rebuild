from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import CurrentUser, SessionDep, require_permission
from app.api.v1.endpoints.auth import IdempotencyDep
from app.schemas.employee import EmployeeCreate, EmployeeOut, EmployeeUpdate
from app.schemas.iam import DeletedOut
from app.services.employee import (
    create_employee,
    delete_employee,
    get_employee,
    list_employees,
    update_employee,
)
from app.services.idempotency import replay_or_reserve, store_response

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("", response_model=list[EmployeeOut], summary="List employees")
async def list_all(
    session: SessionDep,
    current: Annotated[CurrentUser, Depends(require_permission("employee.employee.read"))],
    branch_id: Annotated[UUID | None, Query(description="Filter by branch ID")] = None,
    department_id: Annotated[UUID | None, Query(description="Filter by department ID")] = None,
    is_active: Annotated[bool | None, Query(description="Filter by active status")] = None,
) -> list[EmployeeOut]:
    return await list_employees(
        session=session,
        tenant_id=current.tenant_id,
        branch_id=branch_id,
        department_id=department_id,
        is_active=is_active,
    )


@router.get("/{employee_id}", response_model=EmployeeOut, summary="Get employee details")
async def get_one(
    employee_id: UUID,
    session: SessionDep,
    current: Annotated[CurrentUser, Depends(require_permission("employee.employee.read"))],
) -> EmployeeOut:
    return await get_employee(session, current.tenant_id, employee_id)


@router.post("", response_model=EmployeeOut, status_code=201, summary="Create an employee")
async def create(
    payload: EmployeeCreate,
    response: Response,
    session: SessionDep,
    current: Annotated[CurrentUser, Depends(require_permission("employee.employee.create"))],
    idempotency_key: IdempotencyDep,
) -> EmployeeOut:
    body_in = payload.model_dump(mode="json")
    replay = await replay_or_reserve(session, current.tenant_id, idempotency_key, "/api/v1/employees", body_in)
    if replay:
        response.status_code = int(replay["status_code"])
        return EmployeeOut.model_validate(replay["body"])

    created = await create_employee(session, current.tenant_id, payload)
    await store_response(
        session,
        current.tenant_id,
        idempotency_key,
        "/api/v1/employees",
        body_in,
        201,
        created.model_dump(mode="json"),
    )
    return created


@router.patch("/{employee_id}", response_model=EmployeeOut, summary="Update an employee")
async def update(
    employee_id: UUID,
    payload: EmployeeUpdate,
    session: SessionDep,
    current: Annotated[CurrentUser, Depends(require_permission("employee.employee.update"))],
) -> EmployeeOut:
    return await update_employee(session, current.tenant_id, employee_id, payload)


@router.delete("/{employee_id}", response_model=DeletedOut, summary="Delete an employee")
async def remove(
    employee_id: UUID,
    session: SessionDep,
    current: Annotated[CurrentUser, Depends(require_permission("employee.employee.delete"))],
) -> DeletedOut:
    await delete_employee(session, current.tenant_id, employee_id)
    return DeletedOut(id=employee_id)
