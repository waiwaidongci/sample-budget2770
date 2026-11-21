import {DOMAIN} from '../constants/domain.js';
import {store} from '../stores/research.js';
import {status} from '../components/common/status.js';
import {table} from '../components/common/table.js';
import {VERDICT_LABELS} from '../types/enums.js';

export function render(){
  const counts=store.studies.reduce((acc,s)=>{acc[s.state]=(acc[s.state]||0)+1;return acc;},{});
  return `<div class="eyebrow">FIELD NOTES / ${DOMAIN.direction}</div><section class="hero"><div><h1>${DOMAIN.title}</h1><p class="lead">${DOMAIN.scenario}</p><a class="button" href="#data">登记投放计划 →</a></div><aside><span class="folio">${DOMAIN.id.slice(-2)}</span><p>${DOMAIN.algorithm}</p><small>开投前锁定 · 搜寻只选群 · 复核才揭盲 · 区间下限定追加</small></aside></section>
  <section class="strip"><span>${store.studies.length} 个${DOMAIN.study_label}</span><span>${store.studies.reduce((n,s)=>n+s.member_count,0)} 名受众</span><span>${counts.reviewed||0} 份已复核结论</span></section>
  <h2>四步方法</h2>
  <ol class="steps"><li><b>锁定</b>开投前固定每人的搜寻/复核归属、重叠标签与原分派，并生成归属 SHA256。</li><li><b>选群</b>只用搜寻集，选「处理-对照」点击率差最大的重叠标签；搜寻更正后可改选。</li><li><b>揭盲</b>复核点击按原分派汇总，补报与揭盲只取完整同批；缺报排除不记零。</li><li><b>决策</b>95% 区间下限为正才追加投放；揭盲结论不可覆盖，原预算照常。</li></ol>
  <h2>投放计划进度 <small>从锁定到复核的同一条链路</small></h2>
  ${table(['投放计划','来源文件','受众数','阶段','锁定人群','结论',''],store.studies.map(s=>[s.name,s.source_filename,s.member_count,{html:status(s.state)},s.locked_label||'—',s.verdict?VERDICT_LABELS[s.verdict]:'—',{html:`<a href="#data">打开 →</a>`}]))}`;
}
export function bind(){}
