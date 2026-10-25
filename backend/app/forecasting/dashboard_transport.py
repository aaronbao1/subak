"""Opt-in dashboard wire representation; immutable forecast values are unchanged.

Repeated driver objects are interned by their full JSON content, including object
field order. Clients reconstruct each occurrence independently from its reference.
Detailed calculations remain available from the unchanged explanation endpoint.
"""
from __future__ import annotations

import json


def dashboard_transport(bundle: dict) -> dict:
    """Compact a fresh views response without copying or changing its nested data."""
    result = {key: value for key, value in bundle.items() if key != 'calculations'}
    pool = {}
    identities = {}

    def reference(driver):
        # IDs are not content identities. Two revisions may legitimately share an
        # ID; field insertion order is also visible in parameter-detail rendering.
        identity = json.dumps(driver, separators=(',', ':'), allow_nan=False)
        key = identities.get(identity)
        if key is None:
            key = 'd' + str(len(pool))
            identities[identity] = key
            pool[key] = driver
        return key

    if 'views' in bundle:
        views = []
        for original in bundle['views']:
            view = dict(original)
            for field, refs in (('included_drivers', 'included_driver_refs'),
                                ('queued_changes', 'queued_change_refs')):
                if field in view:
                    drivers = view.pop(field)
                    view[refs] = None if drivers is None else [reference(driver) for driver in drivers]
            views.append(view)
        result['views'] = views
    actuals = bundle.get('current_actuals')
    if isinstance(actuals, dict):
        result['current_actuals'] = {key: value for key, value in actuals.items()
                                     if key not in ('observations', 'coverage', 'required_sources')}
    return {**result, 'transport': 'forecast-dashboard-v1', 'driver_pool': pool}
