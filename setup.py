# import multiprocessing to avoid this bug (http://bugs.python.org/issue15881#msg170215)
import multiprocessing
assert multiprocessing
import re
from setuptools import setup, find_packages


def get_version():
    """
    Extracts the version number from the version.py file.
    """
    VERSION_FILE = 'ambition_utils/version.py'
    mo = re.search(r'^__version__ = [\'"]([^\'"]*)[\'"]', open(VERSION_FILE, 'rt').read(), re.M)
    if mo:
        return mo.group(1)
    else:
        raise RuntimeError('Unable to find version string in {0}.'.format(VERSION_FILE))


install_requires = [
    'ambition-django-timezone-field>=2.0.1',
    'Django>=1.11',
    'pandas>=0.21.0',
    'python-dateutil>=2.4.2',
    'fleming>=0.4.6',
    'django-manager-utils>=0.13.1',
    'pytz>=2015.6',
    'six',
    'tdigest',
    'celery',
]

tests_require = [
    'django-nose>=1.4',
    'django-dynamic-fixture',
    'freezegun',
    'mock',
    'psycopg2',
    'coverage',
]


setup(
    name='ambition-utils',
    version=get_version(),
    description='Various utility packages used across Ambition projects.',
    long_description=open('README.rst').read(),
    url='https://github.com/ambitioninc/ambition-utils',
    author='Wes Okes',
    author_email='wes.okes@gmail.com',
    keywords='django, database, query, sql, postgres, upsert',
    packages=find_packages(),
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Framework :: Django',
        'Framework :: Django :: 1.11',
        'Framework :: Django :: 2.0',
    ],
    license='MIT',
    install_requires=install_requires,
    tests_require=tests_require,
    extras_require={'dev': tests_require},
    test_suite='run_tests.run_tests',
    include_package_data=True,
)
