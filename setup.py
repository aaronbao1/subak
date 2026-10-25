"""Compatibility shim for offline builds with older installed setuptools.

Standard isolated builds use the pinned backend in pyproject.toml.
"""
from setuptools import find_packages, setup

setup(name='evidence-forecasting',version='0.1.0',
      description='Versioned, evidence-bound enterprise cost forecasting reference implementation',
      python_requires='>=3.9',packages=find_packages('src'),package_dir={'':'src'},
      entry_points={'console_scripts':['forecasting=forecasting.cli:main']},
      extras_require={
          'models':['numpy==1.26.4','scipy==1.13.1','scikit-learn==1.6.1','joblib==1.5.3','threadpoolctl==3.6.0'],
          'test':['pytest==8.4.2'],
      })
