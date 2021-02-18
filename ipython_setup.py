from atat.app import make_config, make_app

app = make_app(make_config())
ctx = app.app_context()
ctx.push()

print(
    "\nWelcome to atat. This shell has all models in scope, and a SQLAlchemy session called db."
)
