from flask import Flask, request, jsonify, _request_ctx_stack
from flask_cors import cross_origin, CORS
from flask_socketio import SocketIO, Namespace, emit, join_room, leave_room, close_room, rooms, disconnect
from jose import jwt
from six.moves.urllib.request import urlopen
from functools import wraps
import json, psycopg2, os, hashlib

conn = psycopg2.connect(dbname=os.environ['DBNAME'], user=os.environ['USER'], password=os.environ['PASSWORD'], host=os.environ['HOST'])
cur = conn.cursor()

app = Flask(__name__)
# CORS(app)

AUTH0_DOMAIN = 'dev-0fw6q03t.auth0.com'
API_AUDIENCE = 'localhost'
ALGORITHMS = ["RS256"]
jwks = json.loads(urlopen("https://"+AUTH0_DOMAIN + "/.well-known/jwks.json").read())
SALT = '8616b99be2344c82ad77f24977eac12e'.encode('utf-8')

room_list = [{
    'name':'name',
    'ping_time':'time',
    'players':{
        'count':3,
        'one':{
            'name':'auth_0 code',
            'score':0,
            'ping':72
        },
        'two':{
            'name':'auth_0 code',
            'score':0,
            'ping':73
        },
        'thee':{
            'name':'auth_0 code',
            'score':0,
            'ping':74
        }
    },
    'viewers':['auth_0 code','auth_0 code','auth_0 code','auth_0 code']
}]

class AuthError(Exception):
    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code


@app.errorhandler(AuthError)
def handle_auth_error(ex):
    response = jsonify(ex.error)
    response.status_code = ex.status_code
    return response


def get_token_auth_header():
    """Obtains the access token from the Authorization Header
    """
    auth = request.headers.get("Authorization", None)
    if not auth:
        raise AuthError({"code": "authorization_header_missing",
                         "description":
                         "Authorization header is expected"}, 401)

    parts = auth.split()

    if parts[0].lower() != "bearer":
        raise AuthError({"code": "invalid_header",
                         "description":
                         "Authorization header must start with"
                         " Bearer"}, 401)
    elif len(parts) == 1:
        raise AuthError({"code": "invalid_header",
                         "description": "Token not found"}, 401)
    elif len(parts) > 2:
        raise AuthError({"code": "invalid_header",
                         "description":
                         "Authorization header must be"
                         " Bearer token"}, 401)

    token = parts[1]
    return token


def requires_auth(f):
    """Determines if the access token is valid
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token_auth_header()
        jsonurl = urlopen("https://"+AUTH0_DOMAIN+"/.well-known/jwks.json")
        jwks = json.loads(jsonurl.read())
        unverified_header = jwt.get_unverified_header(token)
        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
        if rsa_key:
            try:
                payload = jwt.decode(
                    token,
                    rsa_key,
                    algorithms=ALGORITHMS,
                    audience=API_AUDIENCE,
                    issuer="https://"+AUTH0_DOMAIN+"/"
                )
            except jwt.ExpiredSignatureError:
                raise AuthError({"code": "token_expired",
                                 "description": "token is expired"}, 401)
            except jwt.JWTClaimsError:
                raise AuthError({"code": "invalid_claims",
                                 "description":
                                 "incorrect claims,"
                                 "please check the audience and issuer"}, 401)
            except Exception:
                raise AuthError({"code": "invalid_header",
                                 "description":
                                 "Unable to parse authentication"
                                 " token."}, 400)

            _request_ctx_stack.top.current_user = payload
            return f(*args, **kwargs)
        raise AuthError({"code": "invalid_header",
                         "description": "Unable to find appropriate key"}, 400)
    return decorated


def requires_scope(required_scope):
    """Determines if the required scope is present in the Access Token
    Args:
        required_scope (str): The scope required to access the resource
    """
    token = get_token_auth_header()
    unverified_claims = jwt.get_unverified_claims(token)
    if unverified_claims.get("scope"):
        token_scopes = unverified_claims["scope"].split()
        for token_scope in token_scopes:
            if token_scope == required_scope:
                return True
    return False


@app.route('/api/connect', methods=['POST'])
@cross_origin(headers=['Content-Type', 'Authorization'])
@requires_auth
def connect():
    global jwks, ALGORITHMS, SALT
    id_token = request.get_json()['IDToken']
    access_token = get_token_auth_header()
    id_decode = jwt.decode(id_token, jwks, algorithms=ALGORITHMS, audience="3eCEPx9I6Wr0N3FIJAwXXi5caFdRfZzV", access_token=access_token)
    hashed_id = str(hashlib.sha512(id_decode['sub'].encode('utf-8') + SALT).hexdigest())
    cur.execute("SELECT username FROM players WHERE auth0_sub = %s", (hashed_id,))
    username = cur.fetchone()
    if username == None:
        return jsonify({'response': 'username'})
    return jsonify({'response': True, 'username': username})


@app.route('/api/connect/reg', methods=['POST'])
@cross_origin(headers=['Content-Type', 'Authorization'])
@requires_auth
def set_username():
    global jwks, ALGORITHMS, SALT
    id_token = request.get_json()['IDToken']
    username = request.get_json()['user']
    access_token = get_token_auth_header()
    id_decode = jwt.decode(id_token, jwks, algorithms=ALGORITHMS, audience="3eCEPx9I6Wr0N3FIJAwXXi5caFdRfZzV", access_token=access_token)
    hashed_id = str(hashlib.sha512(id_decode['sub'].encode('utf-8') + SALT).hexdigest())
    cur.execute("SELECT count(auth0_sub) FROM players WHERE auth0_sub = %s", (hashed_id,))
    if cur.fetchone()[0] == '0':
        cur.execute("INSERT INTO players(username, auth0_sub) VALUES (%s, %s)", (username, hashed_id))
    else:
        cur.execute("UPDATE players SET username = %s WHERE auth0_sub = %s", (username, hashed_id))
    conn.commit()
    return jsonify({'response': True, 'username': username})


@app.route('/api/roomlist', methods=['GET'])
@cross_origin(headers=['Content-Type', 'Authorization'])
@requires_auth
def get_room_list():
    global room_list
    return jsonify(room_list)

class jeopardy_socket(Namespace):
    def on_connect(self):
        pass
    
    def on_disconnect(self):
        pass

if __name__ == '__main__':
    app.run(debug=True)
    # ,host= '0.0.0.0'
