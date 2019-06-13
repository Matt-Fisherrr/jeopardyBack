import psycopg2, os
from .auth import Auth

class global_variables():
    def __init__(self):
        self.auth = Auth()
        self.room_list = {}
        self.connected_users = {}
        self.conn = psycopg2.connect(os.environ['DATABASE_URL'])
        self.cur = self.conn.cursor()
        self.req_ids = {}
        self.jwks = self.auth.get_jwks()