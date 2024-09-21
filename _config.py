from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///re-feed.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['RSS_FEED_URL'] = ''
app.config['JSON_FEED_URL'] = ''
app.config['FETCH_MODE'] = 'json'
app.config['RSS_PUBLISHED_AT_FORMAT'] = '%a, %d %b %Y %H:%M:%S %z'
app.config['JSON_PUBLISHED_AT_FORMAT'] = '%Y-%m-%d %H:%M:%S'
app.config['SECRET_KEY'] = 'sfksdfkjseeir-4r5fsdf-unffs3ksf'
app.config['FEED_TITLE'] = 'My Feed'
app.config['LOGO'] = None
app.config['FOOTER_LOGO'] = None

# Load custom config if it exists
try:
    from config import *  # noqa

    app.config.from_object('config')
except ImportError:
    pass

db = SQLAlchemy(app)
