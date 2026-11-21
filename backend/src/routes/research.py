from fastapi import APIRouter,Depends
from fastapi.responses import Response
from sqlalchemy import select
from src.config.database import get_db
from src.controllers import research
from src.middlewares.auth import current_user,writer,admin
from src.schemas.study import StudyInput
from src.schemas.audience import (MemberRow,MemberBulkInput,SearchCorrectionInput,
                                  ValidationBatchInput,UnblindInput,DecisionInput)
from src.config.domain import DOMAIN
from src.services import audiences,decisions
from src.models.audit import Audit
from src.utils.serializers import record

router=APIRouter()


@router.get('/domain')
def domain(user=Depends(current_user)): return DOMAIN


@router.get('/overview')
def overview(db=Depends(get_db),user=Depends(current_user)):
    return {'studies':audiences.list_studies(db)}


@router.get('/studies')
def list_studies(db=Depends(get_db),user=Depends(current_user)): return audiences.list_studies(db)


@router.post('/studies')
def create_study(data:StudyInput,db=Depends(get_db),user=Depends(writer)):
    return research.create_study(db,data,user)


@router.get('/studies/{id}/cohort')
def cohort(id:int,db=Depends(get_db),user=Depends(current_user)):
    return audiences.cohort(db,id)


@router.post('/studies/{id}/members')
def add_members(id:int,data:MemberBulkInput,db=Depends(get_db),user=Depends(writer)):
    return audiences.save_members(db,id,[x.model_dump() for x in data.rows],user)


@router.put('/studies/{id}/members/{row_id}')
def update_member(id:int,row_id:int,data:MemberRow,db=Depends(get_db),user=Depends(writer)):
    return research.update_member(db,id,row_id,data.model_dump(),user)


@router.delete('/studies/{id}/members/{row_id}')
def delete_member(id:int,row_id:int,db=Depends(get_db),user=Depends(writer)):
    return audiences.delete_member(db,id,row_id,user)


@router.post('/studies/{id}/lock')
def lock(id:int,db=Depends(get_db),user=Depends(writer)):
    return audiences.lock(db,id,user)


@router.post('/studies/{id}/search-clicks')
def correct_search(id:int,data:SearchCorrectionInput,db=Depends(get_db),user=Depends(writer)):
    return audiences.correct_search(db,id,[x.model_dump() for x in data.corrections],user)


@router.post('/studies/{id}/selection')
def select_audience(id:int,db=Depends(get_db),user=Depends(writer)):
    return decisions.select(db,id,user)


@router.post('/studies/{id}/validation-batches')
def report(id:int,data:ValidationBatchInput,db=Depends(get_db),user=Depends(writer)):
    return decisions.report(db,id,data,user)


@router.post('/studies/{id}/unblind')
def unblind(id:int,data:UnblindInput,db=Depends(get_db),user=Depends(admin)):
    return decisions.unblind(db,id,data,user)


@router.post('/studies/{id}/decision')
def decide(id:int,data:DecisionInput,db=Depends(get_db),user=Depends(admin)):
    return decisions.decide(db,id,data,user)


@router.get('/studies/{id}/export')
def export(id:int,db=Depends(get_db),user=Depends(current_user)):
    content=decisions.export(db,id,user)
    return Response(content=content.encode('utf-8'),media_type='text/csv',
                    headers={'Content-Disposition':f'attachment; filename="audience-lift-{id}.csv"'})


@router.get('/audits')
def audits(db=Depends(get_db),user=Depends(current_user)):
    return [record(x) for x in db.scalars(select(Audit).order_by(Audit.id.desc()).limit(100))]
