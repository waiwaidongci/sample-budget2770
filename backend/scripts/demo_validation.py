"""Optional demo helper: generate validation clicks for the first plan.

Writes a batch through the same persistence path the UI uses, so the
missing-report rule ("not zero") and the sealed-batch rule still apply.
"""
import numpy as np
from sqlalchemy import select
from src.config.database import Session
from src.config.domain import DOMAIN
from src.models.study import Study
from src.models.audience import AudienceMember
from src.models.user import User
from src.services import decisions
from src.schemas.audience import ValidationBatchInput
from scripts.seed_demo import click_probability


def validation_clicks(seed_value=7):
    rng=np.random.default_rng(seed_value)
    with Session() as db:
        study=db.scalar(select(Study).where(Study.name==DOMAIN['names'][0]))
        members=list(db.scalars(select(AudienceMember).where(AudienceMember.study_id==study.id,
                                                             AudienceMember.split=='validation')
                                .order_by(AudienceMember.source_key)))
        admin=db.scalar(select(User).where(User.email=='admin@demo.local'))
        k=DOMAIN['names'].index(study.name)
        # Six members are left out on purpose to exercise the missing-report path.
        reports=[{'source_key':m.source_key,'click':int(rng.random()<click_probability(m.labels,m.arm,k))}
                 for m in members[6:]]
        data=ValidationBatchInput(batch_key='DEMO-V1',note='演示复核批次：含6条缺报',reports=reports)
        return decisions.report(db,study.id,data,admin)


if __name__=='__main__':
    print(validation_clicks())
