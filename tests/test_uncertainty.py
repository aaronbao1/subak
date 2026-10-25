from datetime import date, datetime, timedelta, timezone
import pytest
from forecasting.uncertainty import CalibrationPoint, cumulative_interval, JointPaths, empirical_quantile

UTC=timezone.utc
CUTOFF=datetime(2025,5,1,tzinfo=UTC)
def points(n):
    return tuple(CalibrationPoint(str(i), date(2024,1,1)+timedelta(days=i*7), date(2024,1,8)+timedelta(days=i*7), 10, 12, datetime(2024,1,8,tzinfo=UTC)+timedelta(days=i*7), 'p', 'team') for i in range(n))

def test_exact_horizon_conformal_boundary_does_not_cap_infinity():
    r=cumulative_interval(10,points(18),cutoff=CUTOFF,horizon=7,procedure_id='p',scope='team',alpha=.05)
    assert r.status == 'insufficient_evidence' and r.lower is None and r.upper is None
    r=cumulative_interval(10,points(19),cutoff=CUTOFF,horizon=7,procedure_id='p',scope='team',alpha=.05)
    assert (r.lower,r.upper)==(8,12)
    assert r.event_probability is None
    assert r.capabilities == ('cumulative_interval',)

def test_calibration_excludes_immature_mismatch_and_revisions_replace_once():
    base=points(20)
    late=CalibrationPoint('late',date(2025,4,1),date(2025,4,8),0,100,datetime(2026,1,1,tzinfo=UTC),'p','team')
    r=cumulative_interval(10,base+(late,base[0]),cutoff=CUTOFF,horizon=7,procedure_id='p',scope='team')
    assert r.n == 20 and r.upper == 12
    assert cumulative_interval(10,base,cutoff=CUTOFF,horizon=30,procedure_id='p',scope='team').n == 0
    revised=CalibrationPoint('0',base[0].target_start,base[0].target_end,10,100,CUTOFF,'p','team',revision=2)
    assert cumulative_interval(10,base+(revised,),cutoff=CUTOFF,horizon=7,procedure_id='p',scope='team').upper == 100

def test_overlapping_calibration_targets_rejected():
    base=points(20)
    overlap=CalibrationPoint('overlap',base[0].target_start,base[0].target_end,10,12,base[0].mature_at,'p','team')
    with pytest.raises(ValueError,match='overlap'):
        cumulative_interval(10,base+(overlap,),cutoff=CUTOFF,horizon=7,procedure_id='p',scope='team')

def test_joint_paths_preserve_correlation_and_quantiles_of_totals():
    dependent=JointPaths(('quiet','burst'),('a','b'),(((0,),(0,)),((100,),(100,))),(.9,.1))
    independent=JointPaths(('00','01','10','11'),('a','b'),(((0,),(0,)),((0,),(100,)),((100,),(0,)),((100,),(100,))),(.81,.09,.09,.01))
    assert dependent.exceedance(150) == pytest.approx(.1)
    assert independent.exceedance(150) == pytest.approx(.01)
    daily=JointPaths(('00','01','10','11'),('a',),(((0,0),),((0,100),),((100,0),),((100,100),)),(.9216,.0384,.0384,.0016))
    assert empirical_quantile((0,100),(.96,.04),.95)==0
    assert daily.quantile(.95)==100

def test_signed_paths_not_clipped_or_forced_monotone():
    paths=JointPaths(('refund',),('team',),(((100,-120),),),(1.,))
    assert paths.totals() == (-20,)
    assert paths.exceedance(0)==0

def test_pending_revision_removes_old_residual_and_revision_target_cannot_change():
    from dataclasses import replace
    base=points(20)
    pending=replace(base[0],revision=2,available_at=CUTOFF,mature_at=CUTOFF+timedelta(days=2),status='pending')
    result=cumulative_interval(10,base+(pending,),cutoff=CUTOFF,horizon=7,procedure_id='p',scope='team')
    assert result.n==19
    bad=replace(base[0],revision=2,target_start=base[0].target_start+timedelta(days=1))
    with pytest.raises(ValueError,match='identity'):
        cumulative_interval(10,base+(bad,),cutoff=CUTOFF,horizon=7,procedure_id='p',scope='team')

def test_half_open_exact_horizon_calibration_accepts_exclusive_end_midnight():
    records=tuple(CalibrationPoint(str(i),date(2024,1,1)+timedelta(days=7*i),date(2024,1,8)+timedelta(days=7*i),10,12,datetime(2024,1,8,tzinfo=UTC)+timedelta(days=7*i),'p','t') for i in range(20))
    result=cumulative_interval(10,records,cutoff=CUTOFF,horizon=7,procedure_id='p',scope='t')
    assert result.n==20 and (result.lower,result.upper)==(8,12)
    assert cumulative_interval(10,records,cutoff=CUTOFF,horizon=8,procedure_id='p',scope='t').n==0

def test_half_open_calibration_month_remainder_has_eight_days_not_nine():
    record=CalibrationPoint('month',date(2025,1,24),date(2025,2,1),8,9,datetime(2025,2,1,tzinfo=UTC),'p','t')
    result=cumulative_interval(8,(record,),cutoff=datetime(2025,2,1,tzinfo=UTC),horizon=8,procedure_id='p',scope='t',alpha=.5)
    assert result.n==1 and (result.lower,result.upper)==(7,9)

def test_half_open_calibration_midnight_equivalent_offset_is_eligible():
    end=date(2025,1,8)
    same_instant=datetime(2025,1,7,16,tzinfo=timezone(timedelta(hours=-8)))
    record=CalibrationPoint('week',date(2025,1,1),end,7,9,same_instant,'p','t')
    result=cumulative_interval(7,(record,),cutoff=datetime(2025,1,8,tzinfo=UTC),horizon=7,procedure_id='p',scope='t',alpha=.5)
    assert result.n==1 and (result.lower,result.upper)==(5,9)
    with pytest.raises(ValueError,match='maturity'):
        CalibrationPoint('early',date(2025,1,1),end,7,9,same_instant-timedelta(microseconds=1),'p','t')

def test_joint_paths_freeze_supplied_nested_mutable_values_and_identity():
    ids=['quiet','burst']
    entities=['t']
    values=[[[0]],[[100]]]
    weights=[.9,.1]
    paths=JointPaths(ids,entities,values,weights)
    ids[1]='rewritten'
    entities[0]='other'
    values[1][0][0]=10000
    weights[:]=[0,1]
    assert paths.path_ids==('quiet','burst') and paths.entities==('t',)
    assert paths.values==(((0,),),((100,),)) and paths.weights==(.9,.1)
    assert paths.exceedance(50)==pytest.approx(.1)
    assert paths.expected_excess(50)==pytest.approx(5)
    with pytest.raises(TypeError):paths.values[1][0][0]=10000

@pytest.mark.parametrize('threshold',[float('nan'),float('inf'),float('-inf')])
def test_joint_paths_expected_excess_rejects_nonfinite_threshold(threshold):
    paths=JointPaths(('p',),('t',),(((100,),),),(1.,))
    with pytest.raises(ValueError,match='finite threshold'):
        paths.expected_excess(threshold)
