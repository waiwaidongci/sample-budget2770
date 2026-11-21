import {store,load,loadCohort} from '../stores/research.js';
import {studies} from '../api/research.js';
import {studySelect} from '../components/common/study-select.js';
import {status} from '../components/common/status.js';
import {table} from '../components/common/table.js';
import {download} from '../utils/download.js';
import {esc,pct,ci} from '../utils/format.js';
import {bindForm} from '../hooks/forms.js';
import {VERDICT_LABELS} from '../types/enums.js';

export async function render(){
  await loadCohort();
  const c=store.cohort;
  const writable=localStorage.getItem('research-role')!=='viewer';
  const isAdmin=localStorage.getItem('research-role')==='admin';
  const study=store.studies.find(s=>s.id===store.studyId);
  if(!c)return `<div class="eyebrow">04 / UNBLIND & DECISION</div><h1>揭盲与预算决策</h1><p class="method-note">先创建投放计划。</p>`;
  const active=c.active_selection;
  const uni=c.unblind;
  const r=uni?.result;
  const openBatches=(c.batches||[]).filter(b=>b.status!=='sealed');
  return `<div class="eyebrow">04 / UNBLIND & DECISION</div><h1>揭盲与预算决策</h1><p>揭盲一次只取一个完整批次，按开投前的原分派计算复核集点击率差与 95% 区间。页面用<b>区间下限是否为正</b>说明能否追加；无论结论如何，原预算照常执行。结论一经揭盲不可覆盖。</p>
  <div class="toolbar">${studySelect()}${study?status(study.state):''}</div>
  ${!active?`<p class="method-note">尚未选群。先到「搜寻选群」锁定最大点击率差人群。</p>`:''}
  ${active&&!uni?`<section class="result-intro"><strong>待验证人群：${esc(active.label)}</strong><p>搜寻集点击率差 ${pct(active.difference)} · ${active.is_current?'搜寻数据一致':'搜寻数据已更正，需先重选'}</p></section>
    ${isAdmin?`<h2>揭盲一个完整批次</h2>${openBatches.length?`<form id="unblind-form" class="worksheet"><label>选择要揭盲的完整批次<select name="batch_key">${openBatches.map(b=>`<option value="${esc(b.batch_key)}">${esc(b.batch_key)} · 报告${b.report_count} · 缺报${b.missing_count}</option>`).join('')}</select></label><p><small>缺报成员会被排除，不计为零；该批揭盲后封存，不再接收补报。</small></p><button type="submit">锁定并揭盲 →</button></form>`:'<p class="method-note">尚无复核批次。先到「复核记录」录入。</p>'}`:'<p class="method-note">仅负责人可以揭盲。</p>'}`:''}
  ${uni&&r?`<h2>揭盲结论</h2>
    <section class="result-intro ${uni.verdict==='can_expand'?'good':'warn'}"><strong>${VERDICT_LABELS[uni.verdict]}</strong><p>${uni.verdict==='can_expand'?'复核集差值区间下限大于 0，说明追加投放的增量为正，可在此人群追加；原预算照常。':'复核集差值区间下限不为正，暂无证据支持追加；原预算照常，不要据本轮加投。'}</p></section>
    ${table(['指标','数值'],[
      ['锁定人群',uni.label],
      ['复核批次',uni.batch_key],
      ['原分派·对照',`${r.control_click}/${r.control_n}（${pct(r.control_rate)}）`],
      ['原分派·处理',`${r.treatment_click}/${r.treatment_n}（${pct(r.treatment_rate)}）`],
      ['差值（处理-对照）',pct(r.difference)],
      [`${r.ci_level}% 区间`,ci(r.ci_low,r.ci_high)],
      ['区间下限是否为正',r.ci_low>0?'是':'否'],
      ['缺报（已排除，不计零）',r.missing.length?r.missing.join('、'):'无'],
      ['揭盲人 / 时间',`${uni.created_by} · ${uni.created_at}`]])}
    <div class="toolbar"><button id="export">下载结论 CSV</button></div>
    <h2>预算决策 <small>复核不可覆盖</small></h2>
    ${uni.decision?`<div class="method-note"><strong>已复核</strong><p>${esc(uni.decision.note)}</p><small>${esc(uni.decision.author)} · ${esc(uni.decision.created_at)}</small></div>`
      :isAdmin?`<form id="decision-form"><label>复核意见与后续动作（写明区间下限判断与原预算安排）<textarea name="note" minlength="5" maxlength="2000" required></textarea></label><button type="submit">确认复核并归档</button></form>`
      :'<div class="method-note">等待负责人复核；分析师可查看全部依据。</div>'}
  `:''}`;
}

export function bind(refresh){
  const sel=document.getElementById('study-select');
  if(sel)sel.onchange=()=>{store.studyId=+sel.value;refresh();};
  bindForm('unblind-form',async data=>{await studies.unblind(store.studyId,data.batch_key);await load();refresh();});
  bindForm('decision-form',async data=>{await studies.decide(store.studyId,data.note);await load();refresh();});
  const exp=document.getElementById('export');
  if(exp)exp.onclick=async()=>{
    try{download(await studies.exportCsv(store.studyId),'audience-lift-'+store.studyId+'.csv');}
    catch(e){document.getElementById('notice').textContent=e.message;}
  };
}
