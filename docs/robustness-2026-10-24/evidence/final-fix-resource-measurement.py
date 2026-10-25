"""Bounded, deterministic measurement of the accepted root-work cap. No stress/OOM test."""
from datetime import date, datetime, timedelta, timezone
import json
import resource
import time
import tracemalloc

from forecasting.contracts import Target
from forecasting.state import (ExposureSpell, ExecutionMark, HurdleParameters,
                               generate_recurrent_scenarios, MAX_RECURRENT_ROOT_WORK)

origin = datetime(2024, 1, 1, tzinfo=timezone.utc)
dates = tuple(origin.date()+timedelta(days=i) for i in range(25))
exposures = tuple(ExposureSpell(str(i), str(i), 'team', dates[0], dates[-1]+timedelta(days=1), origin, True)
                  for i in range(10))
target = Target('tokens', 'org', 'metered_usage', 'tokens', None, ('fixture',), ('all',), support='nonnegative')
start = time.perf_counter()
tracemalloc.start()
result = generate_recurrent_scenarios(exposures, (), (HurdleParameters('team', 1, (2,), (ExecutionMark(1),)),),
    as_of=origin, dates=dates, path_count=100, seed=7, target=target, snapshot_id='bounded-measurement')
current, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()
roots = sum(len(path.roots) for path in result.paths)
assert roots == 50000 == MAX_RECURRENT_ROOT_WORK
assert result.bundle.totals() == (500.,)*100
report = {'paths':100, 'people':10, 'days':25, 'max_positive_count':2,
          'root_budget':MAX_RECURRENT_ROOT_WORK, 'emitted_roots':roots,
          'cells':25000, 'seconds_with_tracemalloc':time.perf_counter()-start,
          'tracemalloc_current_bytes':current, 'tracemalloc_peak_bytes':peak,
          'process_peak_rss_bytes_macos':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
          'qualification':'One finite fixture at cap, not production memory certification; serialization contributes to peak.'}
print(json.dumps(report, indent=2))
