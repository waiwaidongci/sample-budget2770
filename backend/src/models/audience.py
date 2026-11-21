from sqlalchemy import Column,Integer,String,Text,Float,JSON,ForeignKey,UniqueConstraint
from src.config.database import Base


class AudienceMember(Base):
    __tablename__='audience_members'
    __table_args__=(UniqueConstraint('study_id','source_key'),)
    id=Column(Integer,primary_key=True)
    study_id=Column(Integer,ForeignKey('studies.id'),nullable=False)
    source_key=Column(String(100),nullable=False)
    labels=Column(JSON,nullable=False)
    split=Column(String(20),nullable=False)
    arm=Column(String(20),nullable=False)
    search_click=Column(Integer,nullable=True)


class AudienceLock(Base):
    __tablename__='audience_locks'
    id=Column(Integer,primary_key=True)
    study_id=Column(Integer,ForeignKey('studies.id'),unique=True,nullable=False)
    checksum=Column(String(64),nullable=False)
    member_count=Column(Integer,nullable=False)
    search_count=Column(Integer,nullable=False)
    validation_count=Column(Integer,nullable=False)
    locked_by=Column(String(120),nullable=False)
    created_at=Column(String(40),nullable=False)


class AudienceSelection(Base):
    __tablename__='audience_selections'
    id=Column(Integer,primary_key=True)
    study_id=Column(Integer,ForeignKey('studies.id'),nullable=False)
    label=Column(String(40),nullable=False)
    difference=Column(Float,nullable=False)
    detail=Column(JSON,nullable=False)
    search_fingerprint=Column(String(64),nullable=False)
    status=Column(String(20),default='active')
    created_by=Column(String(120),nullable=False)
    created_at=Column(String(40),nullable=False)
    superseded_at=Column(String(40),nullable=True)


class ValidationBatch(Base):
    __tablename__='validation_batches'
    __table_args__=(UniqueConstraint('study_id','batch_key'),)
    id=Column(Integer,primary_key=True)
    study_id=Column(Integer,ForeignKey('studies.id'),nullable=False)
    batch_key=Column(String(60),nullable=False)
    note=Column(Text,default='')
    status=Column(String(20),default='open')
    report_count=Column(Integer,default=0)
    missing_count=Column(Integer,default=0)
    created_by=Column(String(120),nullable=False)
    created_at=Column(String(40),nullable=False)
    updated_at=Column(String(40),nullable=False)


class ValidationReport(Base):
    __tablename__='validation_reports'
    __table_args__=(UniqueConstraint('batch_id','source_key'),)
    id=Column(Integer,primary_key=True)
    batch_id=Column(Integer,ForeignKey('validation_batches.id'),nullable=False)
    source_key=Column(String(100),nullable=False)
    click=Column(Integer,nullable=True)


class AudienceUnblind(Base):
    __tablename__='audience_unblinds'
    id=Column(Integer,primary_key=True)
    study_id=Column(Integer,ForeignKey('studies.id'),unique=True,nullable=False)
    selection_id=Column(Integer,ForeignKey('audience_selections.id'),nullable=False)
    batch_id=Column(Integer,ForeignKey('validation_batches.id'),nullable=False)
    batch_key=Column(String(60),nullable=False)
    label=Column(String(40),nullable=False)
    difference=Column(Float,nullable=False)
    ci_low=Column(Float,nullable=False)
    ci_high=Column(Float,nullable=False)
    verdict=Column(String(40),nullable=False)
    result=Column(JSON,nullable=False)
    created_by=Column(String(120),nullable=False)
    created_at=Column(String(40),nullable=False)


class BudgetDecision(Base):
    __tablename__='budget_decisions'
    id=Column(Integer,primary_key=True)
    unblind_id=Column(Integer,ForeignKey('audience_unblinds.id'),unique=True,nullable=False)
    note=Column(Text,nullable=False)
    author=Column(String(120),nullable=False)
    created_at=Column(String(40),nullable=False)


Review=BudgetDecision
