from app.forecasting.demo import run_demo


def test_executable_publication_evidence_explanation_scenario_and_learning(tmp_path):
    report=run_demo(tmp_path/'demo')
    assert report['passed'] is True
    assert len(report['checks']) >= 13
    assert all(report['checks'].values())
    assert report['initial_run_id'] != report['published_run_id']
    assert report['truth_source']=='independent synthetic observed usage, not forecast output'
    assert (tmp_path/'demo'/'northstar-history.json').exists()
