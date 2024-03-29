import os
import json

import sys
from django.conf import settings


def configure_settings():
    """
    Configures settings for manage.py and for run_tests.py.
    """
    if not settings.configured:
        # Determine the database settings depending on if a test_db var is set in CI mode or not
        test_db = os.environ.get('DB', None)
        if test_db is None:
            db_config = {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': 'ambition_utils',
                'USER': 'postgres',
                'PASSWORD': '',
                'HOST': 'db',
            }
        elif test_db == 'postgres':
            db_config = {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': 'ambition_utils',
                'USER': 'postgres',
                'PASSWORD': '',
                'HOST': 'db',
            }
        else:
            raise RuntimeError('Unsupported test DB {0}'.format(test_db))

        # Check env for db override (used for github actions)
        if os.environ.get('DB_SETTINGS'):
            db_config = json.loads(os.environ.get('DB_SETTINGS'))

        settings.configure(
            TEST_RUNNER='django_nose.NoseTestSuiteRunner',
            SECRET_KEY='*',
            DEFAULT_AUTO_FIELD='django.db.models.AutoField',
            NOSE_ARGS=['--nocapture', '--nologcapture', '--verbosity=1'],
            DATABASES={
                'default': db_config,
            },
            DEBUG=False,
            INSTALLED_APPS=(
                'django.contrib.auth',
                'django.contrib.contenttypes',
                'ambition_utils',
                'ambition_utils.tests',
                'ambition_utils.activity',
                'ambition_utils.anomaly',
                'ambition_utils.anomaly.tests',
                'ambition_utils.postgres_lock',
                'ambition_utils.rrule',
                'ambition_utils.rrule.tests',
            ),
            LOGGING={
                'version': 1,
                'disable_existing_loggers': False,
                'filters': {
                    'require_debug_false': {
                        '()': 'django.utils.log.RequireDebugFalse'
                    }
                },
                'formatters': {
                    'standard': {
                        'format': '[%(asctime)s %(levelname)s] %(name)s:%(lineno)d \'%(message)s\'',
                    }
                },
                'handlers': {
                    'console': {
                        'level': 'DEBUG',
                        'class': 'logging.StreamHandler',
                        'stream': sys.stdout,
                        'formatter': 'standard'
                    }
                },
                'loggers': {
                    'ambition_utils': {
                        'handlers': ['console'],
                        'level': 'DEBUG',
                        'propagate': True
                    },
                }
            },
            ROOT_URLCONF='ambition_utils.urls',
            TIME_ZONE='UTC',
            USE_TZ=False,
            USE_DEPRECATED_PYTZ=True,
            MIDDLEWARE=[],
            TEMPLATES=[
                {
                    'BACKEND': 'django.template.backends.django.DjangoTemplates',
                }
            ]
        )
