import math
import pytest
from src.services import analysis


def test_wilson_matches_known():
    low,high=analysis.wilson(5,10,1.959963984540054)
    assert low==pytest.approx(0.2366,abs=1e-3)
    assert high==pytest.approx(0.7634,abs=1e-3)


def test_newcombe_matches_published_example():
    # Newcombe (1998) method 10 example: 56/70 vs 48/80 -> diff 0.2
    d,low,high=analysis.newcombe(48,80,56,70,1.959963984540054)
    assert d==pytest.approx(0.2)
    assert low==pytest.approx(0.0524,abs=1e-3)
    assert high==pytest.approx(0.3339,abs=1e-3)


def test_search_table_equal_sizes():
    members=[
        {'split':'search','search_click':1,'arm':'treatment','labels':['A']},
        {'split':'search','search_click':0,'arm':'treatment','labels':['A']},
        {'split':'search','search_click':0,'arm':'control','labels':['A']},
        {'split':'search','search_click':0,'arm':'control','labels':['A']},
    ]
    rows=analysis.search_table(members)
    assert rows[0]['difference']==pytest.approx(0.5)


def test_selection_uses_only_search_split():
    members=[
        {'split':'search','search_click':1,'arm':'treatment','labels':['A']},
        {'split':'search','search_click':0,'arm':'control','labels':['A']},
        {'split':'validation','search_click':None,'arm':'treatment','labels':['B']},
        {'split':'validation','search_click':None,'arm':'control','labels':['B']},
    ]
    rows=analysis.search_table(members)
    assert [r['label'] for r in rows]==['A']
    assert analysis.select_label(rows)['label']=='A'


def test_missing_report_is_not_zero():
    members=[{'source_key':'c1','split':'validation','arm':'control','labels':['A']},
             {'source_key':'c2','split':'validation','arm':'control','labels':['A']},
             {'source_key':'t1','split':'validation','arm':'treatment','labels':['A']}]
    reports=[{'source_key':'c1','click':0},{'source_key':'c2','click':None},{'source_key':'t1','click':1}]
    out=analysis.validation_outcome(members,reports,'A')
    assert out['control_n']==1 and out['control_click']==0
    assert out['missing']==['c2']
    assert out['treatment_n']==1


def test_verdict_depends_on_lower_bound():
    outcome={'control_click':0,'control_n':50,'treatment_click':0,'treatment_n':50,'used':[],'missing':[]}
    result=analysis.evaluate('A',0.1,outcome)
    assert result['ci_low']<=0 and result['verdict']=='do_not_expand'
    outcome={'control_click':2,'control_n':50,'treatment_click':20,'treatment_n':50,'used':[],'missing':[]}
    result=analysis.evaluate('A',0.4,outcome)
    assert result['ci_low']>0 and result['verdict']=='can_expand'
