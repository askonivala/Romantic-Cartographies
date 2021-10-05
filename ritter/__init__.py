from flask import Flask
import secrets

app = Flask(__name__)
secret_key = secrets.token_urlsafe(16)
app.secret_key = secret_key

from ritter import routes
from ritter import admin

if __name__ == '__main__':
    app.run()
