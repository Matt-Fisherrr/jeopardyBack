from flask import current_app as app
from pathlib import Path
from importlib import import_module

p = Path('./files/routes')

# Gets paths, removes .py from the end and joins them on . for import format
routes = [x for x in list(p.glob('**/*.py')) if x.parts[-1] != '__init__.py']
routes_no_py =  ['.'.join(list(x.parts[:-1]) + list(x.parts[-1].split('.py')))[:-1] for x in routes]

# Loops through all the files found and imports them
with app.app_context():
    for route in routes_no_py:
        import_module(route)