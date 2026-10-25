"""Restart-safe refresh worker; safe to run in multiple web/worker processes."""
from __future__ import annotations

import asyncio
import logging
import threading
import uuid

from .persistence import iso

log = logging.getLogger(__name__)


class ForecastWorker:
    def __init__(self, service, *, owner=None, lease_seconds=300):
        self.service = service
        self.owner = owner or 'worker_' + uuid.uuid4().hex
        self.lease_seconds = lease_seconds

    def process_one(self, *, job_id=None):
        with self.service.store.operation():
            return self._process_one(job_id=job_id)

    def _process_one(self, *, job_id=None):
        store = self.service.store
        job = store.claim(self.owner, iso(self.service.now()), lease_seconds=self.lease_seconds, job_id=job_id)
        if not job:
            return False
        heartbeat_stop = threading.Event()
        def renew():
            while not heartbeat_stop.wait(max(0.001, self.lease_seconds / 3)):
                try:
                    if not store.heartbeat(job['id'], job['lease_token'], iso(self.service.now()), lease_seconds=self.lease_seconds):
                        return
                except Exception:
                    log.exception('forecast lease heartbeat failed: %s', job['id'])
                    return
        heartbeat = threading.Thread(target=renew, daemon=True)
        heartbeat.start()
        try:
            snapshot = store.get_snapshot(job['snapshot_id'])
            targets = []
            if job['job_type'] == 'interpretation':
                from .evidence import extract_event
                envelope = job['job_payload']['envelope']
                drivers = extract_event(envelope, snapshot)
                self.service.validate_drivers(drivers)
                bundle = {'envelope': envelope, 'drivers': drivers}
            elif job['job_type'] == 'scenario':
                bundle = self.service.builder(snapshot, run_id=job['run_id'], generated_at=iso(self.service.now()), drivers=job['job_payload']['drivers'])
                bundle.update(scenario_id=job['run_id'], parent_run_id=job['parent_run_id'], is_scenario=True, job_id=job['id'], status='succeeded')
            else:
                from forecasting.learning import build_learning_bundle
                bundle = build_learning_bundle(snapshot, run_id=job['run_id'], generated_at=iso(self.service.now()), builder=self.service.builder)
                targets = bundle.pop('learning_targets', [])
            store.complete(job['id'], job['lease_token'], bundle, iso(self.service.now()), issued_targets=targets)
        except Exception as exc:
            log.exception('forecast refresh failed: %s', job['id'])
            store.fail(job['id'], job['lease_token'], str(exc), iso(self.service.now()), retry_seconds=5 * job['attempts'])
        finally:
            heartbeat_stop.set()
            heartbeat.join(timeout=1)
        return True

    async def run_forever(self, stop: asyncio.Event, *, poll_seconds=1, schedule=True):
        while not stop.is_set():
            try:
                if schedule:
                    await asyncio.to_thread(self.service.schedule_due)
                worked = await asyncio.to_thread(self.process_one)
            except Exception:
                # Repository/reset outages must not permanently kill the scheduler.
                log.exception('forecast polling failed; retrying after the polling interval')
                worked = False
            if not worked:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=poll_seconds)
                except TimeoutError:
                    pass
