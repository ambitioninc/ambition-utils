import os

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
                'ENGINE': 'django.db.backends.postgresql_psycopg2',
                'NAME': 'ambition',
                'USER': 'ambition',
                'PASSWORD': 'ambition',
                'HOST': 'db'
            }
        elif test_db == 'postgres':
            db_config = {
                'ENGINE': 'django.db.backends.postgresql_psycopg2',
                'USER': 'postgres',
                'NAME': 'ambition_utils',
            }
        else:
            raise RuntimeError('Unsupported test DB {0}'.format(test_db))

        settings.configure(
            TEST_RUNNER='django_nose.NoseTestSuiteRunner',
            NOSE_ARGS=['--nocapture', '--nologcapture', '--verbosity=1'],
            MIDDLEWARE_CLASSES=(),
            DATABASES={
                'default': db_config,
                'mock-second-database': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'TEST_MIRROR': 'default',
                },
            },
            INSTALLED_APPS=(
                'django.contrib.auth',
                'django.contrib.contenttypes',
                'ambition_utils',
                'ambition_utils.tests',
                'ambition_utils.activity',
                'ambition_utils.anomaly',
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
            TEMPLATES=[
                {
                    'BACKEND': 'django.template.backends.django.DjangoTemplates',
                }
            ]
        )
