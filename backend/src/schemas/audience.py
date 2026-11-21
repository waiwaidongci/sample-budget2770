from typing import Optional
from pydantic import BaseModel,Field


class MemberRow(BaseModel):
    source_key:str=Field(min_length=1,max_length=100)
    labels:list[str]=Field(min_length=1,max_length=12)
    split:str
    arm:str
    search_click:Optional[int]=None


class MemberBulkInput(BaseModel):
    rows:list[MemberRow]=Field(min_length=1,max_length=5000)


class SearchCorrection(BaseModel):
    source_key:str=Field(min_length=1,max_length=100)
    click:int


class SearchCorrectionInput(BaseModel):
    corrections:list[SearchCorrection]=Field(min_length=1,max_length=5000)


class ValidationReport(BaseModel):
    source_key:str=Field(min_length=1,max_length=100)
    click:Optional[int]=None


class ValidationBatchInput(BaseModel):
    batch_key:str=Field(min_length=1,max_length=60)
    note:str=Field(default='',max_length=2000)
    reports:list[ValidationReport]=Field(min_length=1,max_length=5000)


class UnblindInput(BaseModel):
    batch_key:str=Field(min_length=1,max_length=60)


class DecisionInput(BaseModel):
    note:str=Field(min_length=5,max_length=2000)
