import {request,post} from './client.js';

export const studies={
  list:()=>request('/studies'),
  create:x=>post('/studies',x),
  cohort:id=>request(`/studies/${id}/cohort`),
  addMembers:(id,rows)=>post(`/studies/${id}/members`,{rows}),
  updateMember:(id,row,x)=>request(`/studies/${id}/members/${row}`,{method:'PUT',body:JSON.stringify(x)}),
  removeMember:(id,row)=>request(`/studies/${id}/members/${row}`,{method:'DELETE'}),
  lock:id=>post(`/studies/${id}/lock`),
  correctSearch:(id,corrections)=>post(`/studies/${id}/search-clicks`,{corrections}),
  select:id=>post(`/studies/${id}/selection`),
  reportBatch:(id,x)=>post(`/studies/${id}/validation-batches`,x),
  unblind:(id,batch_key)=>post(`/studies/${id}/unblind`,{batch_key}),
  decide:(id,note)=>post(`/studies/${id}/decision`,{note}),
  exportCsv:id=>request(`/studies/${id}/export`),
};
