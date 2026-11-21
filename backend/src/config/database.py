import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

class Base(DeclarativeBase):
    pass

url=os.environ['DATABASE_URL']
engine=create_engine(url,pool_pre_ping=True,connect_args={'check_same_thread':False} if url.startswith('sqlite') else {})
Session=sessionmaker(bind=engine,expire_on_commit=False)

def get_db():
    with Session() as db:
        yield db
