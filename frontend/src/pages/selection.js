import {DOMAIN} from '../constants/domain.js';
import {store,load,loadCohort} from '../stores/research.js';
import {studies} from '../api/research.js';
import {studySelect} from '../components/common/study-select.js';
import {status} from '../components/common/status.js';
import {table} from '../components/common/table.js';
import {esc,pct} from '../utils/format.js';
import {bindForm} from '../hooks/forms.js';

export async function render(){
  await loadCohort();
  const c=store.cohort;
  const writable=localStorage.getItem('research-role')!=='viewer';
  const study=store.studies.find(s=>s.id===store.studyId);
  if(!c)return `<div class="eyebrow">02 / SEARCH-SPLIT SELECTION</div><h1>搜寻集选群</h1><p class="method-note">先创建投放计划。</p>`;
  const locked=!!c.lock;
  const unblinded=!!c.unblind;
  const active=c.active_selection;
  const fresh=active?.is_current;
  const canSelect=writable&&locked&&!unblinded;
  return `<div class="eyebrow">02 / SEARCH-SPLIT SELECTION</div><h1>${DOMAIN.field_label}</h1><p class="lead">只用搜寻集的点击，比较每个重叠标签在「处理-对照」上的点击率差，选差最大的一群作为候选追加受众。复核集在此阶段完全不参与。</p><div class="method-note">${DOMAIN.note}</div>
  <div class="toolbar">${studySelect()}${study?status(study.state):''}</div>
  ${!locked?`<p class="method-note">尚未锁定归属，不能选群。回到来源录入页锁定成员。</p>`:''}
  ${unblinded?`<p class="method-note">该计划已揭盲。复核集只验证当时锁定的人群，不能再改选。</p>`:''}
  ${active?`<section class="result-intro"><strong>当前锁定人群：${esc(active.label)}</strong><p>搜寻集点击率差 ${pct(active.difference)} · 锁定于 ${esc(active.created_at)} · ${active.is_current?'与当前搜寻数据一致':'搜寻数据已更正，需重选'}</p></section>`:''}
  ${canSelect?`<div class="toolbar"><button id="select-btn" ${active&&fresh?'disabled':''}>${active?'按最新搜寻数据重新选群':'锁定最大点击率差人群 →'}</button></div>${active&&fresh?'<p><small>搜寻数据未变；如变更了搜寻点击，更正后可再点。</small></p>':''}`:''}
  ${writable&&locked&&!unblinded?`<h2>更正搜寻点击</h2><form id="correct-form"><label>每行「成员编号,点击(0/1)」<textarea name="bulk" class="mono" placeholder="1-0007,1
1-0011,0"></textarea></label><button type="submit">提交更正（选群可改选，已揭盲则拒绝）</button></form>`:''}
  ${active?.detail?.table?`<h2>搜寻集逐标签点击率差 <small>选群时冻结</small></h2>${table(['重叠标签','对照点击/人数','对照点击率','处理点击/人数','处理点击率','处理率差','是否可比较'],
    (active.detail.table||[]).map(r=>[r.label,`${r.control_click}/${r.control_n}`,pct(r.control_rate),`${r.treatment_click}/${r.treatment_n}`,pct(r.treatment_rate),r.difference==null?'—':pct(r.difference),r.complete?'是':'否（某臂无人）']))}`:''}
  ${c.selections.length>1?`<h2>选群历史 <small>改选只追加，不覆盖</small></h2>${table(['编号','标签','差值','状态','时间','搜索指纹'],c.selections.map(s=>[s.id,s.label,pct(s.difference),s.status==='active'?'当前':'已被改选替代',s.created_at,s.search_fingerprint.slice(0,12)]))}`:''}`;
}

export function bind(refresh){
  const sel=document.getElementById('study-select');
  if(sel)sel.onchange=()=>{store.studyId=+sel.value;refresh();};
  const btn=document.getElementById('select-btn');
  if(btn)btn.onclick=async()=>{
    btn.disabled=true;
    try{await studies.select(store.studyId);await load();refresh();}
    catch(e){document.getElementById('notice').textContent=e.message;btn.disabled=false;}
  };
  bindForm('correct-form',async data=>{
    const corrections=String(data.bulk||'').split(/\r?\n/).map(x=>x.trim()).filter(Boolean).map(line=>{
      const [source_key,click]=line.split(',').map(x=>(x??'').trim());
      if(!source_key||click==='')throw new Error('每行需要「成员编号,点击」：'+line);
      return {source_key,click:Number(click)};
    });
    if(!corrections.length)throw new Error('没有可解析的更正');
    await studies.correctSearch(store.studyId,corrections);
    await load();refresh();
  });
}
