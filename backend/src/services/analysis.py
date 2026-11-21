import math

from scipy import stats


def rate(success,total):
    return success/total if total else None


def wilson(success,total,z):
    """Wilson score interval for a binomial proportion."""
    if total<=0: return (None,None)
    p=success/total
    denom=1+z*z/total
    centre=(p+z*z/(2*total))/denom
    half=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/denom
    return (max(0.,centre-half),min(1.,centre+half))


def newcombe(s1,n1,s2,n2,z):
    """Newcombe hybrid score interval for p2-p1 (treatment minus control)."""
    p1=s1/n1;p2=s2/n2
    l1,u1=wilson(s1,n1,z);l2,u2=wilson(s2,n2,z)
    d=p2-p1
    low=d-math.sqrt((p2-l2)**2+(u1-p1)**2)
    high=d+math.sqrt((u2-p2)**2+(p1-l1)**2)
    return d,max(-1.,low),min(1.,high)


def z_for(confidence=0.95):
    if not 0.5<=confidence<1: raise ValueError('置信水平必须在0.5到1之间')
    return float(stats.norm.ppf(1-(1-confidence)/2))


def search_table(members):
    """Per-label search-split click counts.

    Only members whose search click is observed (0/1) enter the denominators;
    an unobserved click is excluded rather than treated as a non-click.
    """
    buckets={}
    for m in members:
        if m['split']!='search' or m['search_click'] is None: continue
        for label in m['labels']:
            b=buckets.setdefault(label,{'control':[0,0],'treatment':[0,0]})
            b[m['arm']][0]+=int(m['search_click'])
            b[m['arm']][1]+=1
    rows=[]
    for label in sorted(buckets):
        b=buckets[label]
        c_s,c_n=b['control'];t_s,t_n=b['treatment']
        complete=c_n>=1 and t_n>=1
        rows.append({'label':label,
                     'control_click':c_s,'control_n':c_n,'treatment_click':t_s,'treatment_n':t_n,
                     'control_rate':rate(c_s,c_n),'treatment_rate':rate(t_s,t_n),
                     'difference':(rate(t_s,t_n)-rate(c_s,c_n)) if complete else None,
                     'complete':complete})
    return rows


def select_label(rows):
    """Largest treatment-minus-control click-rate difference among complete rows."""
    usable=[r for r in rows if r['complete']]
    if not usable: raise ValueError('搜寻集中没有同时具备对照与处理点击的标签，无法锁定人群')
    return max(usable,key=lambda r:(r['difference'],r['label']))


def validation_outcome(members,reports,label):
    """Aggregate the labelled validation members using only this batch's reports.

    A report with click=None and a member with no report are both missing: they are
    listed and excluded, never counted as a non-click. Arm comes from the lock.
    """
    clicks={r['source_key']:r['click'] for r in reports}
    control_s=control_n=treatment_s=treatment_n=0
    missing=[];used=[]
    for m in members:
        if m['split']!='validation' or label not in m['labels']: continue
        click=clicks.get(m['source_key'])
        if click is None:
            missing.append(m['source_key']);continue
        used.append(m['source_key'])
        if m['arm']=='control': control_s+=click;control_n+=1
        else: treatment_s+=click;treatment_n+=1
    if control_n<1 or treatment_n<1:
        raise ValueError(f'完整复核报告不足：对照{control_n}人、处理{treatment_n}人，每个原分派至少需要1人')
    return {'control_click':control_s,'control_n':control_n,
            'treatment_click':treatment_s,'treatment_n':treatment_n,
            'used':sorted(used),'missing':sorted(missing)}


def evaluate(label,selection_difference,outcome,confidence=0.95):
    z=z_for(confidence)
    d,low,high=newcombe(outcome['control_click'],outcome['control_n'],
                        outcome['treatment_click'],outcome['treatment_n'],z)
    return {'label':label,'selection_difference':selection_difference,
            'control_click':outcome['control_click'],'control_n':outcome['control_n'],
            'treatment_click':outcome['treatment_click'],'treatment_n':outcome['treatment_n'],
            'control_rate':outcome['control_click']/outcome['control_n'],
            'treatment_rate':outcome['treatment_click']/outcome['treatment_n'],
            'difference':d,'ci_low':low,'ci_high':high,'confidence':confidence,
            'ci_level':round(confidence*100,1),
            'verdict':'can_expand' if low>0 else 'do_not_expand',
            'used':outcome['used'],'missing':outcome['missing']}
