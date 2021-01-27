from flask_debugtoolbar import DebugToolbarExtension


def setup_debug_toolbar(app, enviroment_name: str):
    """
    Setup Flask debug toolbar.
    
    Sets application attributes and creates the debugging toolbar for
    the application.
    """
    toolbar = None

    is_development = enviroment_name in ["dev", "development"]
    is_dev_tool = str(app.config["DEV_DEBUG_TOOL"]).lower() == "true"

    if is_development and is_dev_tool:
        # The toolbar is only enabled in debug mode
        app.debug = True
        # Toolbar factory instance can be use to configure functionality later
        toolbar = DebugToolbarExtension(app)

    return toolbar
