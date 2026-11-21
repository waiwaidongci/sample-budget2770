import os,tempfile
import pytest

FD,DB_PATH=tempfile.mkstemp(suffix='.db')
os.close(FD)
os.environ.setdefault('DATABASE_URL','sqlite:///'+DB_PATH)
os.environ.setdefault('REDIS_URL','')
os.environ.setdefault('JWT_SECRET','test-secret')

from fastapi.testclient import TestClient  # noqa: E402
from src.main import app  # noqa: E402
from src.config.database import Base,engine,Session  # noqa: E402
from src.models.user import User  # noqa: E402
from src.utils.security import hash_password  # noqa: E402


@pytest.fixture(scope='session',autouse=True)
def prepare():
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine)
    with Session() as db:
        for role in ('admin','analyst','viewer'):
            db.add(User(email=role+'@demo.local',role=role,password_hash=hash_password('pw')))
        db.commit()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def token(client,role):
    r=client.post('/auth/login',json={'email':role+'@demo.local','password':'pw'})
    assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['token']}


@pytest.fixture()
def admin(client): return token(client,'admin')


@pytest.fixture()
def analyst(client): return token(client,'analyst')


def make_study(client,headers,name='T'):
    r=client.post('/studies',headers=headers,json={'name':name,'source_filename':'f.csv','description':''})
    assert r.status_code==200,r.text
    return r.json()['id']


SEARCH_CONTROL=[('s-c1',['A'],0),('s-c2',['A'],0),('s-c3',['A','B'],1),('s-c4',['B'],0),('s-c5',['B'],1),('s-c6',['C'],1)]
SEARCH_TREAT=[('s-t1',['A'],1),('s-t2',['A'],1),('s-t3',['A','B'],1),('s-t4',['B'],0),('s-t5',['B'],0),('s-t6',['C'],0)]
VALIDATION=[('v-c1',['A'],'control'),('v-c2',['A'],'control'),('v-c3',['A','B'],'control'),('v-c4',['B'],'control'),
            ('v-t1',['A'],'treatment'),('v-t2',['A'],'treatment'),('v-t3',['A','B'],'treatment'),('v-t4',['B'],'treatment')]


def seed_members(client,headers,sid,validation=VALIDATION):
    rows=[{'source_key':k,'labels':l,'split':'search','arm':'control','search_click':c} for k,l,c in SEARCH_CONTROL]
    rows+=[{'source_key':k,'labels':l,'split':'search','arm':'treatment','search_click':c} for k,l,c in SEARCH_TREAT]
    rows+=[{'source_key':k,'labels':l,'split':'validation','arm':a} for k,l,a in validation]
    r=client.post(f'/studies/{sid}/members',headers=headers,json={'rows':rows})
    assert r.status_code==200,r.text
