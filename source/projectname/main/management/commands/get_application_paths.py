# -*- coding: utf-8 -*-
import os
import sys
import json
from django.core.management import BaseCommand, CommandError
from django.db.models import get_apps

class Command(BaseCommand):

    def handle(self, *args, **options):
        if len(args) > 0:
            raise CommandError('Command takes no arguments (%s given)' % len(args))

        app_dict = {}

        for app_module in get_apps():
            app_name =  app_module.__name__

            if app_name.startswith('projectname.'):
                dir_, file_ = os.path.split(app_module.__file__)

                if file_.startswith('__init__'):
                    dir_ = os.path.join(dir_, '..')

                app_short_name = app_name.split('.')[-2] # app_name ends with '.models'
                app_dict[app_short_name] = dir_

        sys.stdout.write(json.dumps(app_dict, indent=4))
