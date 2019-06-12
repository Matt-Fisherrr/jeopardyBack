import psycopg2, os
from .auth import Auth

class global_variables():
    def __init__(self):
        self.auth = Auth()
        self.room_list = {}
        self.connected_users = {}
        self.conn = psycopg2.connect(dbname=os.environ['DBNAME'], user=os.environ['USER'], password=os.environ['PASSWORD'], host=os.environ['HOST'])
        self.cur = self.conn.cursor()
        self.req_ids = {}
        self.jwks = self.auth.get_jwks()