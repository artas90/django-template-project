Skeleton for django project
===========================

Typical django project structure polished by years.

Setup guide
-----------

1. Init python virtualenv:

    `$ fab init_virtualenv`

2. Copy sample file contains settings for this intallation and fill it:

    `$ cp conf/settings/local.py.sample conf/settings/local.py`
    
3. Activate virtualenv:

    `$ . var/virtualenv/ProjectName/bin/activate`

4. Run site:

    `$ python manage.py runserver`
