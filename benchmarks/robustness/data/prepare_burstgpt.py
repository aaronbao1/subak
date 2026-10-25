#!/usr/bin/env python3
"""Reproduce canonical native-hour token series from immutable public BurstGPT CSV.

Acquire URL/blob pinned in burstgpt_input_provenance.json through an authorized
public download, then: python3 prepare_burstgpt.py /path/to/BurstGPT_1.csv OUTDIR
No network operations, rescaling, invented dates, identities or prices.
"""
import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

RAW_SHA256 = '46fc9480ef0b748ecb2b51d512ff08c196b031782cbe6f78e28044d768e86d5a'
EXPECTED_COLUMNS = ['Timestamp', 'Model', 'Request tokens', 'Response tokens', 'Total tokens', 'Log Type']
EXPECTED = {
    'burstgpt_hourly_tokens.csv': 'e1c6a70ace64a8265982e6843248e0cce6113f20c6179ecd0e1624176ea6b888',
    'burstgpt_hourly_input_tokens.csv': '501f1f40c880ee38bc97b73ad5f15f9bd1d42866357edb55e9e5f396d13858de',
    'burstgpt_hourly_components.csv': '7c131661210b089b58b092550473a4941939fb683abfa8f0806af8c904e9c79f',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw_csv', type=Path)
    parser.add_argument('output_dir', type=Path)
    args = parser.parse_args()
    raw = args.raw_csv.read_bytes()
    if hashlib.sha256(raw).hexdigest() != RAW_SHA256:
        raise ValueError('Raw bytes do not match pinned source SHA256; do not mix revisions')
    bins = defaultdict(lambda: [0, 0, 0, 0])
    low, high, rows, failed = float('inf'), float('-inf'), 0, 0
    with args.raw_csv.open(newline='') as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != EXPECTED_COLUMNS:
            raise ValueError('Actual immutable asset schema changed')
        for row in reader:
            t = int(row['Timestamp'])
            a, b, c = (int(row[key]) for key in EXPECTED_COLUMNS[2:5])
            if min(t, a, b, c) < 0 or a + b != c:
                raise ValueError('Invalid token row or failed input/output identity')
            low, high = min(low, t), max(high, t)
            value = bins[t // 3600 * 3600]
            for i, quantity in enumerate((a, b, c, 1)):
                value[i] += quantity
            rows += 1
            failed += b == 0
    # Conservative edges: retain only hours strictly interior to trace bounds.
    start, end = ((low + 3599) // 3600) * 3600, (high // 3600) * 3600
    contents = {
        'burstgpt_hourly_tokens.csv': 'bin_start_seconds,total_tokens\n',
        'burstgpt_hourly_input_tokens.csv': 'bin_start_seconds,total_tokens\n',
        'burstgpt_hourly_components.csv': 'bin_start_seconds,input_tokens,output_tokens,total_tokens,request_count\n',
    }
    empty = 0
    for t in range(start, end, 3600):
        a, b, c, count = bins[t]
        empty += count == 0
        contents['burstgpt_hourly_tokens.csv'] += f'{t},{c}\n'
        contents['burstgpt_hourly_input_tokens.csv'] += f'{t},{a}\n'
        contents['burstgpt_hourly_components.csv'] += f'{t},{a},{b},{c},{count}\n'
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, text in contents.items():
        data = text.encode()
        checksum = hashlib.sha256(data).hexdigest()
        if checksum != EXPECTED[name]:
            raise ValueError(f'Reproduction mismatch for {name}: {checksum}')
        (args.output_dir / name).write_bytes(data)
    print(json.dumps({'rows': rows, 'zero_response_rows': failed, 'min_timestamp': low,
                      'max_timestamp': high, 'empty_interior_bins': empty,
                      'canonical_bins': (end-start)//3600, 'sha256': EXPECTED}, indent=2))


if __name__ == '__main__':
    main()
