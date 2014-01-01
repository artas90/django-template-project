import os
import json
from contextlib import contextmanager
from fabric.operations import local as fab_local, sudo, env
from fabric.context_managers import lcd, prefix, cd, settings
from fabric.utils import abort


__all__ = [
    'init_virtualenv',
    'create_virtualenv',
    'update_virtualenv',

    'deploy',

    'start',
    'stop',
    'restart',
    'status',

    'make_messages',
    'compile_messages',

    'developer',
    'prod',
    'generate_config_files',
]


PROJECT_NAME = 'ProjectName'
PROJECT_PREFIX = 'PN'
SITE_DIR = os.path.dirname(__file__)
SOURCE_DIR = os.path.join(SITE_DIR, 'source')
MANAGE_PY = os.path.join(SITE_DIR, 'manage.py')
VIRTUALENV_DIR = os.path.join(SITE_DIR, 'var', 'virtualenv')
VIRTUALENV_BIN = os.path.join(VIRTUALENV_DIR, PROJECT_NAME, 'bin')
VIRTUALENV_ACTIVATE = '. {}'.format(os.path.join(VIRTUALENV_BIN, 'activate'))
SUPERVISOR_CONFIG = os.path.join(SITE_DIR, 'conf', 'supervisord.conf')


def create_virtualenv():
    """
    Create empty virtualenv in var/virtualenv folder
    """
    with lcd(SITE_DIR):
        if not os.path.isdir(VIRTUALENV_DIR):
            os.mkdir(VIRTUALENV_DIR)

    with lcd(VIRTUALENV_DIR):
        fab_local('virtualenv --no-site-packages {}'.format(PROJECT_NAME))


def update_virtualenv():
    """
    Install/update project requirements
    """
    with lcd(SITE_DIR):
        print "Clean pyc/pyo"

        fab_local("find . -name '*.pyc' -delete")
        fab_local("find . -name '*.pyo' -delete")

        with prefix(VIRTUALENV_ACTIVATE):
            fab_local('pip install -r requirements.txt')


def init_virtualenv():
    """
    Create virtualenv and install requirements
    """
    create_virtualenv()
    update_virtualenv()


def deploy():
    """
    Deploy/re-deploy the project
    """
    with lcd(SITE_DIR):
        fab_local('git pull')
        with prefix(VIRTUALENV_ACTIVATE):
            fab_local('pip install -r requirements.txt')
            fab_local('python manage.py syncdb --migrate')
            fab_local('python manage.py collectstatic --noinput')
    restart()

#==== Supervisor helper functions ====

@contextmanager
def _supervisor_started():
    with lcd(SITE_DIR):
        if not os.path.exists(os.path.join(SITE_DIR, 'var', 'run', 'supervisord.pid')):
            fab_local('supervisord -c {}'.format(SUPERVISOR_CONFIG))
        yield


def restart(app='all'):
    """
    Usage: fab restart[:app_name]
    """
    with _supervisor_started():
        fab_local('supervisorctl -c {} restart {}'.format(SUPERVISOR_CONFIG, app))


def start(app='all'):
    """
    Usage: fab start[:app_name]
    """
    with _supervisor_started():
        fab_local('supervisorctl -c {} start {}'.format(SUPERVISOR_CONFIG, app))


def stop(app='all'):
    """
    Usage: fab stop[:app_name]
    """
    with _supervisor_started():
        fab_local('supervisorctl -c {} stop {}'.format(SUPERVISOR_CONFIG, app))


def status():
    """
    Usage: fab status
    """
    with _supervisor_started():
        fab_local('supervisorctl -c {} status'.format(SUPERVISOR_CONFIG))


#==== Localization functions ====

class _LocalizationCommand(object):

    def __init__(self, cmd):
        self.cmd = cmd

    def __call__(self, app_name, locale):
        with lcd(SITE_DIR), prefix(VIRTUALENV_ACTIVATE):
            self.applications = json.loads(fab_local('python manage.py get_application_paths', capture=True))

        if app_name.lower() == '__all__':
            for app in self.applications:
                self._process_app(app, locale)
            return

        if app_name not in self.applications:
            abort("Application '{}' not found".format(app_name))

        self._process_app(app_name, locale)

    def _process_app(self, app_path, locale):
        app_path = self.applications[app_path]
        locale_dir = os.path.join(app_path, 'locale')

        if not os.path.isdir(locale_dir):
            os.mkdir(locale_dir)

        if locale.lower() == '__all__':
            for locale_ in os.listdir(locale_dir):
                 if os.path.isdir(os.path.join(locale_dir, locale_)):
                    self._process_locale(app_path, locale_)
            return

        self._process_locale(app_path, locale)

    def _process_locale(self, app_path, locale):
        with lcd(app_path):
            print "Process '{}' ".format(app_path)
            fab_local('python {} {} -l {}'.format(MANAGE_PY, self.cmd, locale))

make_messages = _LocalizationCommand('makemessages')
make_messages.__doc__ = 'Usage: fab makemessages:(app_name or __all__),(locale or __all__)'
compile_messages = _LocalizationCommand('compilemessages')
compile_messages.__doc__ = 'Usage: fab compilemessages:(app_name or __all__),(locale or __all__)'


#==== Tools for generating configs ====

SETTINGS_PROFILES = {
    'developer': {
        'GUNICORN_NAME': '{}_DEVELOPER'.format(PROJECT_PREFIX),
        'GUNICORN_PORT': 16150,
        'GUNICORN_WORKERS': 1,
    },
    'prod': {
        'GUNICORN_NAME': '{}_PROD'.format(PROJECT_PREFIX),
        'GUNICORN_PORT': 16151,
        'GUNICORN_WORKERS': 2,
    },
}


def developer():
    """
    Activate developer configs
    """
    os.environ["FAB_SETTINGS_PROFILE"] = 'developer'


def prod():
    """
    Activate production configs
    """
    os.environ["FAB_SETTINGS_PROFILE"] = 'prod'


def _get_profile():
    profile = os.environ.get("FAB_SETTINGS_PROFILE")
    if not profile:
        abort('\nUsage:\n    fab developer|prod command')
    return profile


def _sample(*args):
    return os.path.join(SITE_DIR, 'conf', 'sample', *args)


def _conf(*args):
    return os.path.join(SITE_DIR, 'conf', *args)


def generate_config_files():
    """
    Generate config for supervisor, gunicorn and nginx
    """

    profile_name = _get_profile()
    profile = SETTINGS_PROFILES[profile_name]

    site_domain = ''
    while not site_domain:
        site_domain = raw_input('Enter domain of your site (ex.: site.com): ')

    config_files = [
        (_sample('nginx_sample.conf'), _conf('_nginx_semanticdesk_{}.conf'.format(profile_name))),
        (_sample('supervisord_sample.conf'), _conf('supervisord.conf')),
        (_sample('gunicorn_conf_sample.py'), _conf('gunicorn_conf.py')),
    ]

    for input, output in config_files:
        with open(input) as f_in, open(output, 'w') as f_out:

            output_data = f_in.read()
            output_data = output_data.replace('{{ SITE_DIR }}', SITE_DIR)
            output_data = output_data.replace('{{ PROFILE }}', profile_name)
            output_data = output_data.replace('{{ GUNICORN_NAME }}', profile['GUNICORN_NAME'])
            output_data = output_data.replace('{{ GUNICORN_PORT }}', unicode(profile['GUNICORN_PORT']))
            output_data = output_data.replace('{{ GUNICORN_WORKERS }}', unicode(profile['GUNICORN_WORKERS']))
            output_data = output_data.replace('{{ VIRTUALENV_BIN }}', VIRTUALENV_BIN)
            output_data = output_data.replace('{{ SITE_DOMAIN }}', site_domain)

            # TODO: Check if file already exists
            f_out.write(output_data)

            print "File '{}' was generated".format(output)