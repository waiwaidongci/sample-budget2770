import csv,io
from fastapi import HTTPException
from sqlalchemy import select
from src.models.audience import (AudienceSelection,ValidationBatch,ValidationReport,AudienceUnblind,BudgetDecision)
from src.config.domain import DOMAIN
from src.services import analysis,audiences
from src.services.domain_validation import clean_reports,text
from src.services.audits import log
from src.utils.serializers import record,now

VERDICT_TEXT={'can_expand':'区间下限为正，可以追加投放',
              'do_not_expand':'区间下限不为正，暂不追加投放'}


def select(db,id,user):
    """Lock the largest search-split click-rate difference as the audience."""
    audiences.require(db,id)
    audiences.lock_study(db,id)
    if not audiences.lock_of(db,id): raise HTTPException(409,'开投前须先锁定每人的归属与原分派')
    if audiences.unblind_of(db,id): raise HTTPException(409,'已揭盲；复核集只验证锁定人群，不能再改选')
    rows=audiences.members(db,id)
    try:
        table=analysis.search_table(audiences.member_dicts(rows))
        best=analysis.select_label(table)
    except ValueError as e: raise HTTPException(422,str(e))
    fingerprint=audiences.search_fingerprint(rows)
    current=audiences.active_selection(db,id)
    if current and current.search_fingerprint==fingerprint:
        raise HTTPException(409,'搜寻数据未变，已锁定「'+current.label+'」；如已更正搜寻点击，请再次更正后重选')
    if current:
        current.status='superseded';current.superseded_at=now()
    obj=AudienceSelection(study_id=id,label=best['label'],difference=best['difference'],
                          detail={'table':table,'chosen':best['label']},
                          search_fingerprint=fingerprint,status='active',
                          created_by=user.email,created_at=now())
    db.add(obj)
    log(db,user,'audience.select',f'{id}: {best["label"]} diff={best["difference"]:.4f}')
    db.commit()
    return {**record(obj),'is_current':True,'table':table}


def report(db,id,data,user):
    """Record validation click reports for one batch.

    A batch is the unit of completeness: once sealed by an unblind it accepts no
    further reports, so a late supplement can never sneak into the scored set.
    """
    audiences.require(db,id)
    audiences.lock_study(db,id)
    if not audiences.lock_of(db,id): raise HTTPException(409,'开投前须先锁定归属')
    batch_key=text(data.batch_key,'复核批次编号',60)
    if not batch_key: raise HTTPException(422,'复核批次编号不得为空')
    batch=audiences.batch_of(db,id,batch_key,lock=True)
    if batch and batch.status=='sealed':
        raise HTTPException(409,'该批已揭盲封存；补报请另开新批，不得改写已封存同批')
    try: reports=clean_reports([x.model_dump() for x in data.reports])
    except ValueError as e: raise HTTPException(422,str(e))
    validation={m.source_key:m for m in audiences.members(db,id) if m.split=='validation'}
    for r in reports:
        if r['source_key'] not in validation: raise HTTPException(422,'复核集中没有该成员：'+r['source_key'])
    if not batch:
        batch=ValidationBatch(study_id=id,batch_key=batch_key,note=data.note,status='open',
                              created_by=user.email,created_at=now(),updated_at=now(),
                              report_count=0,missing_count=0)
        db.add(batch);db.flush()
    elif data.note: batch.note=data.note
    existing={r.source_key:r for r in audiences.batch_reports(db,batch.id)}
    for r in reports:
        if r['source_key'] in existing: existing[r['source_key']].click=r['click']
        else: db.add(ValidationReport(batch_id=batch.id,source_key=r['source_key'],click=r['click']))
    db.flush()
    stored=audiences.batch_reports(db,batch.id)
    batch.report_count=len(stored)
    # Missing = blank reports plus locked-audience members this batch never reported.
    sel=audiences.active_selection(db,id)
    labelled=[m for m in validation.values() if sel and sel.label in m.labels]
    reported={r.source_key for r in stored}
    batch.missing_count=sum(1 for r in stored if r.click is None)+sum(1 for m in labelled if m.source_key not in reported) if sel else sum(1 for r in stored if r.click is None)
    batch.updated_at=now()
    log(db,user,'validation.report',f'{id}/{batch_key}: {len(reports)} rows')
    db.commit()
    return {'batch':record(batch),'reports':[record(r) for r in stored]}


def unblind(db,id,data,user):
    """Seal one batch and evaluate the locked audience using original arms."""
    audiences.require(db,id)
    audiences.lock_study(db,id)
    if not audiences.lock_of(db,id): raise HTTPException(409,'开投前须先锁定归属')
    if audiences.unblind_of(db,id): raise HTTPException(409,'已揭盲；重试不覆盖原结论，复核集只验证锁定人群')
    sel=audiences.active_selection(db,id)
    if not sel: raise HTTPException(409,'尚未用搜寻集锁定人群')
    if not audiences.selection_state(db,id,sel):
        raise HTTPException(409,'搜寻数据已更正，请先按新数据重新选群再揭盲')
    batch_key=text(data.batch_key,'复核批次编号',60)
    batch=audiences.batch_of(db,id,batch_key,lock=True)
    if not batch: raise HTTPException(404,'复核批次不存在：'+batch_key)
    if batch.status=='sealed': raise HTTPException(409,'该批已揭盲封存；重试不覆盖原结论')
    stored=audiences.batch_reports(db,batch.id)
    if not stored: raise HTTPException(422,'该批尚无复核报告，无法揭盲')
    members=audiences.member_dicts(audiences.members(db,id))
    try:
        outcome=analysis.validation_outcome(members,[{'source_key':r.source_key,'click':r.click} for r in stored],sel.label)
        result=analysis.evaluate(sel.label,sel.difference,outcome,float(DOMAIN['defaults']['confidence']))
    except ValueError as e: raise HTTPException(422,str(e))
    batch.status='sealed';batch.updated_at=now()
    obj=AudienceUnblind(study_id=id,selection_id=sel.id,batch_id=batch.id,batch_key=batch.batch_key,
                        label=sel.label,difference=result['difference'],ci_low=result['ci_low'],
                        ci_high=result['ci_high'],verdict=result['verdict'],result=result,
                        created_by=user.email,created_at=now())
    db.add(obj)
    log(db,user,'audience.unblind',f'{id}: {sel.label} diff={result["difference"]:.4f} low={result["ci_low"]:.4f}')
    db.commit()
    return {**record(obj),'result':result}


def decide(db,id,data,user):
    """Archive an immutable budget decision after the interval is read out."""
    audiences.require(db,id)
    audiences.lock_study(db,id)
    uni=audiences.unblind_of(db,id)
    if not uni: raise HTTPException(409,'尚未揭盲，无可复核的区间结论')
    if audiences.decision_of(db,uni.id): raise HTTPException(409,'已复核，记录不可覆盖')
    note=(data.note or '').strip()
    if len(note)<5: raise HTTPException(422,'复核意见至少5个字符')
    obj=BudgetDecision(unblind_id=uni.id,note=note,author=user.email,created_at=now())
    db.add(obj);log(db,user,'review.decide',f'{id}: {note}')
    db.commit()
    return record(obj)


def export(db,id,user):
    """CSV of the sealed verdict; viewers only see released decisions."""
    audiences.require(db,id)
    uni=audiences.unblind_of(db,id)
    if not uni: raise HTTPException(409,'尚未揭盲，无可导出的结论')
    decision=audiences.decision_of(db,uni.id)
    if user.role=='viewer' and not decision: raise HTTPException(403,'观察员只能导出已复核结论')
    result=uni.result
    stream=io.StringIO();w=csv.writer(stream)
    w.writerow(['投放计划','锁定标签','对照点击','对照人数','处理点击','处理人数',
                '对照点击率','处理点击率','差值','95%区间下限','95%区间上限','区间结论',
                '缺报人数','复核批次','复核意见'])
    w.writerow([id,uni.label,result['control_click'],result['control_n'],
                result['treatment_click'],result['treatment_n'],
                f"{result['control_rate']:.6f}",f"{result['treatment_rate']:.6f}",
                f"{result['difference']:.6f}",f"{result['ci_low']:.6f}",f"{result['ci_high']:.6f}",
                VERDICT_TEXT[uni.verdict],len(result['missing']),uni.batch_key,
                decision.note if decision else ''])
    log(db,user,'decision.export',str(id));db.commit()
    return '\ufeff'+stream.getvalue()
