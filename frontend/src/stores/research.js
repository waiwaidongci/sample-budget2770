import {studies} from '../api/research.js';

export const store={studies:[],studyId:0,cohort:null};

export async function load(){
  store.studies=await studies.list();
  if(!store.studyId||!store.studies.some(s=>s.id===store.studyId))store.studyId=store.studies[0]?.id||0;
}

export async function loadCohort(){
  store.cohort=store.studyId?await studies.cohort(store.studyId):null;
  return store.cohort;
}

export const stateOf=study=>study?.state||'unlocked';
