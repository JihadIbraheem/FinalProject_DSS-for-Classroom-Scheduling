from flask import Flask
from app.auth import auth_blueprint
from app.schedule import schedule_blueprint
from config.db_config import db_config

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Database configuration
app.config['DB_CONFIG'] = db_config

# Register Blueprints
app.register_blueprint(auth_blueprint, url_prefix='/auth')
app.register_blueprint(schedule_blueprint, url_prefix='/schedule')

if __name__ == '__main__':
    app.run(debug=True)