# Copyright 2018 MakeMyTrip (Paritosh Anand)
#
# This file is part of edge.
#
# edge is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# edge is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with dataShark.  If not, see <http://www.gnu.org/licenses/>.

"""
Django settings for edge project.

Generated by 'django-admin startproject' using Django 1.11.1.

For more information on this file, see
https://docs.djangoproject.com/en/1.11/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.11/ref/settings/
"""

import datetime
import os

import ldap
from django_auth_ldap.config import GroupOfNamesType, LDAPSearch

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.11/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'kv&d-(91_butn6c!^qxpqy^c^#zy$28bj5p148#$^c^uctwd2e'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["x.x.x.x"]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'space',
    'simple_history',
    'orchestration',
    'report'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
]

ROOT_URLCONF = 'edge.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

LOGIN_URL = '/space/login/'
LOGOUT_URL = '/space/logout/'

ADMIN_SITE_HEADER = 'Edge Admin'

SITE_URL = '/'

WSGI_APPLICATION = 'edge.wsgi.application'

# Database
# https://docs.djangoproject.com/en/1.11/ref/settings/#databases

# Temp fix for mysql gone away issue.
DB_WAIT_TIMEOUT = 2 * 60 * 60

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'edge',
        'USER': os.environ.get('EDGE_MYSQL_USER'),
        'PASSWORD': os.environ.get('EDGE_MYSQL_PASSWORD'),
        'HOST': os.environ.get('EDGE_MYSQL'),
        'PORT': '',
        'OPTIONS': {
            'init_command' : 'set wait_timeout=%d' % DB_WAIT_TIMEOUT
        },
    }
}

# LDAP Vars

AUTH_LDAP_SERVER_URI = "<AUTH_LDAP_SERVER_URI>"
AUTH_LDAP_BIND_DN = "<AUTH_LDAP_BIND_DN>"
AUTH_LDAP_BIND_PASSWORD = "<AUTH_LDAP_BIND_PASSWORD>"
LDAP_BASE_DN = "<LDAP_BASE_DN>"
searchFilter="(&(objectClass=person)(sAMAccountName=%(user)s))"
ldap.set_option(ldap.OPT_REFERRALS, 0)

AUTH_LDAP_USER_SEARCH = LDAPSearch(LDAP_BASE_DN, ldap.SCOPE_SUBTREE, searchFilter)
AUTH_LDAP_GROUP_SEARCH = LDAPSearch(LDAP_BASE_DN, ldap.SCOPE_SUBTREE, "(objectClass=groupOfNames)")

AUTH_LDAP_GROUP_TYPE = GroupOfNamesType()
AUTH_LDAP_USER_ATTR_MAP = {"first_name": "givenName", "last_name": "sn", "email": "mail"}

AUTH_LDAP_USER_FLAGS_BY_GROUP = {
    "is_active": [],
    "is_staff": [],
    "is_superuser": []
}

AUTH_LDAP_CACHE_GROUPS = True
AUTH_LDAP_GROUP_CACHE_TIMEOUT = 3600

# Authentication
AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'auth_request.myLdapAuth.LDAPBackend1',
)

# Session Timeout
SESSION_COOKIE_AGE = 43200

# Password validation
# https://docs.djangoproject.com/en/1.11/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/1.11/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.11/howto/static-files/

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]

LOG_DIR = os.path.join(BASE_DIR, "logs")

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
            'datefmt':'%d/%b/%Y %H:%M:%S'
        },
    },
    'handlers': {
        'null': {
            'level': 'DEBUG',
            'class': 'logging.NullHandler',
        },
        'logfile': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR + "/edge.log",
            'maxBytes': 1024*1024*50,         # 50 MB
            'backupCount': 10,
            'formatter': 'standard',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR + "/console.log",
            'maxBytes': 1024*1024*50,         # 50 MB
            'backupCount': 5,
            'formatter': 'standard'
        },
    },
    'loggers': {
        'space': {
            'handlers': ['logfile'],
            'level': 'DEBUG',
        },
        'auth_request': {
            'handlers': ['logfile'],
            'level': 'DEBUG',
        },
        'orchestration': {
            'handlers': ['logfile'],
            'level': 'DEBUG',
        },
        'orchestration.utils.lb': {
            'handlers': ['logfile'],
            'level': 'DEBUG',
        },
        'report': {
            'handlers': ['logfile'],
            'level': 'DEBUG',
        },
        'django.requests': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'ERROR',
        },
        'django.server': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'django.template': {
            'handlers': ['console'],
            'level': 'ERROR',
        },
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'edge_cache',
        'TIMEOUT': 259200,   # 72*60*60 seconds ~= 3 days
        'OPTIONS': {
            'MAX_ENTRIES': 6000
        }
    }
}

RABBIT_MQ=os.environ.get('RABBIT_MQ')
CELERY_BROKER_URL='amqp://edge:edge@' + RABBIT_MQ + '//edge'
CELERY_RESULT_BACKEND = 'amqp'
CELERY_TASK_RESULT_EXPIRES = 300
# CELERY_DEBUG=False

FABRIC_USER_PASSWORD = os.environ.get('FABRIC_USER_PASSWORD')
FABRIC_SSH_CONFIG_PATH = os.environ.get('FABRIC_SSH_CONFIG_PATH', os.path.join(BASE_DIR, '.ssh_config'))
FABRIC_WHITE_LIST = ['rm -rf /opt/', 'wget', 'tar', 'mkdir', 'md5sum', 'hostname', 'chown', 'chmod', '/opt/', 'cd /opt/', 'ps' , 'pkill', 'cp /opt/', '/etc/init.d/', 'rm -f /opt/', 'ls', 'find', 'systemctl', 'kafka', 'uptime', 'docker', 'grep', 'cat', 'service', 'systemctl', 'sh /opt/', 'kill','netstat']

EMAIL_FROM = 'edge@makemytrip.com'
EMAIL_HOST = os.environ.get('EMAIL_HOST')
