import pytest
from tests.conftest import make_study,seed_members,VALIDATION


def lock_and_select(client,analyst,sid):
    assert client.post(f'/studies/{sid}/lock',headers=analyst).status_code==200
    r=client.post(f'/studies/{sid}/selection',headers=analyst)
    assert r.status_code==200,r.text
    return r.json()


def report_batch(client,headers,sid,key,clicks):
    reports=[{'source_key':k,'click':c} for k,c in clicks.items()]
    return client.post(f'/studies/{sid}/validation-batches',headers=headers,
                       json={'batch_key':key,'note':'batch','reports':reports})


def test_workflow_happy_path(client,admin,analyst):
    sid=make_study(client,analyst,'flow')
    big=[(f'vc{i}',['A'],'control') for i in range(40)]+[(f'vt{i}',['A'],'treatment') for i in range(40)]
    big+=[('v-c4',['B'],'control'),('v-t4',['B'],'treatment')]
    seed_members(client,analyst,sid,validation=big)
    sel=lock_and_select(client,analyst,sid)
    assert sel['label']=='A'
    assert sel['difference']==pytest.approx(2/3)

    clicks={f'vc{i}':int(i<8) for i in range(40)}
    clicks.update({f'vt{i}':int(i<24) for i in range(40)})
    clicks.update({'v-c4':0,'v-t4':0})
    r=report_batch(client,analyst,sid,'B1',clicks)
    assert r.status_code==200,r.text

    r=client.post(f'/studies/{sid}/unblind',headers=admin,json={'batch_key':'B1'})
    assert r.status_code==200,r.text
    result=r.json()['result']
    # v-c4/v-t4 carry only label B, outside the locked A audience.
    assert result['control_n']==40 and result['treatment_n']==40
    assert result['difference']==pytest.approx(0.4)
    assert result['ci_low']>0
    assert result['verdict']=='can_expand'
    assert result['missing']==[]


    r=client.post(f'/studies/{sid}/decision',headers=admin,json={'note':'区间为正，追加；原预算照常'})
    assert r.status_code==200,r.text

    cohort=client.get(f'/studies/{sid}/cohort',headers=analyst).json()
    assert cohort['unblind']['decision']['note'].startswith('区间为正')


def test_selection_refuses_before_lock(client,analyst):
    sid=make_study(client,analyst,'nolock')
    seed_members(client,analyst,sid)
    r=client.post(f'/studies/{sid}/selection',headers=analyst)
    assert r.status_code==409


def test_members_frozen_after_lock(client,analyst):
    sid=make_study(client,analyst,'frozen')
    seed_members(client,analyst,sid)
    assert client.post(f'/studies/{sid}/lock',headers=analyst).status_code==200
    r=client.post(f'/studies/{sid}/members',headers=analyst,
                  json={'rows':[{'source_key':'x','labels':['A'],'split':'search','arm':'control','search_click':1}]})
    assert r.status_code==409
    r=client.post(f'/studies/{sid}/lock',headers=analyst)
    assert r.status_code==409


def test_lock_requires_both_arms_in_both_splits(client,analyst):
    sid=make_study(client,analyst,'arms')
    rows=[{'source_key':'a','labels':['A'],'split':'search','arm':'control','search_click':1},
          {'source_key':'b','labels':['A'],'split':'validation','arm':'control'}]
    client.post(f'/studies/{sid}/members',headers=analyst,json={'rows':rows})
    r=client.post(f'/studies/{sid}/lock',headers=analyst)
    assert r.status_code==422


def test_search_correction_reselect_and_stale_block(client,analyst,admin):
    sid=make_study(client,analyst,'correct')
    seed_members(client,analyst,sid)
    first=lock_and_select(client,analyst,sid)
    assert first['label']=='A'
    # Flip B so treatment now dominates B: B control 0,0 / treatment 0,0 currently.
    # s-c4=0,s-c5=1 control ; s-t4=0,s-t5=0 treatment -> make control 0,0 and treatment 1,1
    r=client.post(f'/studies/{sid}/search-clicks',headers=analyst,
                  json={'corrections':[{'source_key':'s-c5','click':0},
                                       {'source_key':'s-t4','click':1},
                                       {'source_key':'s-t5','click':1}]})
    assert r.status_code==200,r.text
    # Report a batch first, then confirm unblind is blocked until reselection.
    report_batch(client,analyst,sid,'B1',{'v-c1':0,'v-c2':0,'v-c3':1,'v-c4':0,'v-t1':1,'v-t2':1,'v-t3':1,'v-t4':0})
    r=client.post(f'/studies/{sid}/unblind',headers=admin,json={'batch_key':'B1'})
    assert r.status_code==409
    again=client.post(f'/studies/{sid}/selection',headers=analyst)
    assert again.status_code==200,again.text
    assert again.json()['label']=='B'
    cohort=client.get(f'/studies/{sid}/cohort',headers=analyst).json()
    labels=[s['label'] for s in cohort['selections']]
    assert labels==['A','B']
    assert cohort['selections'][0]['status']=='superseded'


def test_selection_idempotent_without_changes(client,analyst):
    sid=make_study(client,analyst,'same')
    seed_members(client,analyst,sid)
    first=lock_and_select(client,analyst,sid)
    r=client.post(f'/studies/{sid}/selection',headers=analyst)
    assert r.status_code==409
    assert first['id']


def test_unblind_blocked_without_selection_and_batch(client,analyst,admin):
    sid=make_study(client,analyst,'guard')
    seed_members(client,analyst,sid)
    assert client.post(f'/studies/{sid}/lock',headers=analyst).status_code==200
    r=client.post(f'/studies/{sid}/unblind',headers=admin,json={'batch_key':'B1'})
    assert r.status_code==409


def test_missing_click_not_imputed_as_zero(client,analyst,admin):
    sid=make_study(client,analyst,'missing')
    seed_members(client,analyst,sid)
    lock_and_select(client,analyst,sid)
    # v-c3 and v-t3 carry the locked label A, so leaving them unreported must exclude them.
    clicks={'v-c1':0,'v-c2':0,'v-c3':None,'v-t1':1,'v-t2':1,'v-t3':None}
    r=report_batch(client,analyst,sid,'B1',clicks)
    assert r.status_code==200,r.text
    assert r.json()['batch']['missing_count']==2
    r=client.post(f'/studies/{sid}/unblind',headers=admin,json={'batch_key':'B1'})
    assert r.status_code==200,r.text
    result=r.json()['result']
    assert result['control_n']==2 and result['treatment_n']==2
    assert result['missing']==['v-c3','v-t3']

def test_unreported_labelled_member_counts_as_missing(client,analyst,admin):
    sid=make_study(client,analyst,'omitted')
    seed_members(client,analyst,sid)
    lock_and_select(client,analyst,sid)
    # No report at all for v-c3; it must be missing, not a control non-click.
    clicks={'v-c1':0,'v-c2':0,'v-t1':1,'v-t2':1}
    report_batch(client,analyst,sid,'B1',clicks)
    r=client.post(f'/studies/{sid}/unblind',headers=admin,json={'batch_key':'B1'})
    assert r.status_code==200,r.text
    result=r.json()['result']
    assert result['control_n']==2 and result['treatment_n']==2
    assert 'v-c3' in result['missing']


def test_partial_batch_never_unblinds_incomplete_at_report_time(client,analyst,admin):
    sid=make_study(client,analyst,'partial')
    seed_members(client,analyst,sid)
    lock_and_select(client,analyst,sid)
    # Only some reports, no completed batch flag: unblind must fail closed.
    r=report_batch(client,analyst,sid,'B1',{'v-c1':0,'v-t1':0})
    assert r.status_code==200
    r=client.post(f'/studies/{sid}/unblind',headers=admin,json={'batch_key':'B1'})
    assert r.status_code==200,r.text
    assert r.json()['result']['missing']


def test_sealed_batch_cannot_be_appended(client,analyst,admin):
    sid=make_study(client,analyst,'seal')
    seed_members(client,analyst,sid)
    lock_and_select(client,analyst,sid)
    report_batch(client,analyst,sid,'B1',{'v-c1':0,'v-c2':0,'v-c3':1,'v-c4':0,'v-t1':1,'v-t2':1,'v-t3':1,'v-t4':0})
    assert client.post(f'/studies/{sid}/unblind',headers=admin,json={'batch_key':'B1'}).status_code==200
    r=report_batch(client,analyst,sid,'B1',{'v-c4':1})
    assert r.status_code==409


def test_unblind_not_overwritten_and_decision_not_overwritten(client,analyst,admin):
    sid=make_study(client,analyst,'immutable')
    seed_members(client,analyst,sid)
    lock_and_select(client,analyst,sid)
    report_batch(client,analyst,sid,'B1',{'v-c1':0,'v-c2':0,'v-c3':1,'v-c4':0,'v-t1':1,'v-t2':1,'v-t3':1,'v-t4':0})
    assert client.post(f'/studies/{sid}/unblind',headers=admin,json={'batch_key':'B1'}).status_code==200
    # Second batch with contradictory data cannot replace the first verdict.
    report_batch(client,analyst,sid,'B2',{'v-c1':1,'v-c2':1,'v-c3':0,'v-c4':1,'v-t1':0,'v-t2':0,'v-t3':0,'v-t4':1})
    r=client.post(f'/studies/{sid}/unblind',headers=admin,json={'batch_key':'B2'})
    assert r.status_code==409
    assert client.post(f'/studies/{sid}/decision',headers=admin,json={'note':'同意追加投放'}).status_code==200
    r=client.post(f'/studies/{sid}/decision',headers=admin,json={'note':'再次复核覆盖'})
    assert r.status_code==409


def test_search_correction_blocked_after_unblind(client,analyst,admin):
    sid=make_study(client,analyst,'postunblind')
    seed_members(client,analyst,sid)
    lock_and_select(client,analyst,sid)
    report_batch(client,analyst,sid,'B1',{'v-c1':0,'v-c2':0,'v-c3':1,'v-c4':0,'v-t1':1,'v-t2':1,'v-t3':1,'v-t4':0})
    assert client.post(f'/studies/{sid}/unblind',headers=admin,json={'batch_key':'B1'}).status_code==200
    r=client.post(f'/studies/{sid}/search-clicks',headers=analyst,json={'corrections':[{'source_key':'s-c1','click':1}]})
    assert r.status_code==409


def test_roles(client,analyst,admin):
    sid=make_study(client,analyst,'roles')
    seed_members(client,analyst,sid)
    viewer=client.post('/auth/login',json={'email':'viewer@demo.local','password':'pw'}).json()['token']
    vh={'Authorization':'Bearer '+viewer}
    r=client.post(f'/studies/{sid}/lock',headers=vh)
    assert r.status_code==403
    assert client.post(f'/studies/{sid}/lock',headers=analyst).status_code==200
    sel=client.post(f'/studies/{sid}/selection',headers=analyst)
    assert sel.status_code==200,sel.text
    report_batch(client,analyst,sid,'B1',{'v-c1':0,'v-c2':0,'v-c3':1,'v-c4':0,'v-t1':1,'v-t2':1,'v-t3':1,'v-t4':0})
    # Analyst cannot unblind; only the owner can.
    r=client.post(f'/studies/{sid}/unblind',headers=analyst,json={'batch_key':'B1'})
    assert r.status_code==403
    assert client.post(f'/studies/{sid}/unblind',headers=admin,json={'batch_key':'B1'}).status_code==200


def test_validation_rejects_wrong_split_member(client,analyst):
    sid=make_study(client,analyst,'wrongsplit')
    seed_members(client,analyst,sid)
    lock_and_select(client,analyst,sid)
    r=report_batch(client,analyst,sid,'B1',{'s-c1':1})
    assert r.status_code==422


def test_viewer_export_requires_decision(client,admin,analyst):
    sid=make_study(client,analyst,'export')
    seed_members(client,analyst,sid)
    lock_and_select(client,analyst,sid)
    report_batch(client,analyst,sid,'B1',{'v-c1':0,'v-c2':0,'v-c3':1,'v-c4':0,'v-t1':1,'v-t2':1,'v-t3':1,'v-t4':0})
    assert client.post(f'/studies/{sid}/unblind',headers=admin,json={'batch_key':'B1'}).status_code==200
    viewer=client.post('/auth/login',json={'email':'viewer@demo.local','password':'pw'}).json()['token']
    vh={'Authorization':'Bearer '+viewer}
    assert client.get(f'/studies/{sid}/export',headers=vh).status_code==403
    assert client.post(f'/studies/{sid}/decision',headers=admin,json={'note':'同意按区间下限判断追加'}).status_code==200
    r=client.get(f'/studies/{sid}/export',headers=vh)
    assert r.status_code==200
    assert '区间结论' in r.text and '暂不追加投放' in r.text
    assert '差值' in r.text and '95%区间下限' in r.text
    assert 'e-' not in r.text  # fixed-point, never scientific notation
