"""Durable local acquisition/replay state; authenticated backend owns access.

Synthetic and actual acquisition inventories are separate namespaces. A repeated
byte delivery may reuse its original receipt; newly learned coverage/finality
facts always retain the actual new acquisition time.
"""
from __future__ import annotations
from dataclasses import replace
import json
from pathlib import Path
import sqlite3

from .contracts import ContractError, canonical_json, day, timestamp, strict
from .ingestion import SourceLedger
from .snapshot import Coverage


class SourceStore:
    def __init__(self,path):
        self.path=str(path)
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        with self._connect() as c:
            c.execute('CREATE TABLE IF NOT EXISTS source_state ('
                      'tenant TEXT, evidence_class TEXT, source_id TEXT, adapter TEXT, body TEXT NOT NULL, '
                      'PRIMARY KEY(tenant,evidence_class,source_id))')

    def _connect(self):
        return sqlite3.connect(self.path,timeout=30)

    @staticmethod
    def _scope(evidence_class,adapter):
        if evidence_class not in {'synthetic_fixture','authorized_local_file','public_trace'}:
            raise ValueError('explicit acquisition evidence class required')
        if adapter not in {'normalized','anthropic_cost_report'}:
            raise ValueError('unsupported acquisition adapter')

    @staticmethod
    def _decode(body,evidence_class):
        value=json.loads(body)
        if set(value)!={'schema_version','ledger','coverage'} or value['schema_version']!='1.0':
            raise ValueError('unsupported durable source schema')
        ledger=SourceLedger.from_dict(value['ledger'])
        # Legacy inventories predate receipt provenance. The durable namespace
        # is an acquisition fact owned by this trusted store, not a serving label.
        deliveries=[]
        for mode,extraction in ledger._deliveries:
            bound=extraction.receipt.evidence_class
            if bound not in {'unspecified',evidence_class}:raise ValueError('stored acquisition provenance mismatch')
            deliveries.append((mode,replace(extraction,receipt=replace(extraction.receipt,evidence_class=evidence_class))))
        ledger._deliveries=tuple(deliveries)
        coverage=[]
        for row in value['coverage']:
            item=strict(Coverage,row)
            item['start']=day(item['start']);item['end']=day(item['end']);item['known_at']=timestamp(item['known_at'])
            coverage.append(Coverage(**item))
        return ledger,tuple(coverage)

    def acquire(self,extraction,coverage,*,evidence_class,adapter,semantics='replacement'):
        """Trusted acquisition boundary: namespace is supplied by the connector.

        Existing bound acquisitions cannot be promoted by a later caller label.
        Unclassified inputs are admitted only under the host's acquisition trust.
        """
        self._scope(evidence_class,adapter)
        if extraction.receipt.evidence_class not in {'unspecified',evidence_class}:
            raise ContractError('acquisition evidence provenance cannot be relabeled')
        extraction=replace(extraction,receipt=replace(extraction.receipt,evidence_class=evidence_class))
        receipt=extraction.receipt
        with self._connect() as c:
            c.execute('BEGIN IMMEDIATE')
            if evidence_class!='synthetic_fixture':
                # A caller may retain an unbound original Extraction after its
                # trusted acquisition. Known synthetic bytes remain synthetic,
                # even if redelivered under a new source alias.
                synthetic=c.execute('SELECT body FROM source_state WHERE tenant=? AND evidence_class=?',
                                    (receipt.tenant_id,'synthetic_fixture')).fetchall()
                for (body,) in synthetic:
                    known,_=self._decode(body,'synthetic_fixture')
                    if any(set(old.raw_hashes)&set(receipt.raw_hashes) for old in known.receipts):
                        raise ContractError('known synthetic acquisition provenance cannot be promoted')
            row=c.execute('SELECT adapter,body FROM source_state WHERE tenant=? AND evidence_class=? AND source_id=?',
                          (receipt.tenant_id,evidence_class,receipt.source_id)).fetchone()
            if row:
                if row[0]!=adapter:raise ValueError('source adapter cannot change within an acquisition identity')
                ledger,existing=self._decode(row[1],evidence_class)
            else:
                ledger=SourceLedger(receipt.tenant_id);existing=()
            retained=ledger.activate(extraction,semantics)
            merged=list(existing)
            for item in coverage:
                if item.source_id!=receipt.source_id or item.generation_id not in (None,receipt.generation_id):
                    raise ValueError('coverage must belong to its acquisition generation')
                bound=replace(item,generation_id=receipt.generation_id,
                              known_at=max(item.known_at,receipt.fetched_at))
                # Redelivery of an identical fact preserves first visibility;
                # changes to state/maturity/version append a new fact.
                semantic=lambda x:(x.source_id,x.start,x.end,x.state,x.maturity,x.version,x.generation_id)
                same_partition=[old for old in merged if (old.source_id,old.start,old.end,old.generation_id)==(bound.source_id,bound.start,bound.end,bound.generation_id)]
                latest=max(same_partition,key=lambda old:old.known_at) if same_partition else None
                if latest is not None and latest.known_at==bound.known_at and semantic(latest)!=semantic(bound):
                    raise ValueError('conflicting coverage evidence at same acquisition time')
                if latest is None or semantic(latest)!=semantic(bound):merged.append(bound)
            body=canonical_json({'schema_version':'1.0','ledger':ledger.to_dict(),'coverage':tuple(merged)})
            c.execute('INSERT INTO source_state(tenant,evidence_class,source_id,adapter,body) VALUES(?,?,?,?,?) '
                      'ON CONFLICT(tenant,evidence_class,source_id) DO UPDATE SET body=excluded.body',
                      (receipt.tenant_id,evidence_class,receipt.source_id,adapter,body))
        return retained

    def load(self,tenant,source_id,*,evidence_class,adapter):
        self._scope(evidence_class,adapter)
        with self._connect() as c:
            row=c.execute('SELECT adapter,body FROM source_state WHERE tenant=? AND evidence_class=? AND source_id=?',
                          (tenant,evidence_class,source_id)).fetchone()
        if row is None:raise PermissionError('no acquired source in this tenant/evidence namespace')
        if row[0]!=adapter:raise ValueError('source adapter mismatch')
        ledger,coverage=self._decode(row[1],evidence_class)
        if ledger.tenant_id!=tenant:raise PermissionError('source tenant mismatch')
        return ledger,coverage
