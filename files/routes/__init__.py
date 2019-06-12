from flask import current_app as app

with app.app_context():
    import files.routes.base
    import files.routes.api.connect.base
    import files.routes.api.connect.reg
    import files.routes.api.roomlist.base
    import files.routes.api.roomlist.create
    import files.routes.api.roomlist.getboard