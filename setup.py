#!/usr/bin/env python3
"""
Setup script for JIRA Update Hook.
"""

from setuptools import setup, find_packages
import os
import re

# Read version from __init__.py
with open(os.path.join('src', 'jira_update', '__init__.py'), 'r') as f:
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", f.read(), re.M)
    if version_match:
        version = version_match.group(1)
    else:
        version = '0.1.0'

# Read long description from README.md
with open('README.md', 'r') as f:
    long_description = f.read()

setup(
    name='jira-update',
    version=version,
    description='A Git hook system that analyzes code changes and updates JIRA tickets',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Your Name',
    author_email='your.email@example.com',
    url='https://github.com/yourusername/jira-update',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=[
        'jira>=3.5.0',
        'gitpython>=3.1.30',
        'pyyaml>=6.0',
        'python-dotenv>=1.0.0',
        'requests>=2.31.0',
        'colorama>=0.4.6',
        'pygments>=2.16.0',
        'keyring>=24.0.0',
    ],
    extras_require={
        'ai': ['openai>=1.0.0'],
    },
    entry_points={
        'console_scripts': [
            'jira-update=jira_update.main:main',
            'jira-update-install=install_hook:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Software Development :: Version Control :: Git',
    ],
    python_requires='>=3.8',
) 