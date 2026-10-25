# Dependency and license inventory

Runtime core has no third-party dependencies. The optional numerical extra is pinned; no model weights or external forecasting services are distributed. License metadata was read from the installed distributions used for verification. This is an inventory, not a legal opinion.

| Package | Verified version | License metadata/classifiers |
|---|---|---|
| numpy | 1.26.4 | OSI Approved :: BSD License |
| scipy | 1.13.1 | OSI Approved :: BSD License |
| scikit-learn | 1.6.1 | OSI Approved :: BSD License |
| joblib | 1.5.3 | BSD-3-Clause |
| threadpoolctl | 3.6.0 | OSI Approved :: BSD License |
| pytest | 8.4.2 | OSI Approved :: MIT License |
| setuptools | 58.0.4 | OSI Approved :: MIT License |

NumPy/SciPy binary distributions include additional BLAS/compiler/runtime notices. Preserve their complete installed notices when redistributing binaries. scikit-learn uses BSD-3-Clause. joblib 1.5.3 metadata declares BSD-3-Clause; threadpoolctl BSD-3-Clause; pytest MIT. No proprietary checkpoint license is assumed.

Standard isolated build backend: setuptools 80.9.0 (pinned, not downloaded in this sandbox). Verified offline compatibility build: installed setuptools 58.0.4 with `setup.py`, using `pip install --no-build-isolation --no-deps .`. Dependencies were already installed; external PyPI resolution failed due network DNS restrictions.
