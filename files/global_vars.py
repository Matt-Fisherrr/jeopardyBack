from .auth import Auth
import psycopg2, os

auth = Auth()
room_list = {}
connected_users = {}
conn = psycopg2.connect(dbname=os.environ['DBNAME'], user=os.environ['USER'], password=os.environ['PASSWORD'], host=os.environ['HOST'])
cur = conn.cursor()
req_ids = {}
jwks = auth.get_jwks()