from src.services import audiences
# Controllers keep endpoint contracts separate from persistence and calculation.
def overview(db): return {'studies':audiences.list_studies(db)}
def create_study(db,data,user): return audiences.create(db,data,user)
def update_member(db,id,row_id,data,user): return audiences.update_member(db,id,row_id,data or {},user)
