#!/bin/bash
python3 -m venv /tmp/build-venv
/tmp/build-venv/bin/pip install -r requirements.txt
/tmp/build-venv/bin/python manage.py migrate --noinput
/tmp/build-venv/bin/python manage.py seed_templates
/tmp/build-venv/bin/python manage.py create_crm_user
/tmp/build-venv/bin/python manage.py collectstatic --noinput --clear
