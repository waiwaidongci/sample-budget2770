import json
import numpy as np
from sqlalchemy import select,func
from src.config.database import Base,engine,Session
from src.config.domain import DOMAIN
from src.models.user import User
from src.models.study import Study
from src.models.audience import AudienceMember
from src.models import audit
from src.utils.security import hash_password
from src.utils.serializers import now

LABELS=('冬季关注','高活跃','新访客','收藏夹')
BASE_CLICK=0.10
ARM_MAIN=0.02
# Per-plan interaction: incremental treatment lift by label. Deliberately large
# enough to keep the demo workbook legible; it is synthetic, not a forecast.
PLAN_INTERACTION=[
    {'冬季关注':0.02,'高活跃':0.30,'新访客':-0.05,'收藏夹':0.06},
    {'冬季关注':0.03,'高活跃':0.05,'新访客':-0.06,'收藏夹':0.13},
    {'冬季关注':-0.02,'高活跃':0.04,'新访客':-0.14,'收藏夹':0.03},
]
SEARCH_N=200
VALIDATION_N=200


def click_probability(labels,arm,k):
    p=BASE_CLICK+ARM_MAIN*(arm=='treatment')+0.01*(len(labels)-1)
    if arm=='treatment': p+=sum(PLAN_INTERACTION[k%len(PLAN_INTERACTION)][x] for x in labels)
    return float(np.clip(p,0.01,0.95))


def draw_labels(rng):
    return sorted(rng.choice(LABELS,size=int(rng.integers(1,4)),replace=False).tolist())


def seed():
    Base.metadata.create_all(engine)
    rng=np.random.default_rng(42)
    with Session() as db:
        for role in ('admin','analyst','viewer'):
            email=role+'@demo.local'
            if not db.scalar(select(User).where(User.email==email)):
                db.add(User(email=email,role=role,password_hash=hash_password('Research2026!')))
        for k,name in enumerate(DOMAIN['names']):
            study=db.scalar(select(Study).where(Study.name==name))
            if not study:
                study=Study(name=name,source_filename=DOMAIN['slug']+f'-202611-{k+1}.csv',
                            description='合成受众：重叠标签、开投前锁定的搜寻/复核归属与原分派；仅供流程演示',
                            created_at=now())
                db.add(study);db.flush()
            if db.scalar(select(func.count()).select_from(AudienceMember).where(AudienceMember.study_id==study.id)):
                continue
            members=[]
            for n in range(SEARCH_N+VALIDATION_N):
                labels=draw_labels(rng)
                split='search' if n<SEARCH_N else 'validation'
                arm='treatment' if n%2==0 else 'control'
                click=None
                if split=='search':
                    click=int(rng.random()<click_probability(labels,arm,k))
                members.append(AudienceMember(study_id=study.id,source_key=f'{k+1}-{n+1:04d}',
                                              labels=labels,split=split,arm=arm,search_click=click))
            db.add_all(members)
        db.commit()
        counts={model.__tablename__:db.scalar(select(func.count()).select_from(model)) for model in (User,Study,AudienceMember)}
        print(json.dumps(counts,ensure_ascii=False));return counts


if __name__=='__main__': seed()
