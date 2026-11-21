import {DOMAIN} from '../constants/domain.js';
import {store,load,loadCohort} from '../stores/research.js';
import {studies} from '../api/research.js';
import {studySelect} from '../components/common/study-select.js';
import {status} from '../components/common/status.js';
import {table} from '../components/common/table.js';
import {esc} from '../utils/format.js';
import {bindForm} from '../hooks/forms.js';
import {SPLIT_LABELS,ARM_LABELS} from '../types/enums.js';

export async function render(){
  await loadCohort();
  const c=store.cohort;
  const writable=localStorage.getItem('research-role')!=='viewer';
  const locked=c?.lock;
  const study=store.studies.find(s=>s.id===store.studyId);
  const members=c?.members||[];
  return `<div class="eyebrow">01 / PRE-LAUNCH REGISTER</div><h1>${DOMAIN.study_label}与${DOMAIN.row_label}</h1><p>开投前录入每个人的搜寻/复核归属、重叠标签与原分派。锁定后成员表冻结，任何改动都会另起计划。</p><div class="toolbar">${studySelect()}${study?status(study.state):''}</div>
  ${writable?`<details ${locked?'':'open'}><summary>新增${DOMAIN.study_label}</summary><form id="study-form" class="inline-form"><label>名称<input name="name" required minlength="2"></label><label>来源文件<input name="source_filename" value="audience-202611.csv" required></label><label>说明<input name="description"></label><button type="submit">保存计划</button></form></details>`:''}
  ${c?`<div class="checksum">归属校验 SHA256 ${c.assignment_checksum||'（暂无成员）'}</div>
  ${locked?`<div class="method-note"><strong>归属已锁定</strong><p>锁定人 ${esc(c.lock.locked_by)} · ${esc(c.lock.created_at)} · 共 ${c.lock.member_count} 人（搜寻 ${c.lock.search_count} / 复核 ${c.lock.validation_count}）。成员表不可再改。</p></div>`
  :writable?`<div class="toolbar"><button id="lock-btn">锁定全部归属与原分派 →</button></div>`:''}
  ${writable&&!locked?`<h2>录入${DOMAIN.row_label}（可批量）</h2><form id="member-form"><label>批量粘贴：每行「成员编号,标签1|标签2,搜寻|复核,对照|处理,搜寻点击(复核集留空)」<textarea name="bulk" class="mono" placeholder="M-001,冬季关注|高活跃,search,control,1
M-002,冬季关注,validation,treatment,"></textarea></label><button type="submit">按行录入</button></form>`:''}
  <h2>成员明细 <small>${members.length} 人 · 锁定后即冻结</small></h2>
  ${table(['成员编号','重叠标签','锁定归属','原分派','搜寻点击',...(writable&&!locked?['操作']:[])],
    members.map(m=>[m.source_key,m.labels.join(' | '),SPLIT_LABELS[m.split],ARM_LABELS[m.arm],m.search_click??'—',
      ...(writable&&!locked?[{html:`<button class="text" data-del="${m.id}">移除</button>`}]:[])]))}
  `:'<p class="method-note">先创建或选择一个投放计划。</p>'}`;
}

export function bind(refresh){
  const sel=document.getElementById('study-select');
  if(sel)sel.onchange=()=>{store.studyId=+sel.value;refresh();};
  bindForm('study-form',async data=>{const s=await studies.create(data);store.studyId=s.id;await load();refresh();});
  bindForm('member-form',async data=>{
    const rows=parseBulk(data.bulk);
    if(!rows.length)throw new Error('没有可解析的行');
    await studies.addMembers(store.studyId,rows);
    await load();refresh();
  });
  const lock=document.getElementById('lock-btn');
  if(lock)lock.onclick=async()=>{
    if(!confirm('锁定后成员归属与原分派不可再修改，确认继续？'))return;
    try{await studies.lock(store.studyId);await load();refresh();}
    catch(e){document.getElementById('notice').textContent=e.message;}
  };
  document.querySelectorAll('[data-del]').forEach(el=>el.onclick=async()=>{
    try{await studies.removeMember(store.studyId,+el.dataset.del);await load();refresh();}
    catch(e){document.getElementById('notice').textContent=e.message;}
  });
}

export function parseBulk(text){
  return String(text||'').split(/\r?\n/).map(line=>line.trim()).filter(Boolean).map(line=>{
    const [source_key,labels,split,arm,click]=line.split(',').map(x=>(x??'').trim());
    if(!source_key||!labels||!split||!arm)throw new Error('每行至少需要 编号、标签、归属、分派：'+line);
    const row={source_key,labels:labels.split('|').map(x=>x.trim()).filter(Boolean),split,arm};
    if(split==='search')row.search_click=click===''?null:Number(click);
    return row;
  });
}
