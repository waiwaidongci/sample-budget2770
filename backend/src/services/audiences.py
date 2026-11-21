from fastapi import HTTPException
from sqlalchemy import select,func
from src.models.study import Study
from src.models.audience import (AudienceMember,AudienceLock,AudienceSelection,
                                 ValidationBatch,ValidationReport,AudienceUnblind,BudgetDecision)
from src.services.domain_validation import clean_member,clean_corrections
from src.services.audits import log
from src.utils.serializers import record,now,checksum


def list_studies(db):
    data=[]
    for s in db.scalars(select(Study).order_by(Study.id)):
        x=record(s)
        x['member_count']=db.scalar(select(func.count()).select_from(AudienceMember).where(AudienceMember.study_id==s.id))
        lock=db.scalar(select(AudienceLock).where(AudienceLock.study_id==s.id))
        sel=active_selection(db,s.id)
        unblind=db.scalar(select(AudienceUnblind).where(AudienceUnblind.study_id==s.id))
        x['locked']=bool(lock)
        x['state']=('reviewed' if unblind and decision_of(db,unblind.id) else 'unblinded' if unblind else 'selected' if sel else 'locked' if lock else 'unlocked')
        x['locked_label']=sel.label if sel else None
        x['verdict']=unblind.verdict if unblind else None
        x['batch_key']=unblind.batch_key if unblind else None
        data.append(x)
    return data


def create(db,data,user):
    if db.scalar(select(Study).where(Study.name==data.name)): raise HTTPException(409,'投放计划名称已存在')
    s=Study(name=data.name,source_filename=data.source_filename,description=data.description,created_at=now())
    db.add(s);log(db,user,'study.create',data.name);db.commit();return record(s)


def require(db,id):
    s=db.get(Study,id)
    if not s: raise HTTPException(404,'投放计划不存在')
    return s


def lock_of(db,id):
    return db.scalar(select(AudienceLock).where(AudienceLock.study_id==id))


def unblind_of(db,id):
    return db.scalar(select(AudienceUnblind).where(AudienceUnblind.study_id==id))


def members(db,id):
    require(db,id)
    return list(db.scalars(select(AudienceMember).where(AudienceMember.study_id==id).order_by(AudienceMember.source_key)))


def member_dicts(rows):
    return [{'id':m.id,'source_key':m.source_key,'labels':list(m.labels),'split':m.split,'arm':m.arm,'search_click':m.search_click} for m in rows]


def active_selection(db,id):
    return db.scalar(select(AudienceSelection).where(AudienceSelection.study_id==id,AudienceSelection.status=='active').order_by(AudienceSelection.id.desc()))


def selection_history(db,id):
    return list(db.scalars(select(AudienceSelection).where(AudienceSelection.study_id==id).order_by(AudienceSelection.id)))


def batches(db,id):
    return list(db.scalars(select(ValidationBatch).where(ValidationBatch.study_id==id).order_by(ValidationBatch.id)))


def _for_update(stmt,db):
    """Row lock on PostgreSQL; SQLite's single writer already serializes."""
    return stmt.with_for_update() if db.get_bind().dialect.name!='sqlite' else stmt


def batch_of(db,id,key,lock=False):
    stmt=select(ValidationBatch).where(ValidationBatch.study_id==id,ValidationBatch.batch_key==key)
    return db.scalar(_for_update(stmt,db) if lock else stmt)


def lock_study(db,id):
    """Serialize write paths per campaign so report/unblind cannot interleave."""
    return db.scalar(_for_update(select(Study).where(Study.id==id),db))


def batch_reports(db,batch_id):
    return list(db.scalars(select(ValidationReport).where(ValidationReport.batch_id==batch_id).order_by(ValidationReport.source_key)))


def decision_of(db,unblind_id):
    return db.scalar(select(BudgetDecision).where(BudgetDecision.unblind_id==unblind_id))


def assignment_checksum(rows):
    payload=[{'source_key':m.source_key,'labels':sorted(m.labels),'split':m.split,'arm':m.arm} for m in sorted(rows,key=lambda m:m.source_key)]
    return checksum(payload)


def search_fingerprint(rows):
    payload=[{'source_key':m.source_key,'arm':m.arm,'click':m.search_click} for m in sorted(rows,key=lambda m:m.source_key) if m.split=='search']
    return checksum(payload)


def save_members(db,id,items,user):
    require(db,id)
    if lock_of(db,id): raise HTTPException(409,'归属已锁定，成员表不可再修改')
    if not items: raise HTTPException(422,'至少录入一名成员')
    existing={m.source_key:m for m in members(db,id)}
    clean=[]
    for item in items:
        try: clean.append(clean_member(item))
        except ValueError as e: raise HTTPException(422,str(e))
    keys=[m['source_key'] for m in clean]
    if len(set(keys))!=len(keys): raise HTTPException(422,'提交的成员编号重复')
    for m in clean:
        if m['source_key'] in existing: raise HTTPException(409,'成员编号已存在：'+m['source_key'])
    if len(existing)+len(clean)>5000: raise HTTPException(422,'单个投放计划最多5000名成员')
    for m in clean: db.add(AudienceMember(study_id=id,**m))
    log(db,user,'member.register',f'{id}: {len(clean)} rows');db.commit()
    return {'created':len(clean),'member_count':len(existing)+len(clean)}


def update_member(db,id,row_id,data,user):
    require(db,id)
    if lock_of(db,id): raise HTTPException(409,'归属已锁定，成员表不可再修改')
    row=db.get(AudienceMember,row_id)
    if not row or row.study_id!=id: raise HTTPException(404,'成员不存在')
    try: clean=clean_member(data)
    except ValueError as e: raise HTTPException(422,str(e))
    other=db.scalar(select(AudienceMember).where(AudienceMember.study_id==id,AudienceMember.source_key==clean['source_key'],AudienceMember.id!=row_id))
    if other: raise HTTPException(409,'成员编号已存在')
    for k,v in clean.items(): setattr(row,k,v)
    log(db,user,'member.update',f'{id}/{clean["source_key"]}');db.commit();return record(row)


def delete_member(db,id,row_id,user):
    require(db,id)
    if lock_of(db,id): raise HTTPException(409,'归属已锁定，成员表不可再修改')
    row=db.get(AudienceMember,row_id)
    if not row or row.study_id!=id: raise HTTPException(404,'成员不存在')
    key=row.source_key;db.delete(row);log(db,user,'member.delete',f'{id}/{key}');db.commit();return {'deleted':True}


def lock(db,id,user):
    require(db,id)
    lock_study(db,id)
    if lock_of(db,id): raise HTTPException(409,'归属已锁定；锁定不可覆盖')
    rows=members(db,id)
    if not rows: raise HTTPException(422,'至少录入一名成员后再锁定')
    search=[m for m in rows if m.split=='search'];validation=[m for m in rows if m.split=='validation']
    if not search: raise HTTPException(422,'搜寻集为空，无法锁定')
    if not validation: raise HTTPException(422,'复核集为空，无法锁定')
    for label,group in (('搜寻集',search),('复核集',validation)):
        for arm,arm_label in (('control','对照'),('treatment','处理')):
            if not any(m.arm==arm for m in group): raise HTTPException(422,f'{label}缺少{arm_label}成员，无法锁定')
    obj=AudienceLock(study_id=id,checksum=assignment_checksum(rows),member_count=len(rows),
                     search_count=len(search),validation_count=len(validation),
                     locked_by=user.email,created_at=now())
    db.add(obj);log(db,user,'audience.lock',f'{id}: {len(rows)} members');db.commit();return record(obj)


def correct_search(db,id,items,user):
    require(db,id)
    lock_study(db,id)
    if not lock_of(db,id): raise HTTPException(409,'开投前必须先锁定归属，才能更正搜寻点击')
    if unblind_of(db,id): raise HTTPException(409,'已揭盲；搜寻数据不可再更正，复核集只验证锁定人群')
    try: clean=clean_corrections(items)
    except ValueError as e: raise HTTPException(422,str(e))
    rows={m.source_key:m for m in members(db,id) if m.split=='search'}
    targets=[]
    for key,click in clean:
        m=rows.get(key)
        if not m: raise HTTPException(404,'搜寻集中没有该成员：'+key)
        targets.append((m,click))
    for m,click in targets: m.search_click=click
    log(db,user,'search.correct',f'{id}: '+', '.join(f'{m.source_key}={c}' for m,c in targets));db.commit()
    return {'corrected':len(targets)}


def selection_state(db,id,sel):
    """Mark whether the frozen selection still matches the current search data."""
    return search_fingerprint(members(db,id))==sel.search_fingerprint


def selection_payload(db,id,sel):
    payload=record(sel)
    payload['detail']=sel.detail
    payload['is_current']=selection_state(db,id,sel)
    return payload


def batch_payload(db,batch):
    reports=batch_reports(db,batch.id)
    return {**record(batch),'reports':[record(r) for r in reports]}


def unblind_payload(db,u):
    payload=record(u)
    decision=decision_of(db,u.id)
    payload['decision']=record(decision) if decision else None
    return payload


def cohort(db,id):
    require(db,id)
    rows=members(db,id)
    lock_row=lock_of(db,id)
    sel=active_selection(db,id)
    uni=unblind_of(db,id)
    return {'study':record(require(db,id)),
            'lock':record(lock_row) if lock_row else None,
            'assignment_checksum':assignment_checksum(rows) if rows else None,
            'members':member_dicts(rows),
            'selections':[selection_payload(db,id,s) for s in selection_history(db,id)],
            'active_selection':selection_payload(db,id,sel) if sel else None,
            'batches':[batch_payload(db,b) for b in batches(db,id)],
            'unblind':unblind_payload(db,uni) if uni else None}
