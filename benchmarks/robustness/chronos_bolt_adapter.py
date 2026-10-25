"""Genuine pinned Chronos-Bolt Tiny adapter; no synthetic/model fallback.

Optional research runtime only. load() acquires official public artifacts using
normal HTTPS when absent, verifies pretrained weight bytes, then loads locally.
Set FORECASTING_CHRONOS_CACHE to an isolated writable cache directory.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import time
from urllib.request import urlopen

CHECKPOINT = 'amazon/chronos-bolt-tiny'
REVISION = 'a0e552de83495b5c28c14c71c374f3e33280b340'
WEIGHT_SHA256 = '75068728d376d2bec670379eeef4bfb4d24c0cfe24d957451f8d19b447030a32'
WEIGHT_BYTES = 34622352
# Exact JSON semantics transcribed from official pinned config. Config byte hash
# is recorded separately because JSON whitespace is not a model parameter.
EXPECTED_CONFIG = {
    '_name_or_path':'autogluon/chronos-bolt-tiny',
    'architectures':['ChronosBoltModelForForecasting'],
    'chronos_config':{'context_length':2048, 'input_patch_size':16,
        'input_patch_stride':16, 'prediction_length':64,
        'quantiles':[.1,.2,.3,.4,.5,.6,.7,.8,.9], 'use_reg_token':True},
    'chronos_pipeline_class':'ChronosBoltPipeline', 'classifier_dropout':0.0,
    'd_ff':1024, 'd_kv':64, 'd_model':256, 'decoder_start_token_id':0,
    'dense_act_fn':'relu', 'dropout_rate':0.1, 'eos_token_id':1,
    'feed_forward_proj':'relu', 'initializer_factor':0.05,
    'is_encoder_decoder':True, 'is_gated_act':False, 'layer_norm_epsilon':1e-6,
    'model_type':'t5', 'n_positions':512, 'num_decoder_layers':4, 'num_heads':4,
    'num_layers':4, 'pad_token_id':0, 'reg_token_id':1,
    'relative_attention_max_distance':128, 'relative_attention_num_buckets':32,
    'torch_dtype':'float32', 'transformers_version':'4.39.3', 'use_cache':True,
    'vocab_size':2,
}
DEPENDENCIES = ('chronos-forecasting', 'torch', 'transformers', 'accelerate',
                'numpy', 'einops', 'scikit-learn', 'safetensors', 'huggingface-hub')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def acquire(cache):
    """Download only official revision-pinned artifacts, without user credentials."""
    cache.mkdir(parents=True, exist_ok=True)
    elapsed = time.perf_counter()
    for filename, limit in (('config.json', 65536), ('model.safetensors', WEIGHT_BYTES)):
        destination = cache / filename
        if not destination.is_file():
            url = f'https://huggingface.co/{CHECKPOINT}/resolve/{REVISION}/{filename}'
            with urlopen(url, timeout=60) as response:
                payload = response.read(limit + 1)
            if len(payload) > limit:
                raise ValueError(f'{filename} exceeds expected byte limit')
            if filename == 'model.safetensors' and (
                    len(payload) != WEIGHT_BYTES or
                    hashlib.sha256(payload).hexdigest() != WEIGHT_SHA256):
                raise ValueError('official pretrained weight bytes/hash mismatch')
            temporary = destination.with_suffix(destination.suffix + '.partial')
            temporary.write_bytes(payload)
            temporary.replace(destination)
    weights = cache / 'model.safetensors'
    if weights.stat().st_size != WEIGHT_BYTES or digest(weights) != WEIGHT_SHA256:
        raise ValueError('cached pretrained weight bytes/hash mismatch')
    config = json.loads((cache / 'config.json').read_text())
    if config != EXPECTED_CONFIG:
        raise ValueError('configuration does not match official pinned JSON semantics')
    return time.perf_counter() - elapsed


def load():
    # Import errors remain load failures and cannot admit a replacement callable.
    import torch
    from chronos import BaseChronosPipeline

    dependency_versions = {name: importlib.metadata.version(name) for name in DEPENDENCIES}
    if dependency_versions['chronos-forecasting'] != '2.2.2':
        raise ValueError('adapter is specified for chronos-forecasting==2.2.2')
    cache = Path(os.environ.get('FORECASTING_CHRONOS_CACHE',
                 str(Path.home() / '.cache' / 'forecasting-benchmark' / REVISION)))
    acquisition_seconds = acquire(cache)
    torch.manual_seed(0)
    torch.set_num_threads(2)
    started = time.perf_counter()
    pipeline = BaseChronosPipeline.from_pretrained(str(cache), device_map='cpu',
        torch_dtype=torch.float32, local_files_only=True)
    pipeline.model.eval()
    model_load_seconds = time.perf_counter() - started

    def predict(prefix, horizon):
        if not isinstance(horizon, int) or not 1 <= horizon <= 64:
            raise ValueError('horizon must be an integer within native64-step output')
        if not prefix or len(prefix) > 2048 or any(
                not math.isfinite(float(x)) or float(x) < 0 for x in prefix):
            raise ValueError('finite nonnegative nonempty context<=2048 required')
        with torch.inference_mode():
            quantiles = pipeline.predict(torch.tensor(prefix, dtype=torch.float32),
                                         prediction_length=horizon)
        if tuple(quantiles.shape) != (1, 9, horizon):
            raise ValueError('unexpected pretrained output shape')
        path = tuple(float(x) for x in quantiles[0, 4].tolist())
        if any(not math.isfinite(x) for x in path):
            raise ValueError('nonfinite pretrained forecast')
        return tuple(max(0.0, x) for x in path)

    metadata = dict(checkpoint=CHECKPOINT, revision=REVISION,
        weights_sha256={'model.safetensors':WEIGHT_SHA256},
        config_sha256=digest(cache / 'config.json'), dependencies=dependency_versions,
        point_statistic='per-bin marginal median (q0.5); sum is a point aggregate, not cumulative median or mean',
        projection='clip_nonnegative per-bin after native-scale prediction',
        device='cpu', dtype='float32', cpu_threads=2, seed=0,
        license='Apache-2.0', weight_bytes=WEIGHT_BYTES,
        acquisition_seconds=acquisition_seconds, model_load_seconds=model_load_seconds,
        source_url=f'https://huggingface.co/{CHECKPOINT}/blob/{REVISION}/model.safetensors',
        calibration='none', pretraining_contamination='unknown for public serving trace')
    return predict, metadata
