from src.config.domain import DOMAIN

SPLITS={x[0] for x in DOMAIN['splits']}
ARMS={x[0] for x in DOMAIN['arms']}


def text(value,label,limit):
    if not isinstance(value,str): raise ValueError(label+'必须是文本')
    value=value.strip()
    if not value: raise ValueError(label+'不得为空')
    if len(value)>limit: raise ValueError(label+f'不得超过{limit}个字符')
    return value


def clean_labels(raw):
    if not isinstance(raw,list): raise ValueError('标签必须是数组')
    if not 1<=len(raw)<=12: raise ValueError('每位成员须有1到12个标签')
    labels=[]
    for x in raw:
        item=text(x,'标签',40)
        if item not in labels: labels.append(item)
    return sorted(labels)


def clean_click(raw,label='点击'):
    if raw is None: return None
    if isinstance(raw,bool) or not isinstance(raw,(int,float)): raise ValueError(label+'必须是0或1')
    if int(raw)!=raw or int(raw) not in (0,1): raise ValueError(label+'必须是0或1')
    return int(raw)


def clean_member(data):
    source_key=text(data.get('source_key'),'成员编号',100)
    labels=clean_labels(data.get('labels'))
    split=data.get('split')
    if split not in SPLITS: raise ValueError('锁定归属必须为搜寻集或复核集')
    arm=data.get('arm')
    if arm not in ARMS: raise ValueError('原分派必须为对照或处理')
    click=clean_click(data.get('search_click'),'搜寻点击')
    if split=='validation' and click is not None: raise ValueError('复核集成员不得携带搜寻点击')
    return {'source_key':source_key,'labels':labels,'split':split,'arm':arm,'search_click':click}


def clean_corrections(items):
    if not items: raise ValueError('至少提交一条更正')
    seen=set();out=[]
    for item in items:
        key=text(item.get('source_key'),'成员编号',100)
        if key in seen: raise ValueError('更正记录中的成员编号重复：'+key)
        seen.add(key)
        click=clean_click(item.get('click'))
        if click is None: raise ValueError('搜寻点击更正必须为0或1')
        out.append((key,click))
    return out


def clean_reports(items):
    if not items: raise ValueError('至少提交一条复核报告')
    seen=set();out=[]
    for item in items:
        key=text(item.get('source_key'),'成员编号',100)
        if key in seen: raise ValueError('复核报告中的成员编号重复：'+key)
        seen.add(key)
        out.append({'source_key':key,'click':clean_click(item.get('click'),'复核点击')})
    return out
