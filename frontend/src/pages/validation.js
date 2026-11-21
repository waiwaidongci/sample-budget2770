import {store,load,loadCohort} from '../stores/research.js';
import {studies} from '../api/research.js';
import {studySelect} from '../components/common/study-select.js';
import {status} from '../components/common/status.js';
import {table} from '../components/common/table.js';
import {esc} from '../utils/format.js';
import {bindForm} from '../hooks/forms.js';

export async function render(){
  await loadCohort();
  const c=store.cohort;
  const writable=localStorage.getItem('research-role')!=='viewer';
  const study=store.studies.find(s=>s.id===store.studyId);
  if(!c)return `<div class="eyebrow">03 / VALIDATION REPORTS</div><h1>复核点击记录</h1><p class="method-note">先创建投放计划。</p>`;
  const active=c.active_selection;
  const labelled=(c.members||[]).filter(m=>m.split==='validation'&&(!active||m.labels.includes(active.label))).length;
  const batches=c.batches||[];
  return `<div class="eyebrow">03 / VALIDATION REPORTS</div><h1>复核点击记录</h1><p>复核集成员补齐点击。缺报不当作零：留空的成员记入缺报清单，揭盲时排除。同一批内补报会覆盖该批的旧值；已揭盲封存的批不再接收补报。</p>
  <div class="toolbar">${studySelect()}${study?status(study.state):''}</div>
  ${!c.lock?'<p class="method-note">尚未锁定归属。</p>':''}
  ${c.lock&&!active?'<p class="method-note">尚未用搜寻集选群；复核集只验证锁定人群。请先到「搜寻选群」页。</p>':''}
  ${active?`<section class="result-intro"><strong>复核对象：${esc(active.label)}</strong><p>该标签在复核集共 ${labelled} 人。批次按完整同批整体揭盲。</p></section>`:''}
  ${writable&&c.lock?`<h2>录入一批复核点击</h2><form id="batch-form" class="worksheet"><label>复核批次编号<input name="batch_key" required placeholder="如 V-2026-11-A"></label><label>批次说明<input name="note" placeholder="如 11月首周复核"></label><label>每行「成员编号,点击(0/1)」；未知或未回填可留空（记入缺报）<textarea name="bulk" class="mono" placeholder="1-0121,0
1-0122,1
1-0123,"></textarea></label><button type="submit">保存本批报告</button></form>`:''}
  <h2>复核批次 <small>${batches.length} 个</small></h2>
  ${batches.length?batches.map(b=>`<div class="batch-card"><h3>${esc(b.batch_key)} <span class="status ${b.status==='sealed'?'completed':'queued'}">${b.status==='sealed'?'已揭盲封存':'可补报'}</span></h3><p>${esc(b.note||'无说明')} · 报告 ${b.report_count} 条 · 缺报 ${b.missing_count} 条 · ${esc(b.created_at)}</p>${table(['成员编号','复核点击'],b.reports.map(r=>[r.source_key,r.click==null?'缺报（不计零）':r.click]))}</div>`).join(''):'<p>尚无复核批次。</p>'}`;
}

export function bind(refresh){
  const sel=document.getElementById('study-select');
  if(sel)sel.onchange=()=>{store.studyId=+sel.value;refresh();};
  bindForm('batch-form',async data=>{
    const reports=String(data.bulk||'').split(/\r?\n/).map(x=>x.trim()).filter(Boolean).map(line=>{
      const parts=line.split(',');
      const source_key=(parts[0]||'').trim();
      const raw=(parts[1]??'').trim();
      if(!source_key)throw new Error('缺少成员编号：'+line);
      return {source_key,click:raw===''?null:Number(raw)};
    });
    if(!reports.length)throw new Error('没有可解析的复核报告');
    await studies.reportBatch(store.studyId,{batch_key:data.batch_key,note:data.note,reports});
    await load();refresh();
  });
}
