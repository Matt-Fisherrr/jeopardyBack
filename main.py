from flask import Flask, request, jsonify, _request_ctx_stack
from flask_cors import cross_origin, CORS
from flask_socketio import SocketIO, Namespace, emit, join_room, leave_room, close_room, rooms, disconnect
from jose import jwt
from six.moves.urllib.request import urlopen
from functools import wraps
import json, psycopg2, os, hashlib, requests, random

conn = psycopg2.connect(dbname=os.environ['DBNAME'], user=os.environ['USER'], password=os.environ['PASSWORD'], host=os.environ['HOST'])
cur = conn.cursor()

app = Flask(__name__)
# CORS(app)

AUTH0_DOMAIN = 'dev-0fw6q03t.auth0.com'
API_AUDIENCE = 'localhost'
ALGORITHMS = ["RS256"]
jwks = json.loads(urlopen("https://"+AUTH0_DOMAIN + "/.well-known/jwks.json").read())
SALT = '8616b99be2344c82ad77f24977eac12e'.encode('utf-8')

connected_users = {}

room_list = {}

# Room list format
# 1:{
# 'name':'name',
# 'room_id':1,
# 'ping_time':'time',
# 'players':{
#     'count':3,
#     'one':{
#         'name':'auth_0 code',
#         'score':0,
#         'ping':72
#     },
#     'two':{
#         'name':'auth_0 code',
#         'score':0,
#         'ping':73
#     },
#     'thee':{
#         'name':'auth_0 code',
#         'score':0,
#         'ping':74
#     }
# },
# 'viewers':['auth_0 code','auth_0 code','auth_0 code','auth_0 code']
# }

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
    global jwks, ALGORITHMS, SALT, connected_users
    id_token = request.get_json()['IDToken']
    access_token = get_token_auth_header()
    id_decode = jwt.decode(id_token, jwks, algorithms=ALGORITHMS, audience="3eCEPx9I6Wr0N3FIJAwXXi5caFdRfZzV", access_token=access_token)
    hashed_id = str(hashlib.sha512(id_decode['sub'].encode('utf-8') + SALT).hexdigest())
    cur.execute("SELECT username FROM players WHERE auth0_sub = %s", (hashed_id,))
    username = cur.fetchone()
    connected_users[access_token] = {'access_token':access_token, 'id_token':id_token, 'auth0_code':hashed_id, 'username':username}
    if username == None:
        return jsonify({'response': 'username'})
    return jsonify({'response': True, 'username': username})


@app.route('/api/connect/reg', methods=['POST'])
@cross_origin(headers=['Content-Type', 'Authorization'])
@requires_auth
def set_username():
    global jwks, ALGORITHMS, SALT, connected_users
    access_token = get_token_auth_header()
    username = request.get_json()['user']
    cur.execute("SELECT count(auth0_sub) FROM players WHERE auth0_sub = %s", (connected_users[access_token]['auth0_code'],))
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO players(username, auth0_sub) VALUES (%s, %s)", (username, connected_users[access_token]['auth0_code']))
        print('that')
    else:
        cur.execute("UPDATE players SET username = %s WHERE auth0_sub = %s", (username, connected_users[access_token]['auth0_code']))
    conn.commit()
    return jsonify({'response': True, 'username': username})

@app.route('/api/roomlist', methods=['GET'])
@cross_origin(headers=['Content-Type', 'Authorization'])
@requires_auth
def get_room_list():
    global room_list, connected_users
    access_token = get_token_auth_header()
    rooms = []
    for room in room_list:
        rooms.append({'name':room_list[room]['name'], 'id':room_list[room]['room_id'], 'players':room_list[room]['players']['count']})
    cur.execute("SELECT room_name, room_id, player1, player2, player3 FROM rooms WHERE player1 = %s AND complete = 'False'",(connected_users[access_token]['username'],))
    for room in cur.fetchall():
        rooms.append({'name':room[0], 'id':room[1], 'players':'started'})
    return jsonify(rooms)

@app.route('/api/roomlist/create', methods=['POST'])
@cross_origin(headers=['Content-Type', 'Authorization'])
@requires_auth
def make_room():
    global room_list, connected_users
    room_name = request.get_json()['roomName']
    access_token = get_token_auth_header()
    # values = [200, 400, 600, 800, 1000]
    # board = {}
    # while len(board) < 5:
    #     category = requests.get(f'http://jservice.io/api/categories?count=1&offset={random.randint(1,18400)}').json()[0]
    #     holderList = []
    #     for value in values:
    #         r = requests.get(f'http://jservice.io/api/clues?category={category["id"]}&value={value}').json()
    #         try:
    #             holderList.append(r[0])
    #         except:
    #             break
    #     if len(holderList) == 5:
    #         board[category['title']] = holderList
    # print(board)
    board = {'hairy it': [{'id': 82119, 'answer': 'an anteater', 'question': 'Seen here, this mammal is all mouth & no teeth', 'value': 200, 'airdate': '2006-11-03T12:00:00.000Z', 'created_at': '2014-02-11T23:40:34.632Z', 'updated_at': '2014-02-11T23:40:34.632Z', 'category_id': 10797, 'game_id': None, 'invalid_count': None, 'category': {'id': 10797, 'title': 'hairy it', 'created_at': '2014-02-11T23:40:34.430Z', 'updated_at': '2014-02-11T23:40:34.430Z', 'clues_count': 5}}, {'id': 82125, 'answer': 'a skunk', 'question': "This small mammal, Mephitis mephitis, can spray musk accurately as far as 12 feet (& it ain't the Jovan kind)", 'value': 400, 'airdate': '2006-11-03T12:00:00.000Z', 'created_at': '2014-02-11T23:40:34.800Z', 'updated_at': '2014-02-11T23:40:34.800Z', 'category_id': 10797, 'game_id': None, 'invalid_count': None, 'category': {'id': 10797, 'title': 'hairy it', 'created_at': '2014-02-11T23:40:34.430Z', 'updated_at': '2014-02-11T23:40:34.430Z', 'clues_count': 5}}, {'id': 82131, 'answer': 'a guinea pig', 'question': 'You think you can experiment with a clue like it was some kind of this rodent, seen here?', 'value': 600, 'airdate': '2006-11-03T12:00:00.000Z', 'created_at': '2014-02-11T23:40:34.964Z', 'updated_at': '2014-02-11T23:40:34.964Z', 'category_id': 10797, 'game_id': None, 'invalid_count': None, 'category': {'id': 10797, 'title': 'hairy it', 'created_at': '2014-02-11T23:40:34.430Z', 'updated_at': '2014-02-11T23:40:34.430Z', 'clues_count': 5}}, {'id': 82137, 'answer': 'a gorilla', 'question': 'There are 3 kinds of this animal: western lowland, eastern lowland & mountain', 'value': 800, 'airdate': '2006-11-03T12:00:00.000Z', 'created_at': '2014-02-11T23:40:35.128Z', 'updated_at': '2014-02-11T23:40:35.128Z', 'category_id': 10797, 'game_id': None, 'invalid_count': None, 'category': {'id': 10797, 'title': 'hairy it', 'created_at': '2014-02-11T23:40:34.430Z', 'updated_at': '2014-02-11T23:40:34.430Z', 'clues_count': 5}}, {'id': 82143, 'answer': 'a bighorn sheep', 'question': 'This species seen here is found only in North America', 'value': 1000, 'airdate': '2006-11-03T12:00:00.000Z', 'created_at': '2014-02-11T23:40:35.292Z', 'updated_at': '2014-02-11T23:40:35.292Z', 'category_id': 10797, 'game_id': None, 'invalid_count': None, 'category': {'id': 10797, 'title': 'hairy it', 'created_at': '2014-02-11T23:40:34.430Z', 'updated_at': '2014-02-11T23:40:34.430Z', 'clues_count': 5}}], 'mixing apples & oranges': [{'id': 107828, 'answer': 'William Tell', 'question': 'An apple & a crossbow play important roles in this 1804 Schiller tale', 'value': 200, 'airdate': '2010-10-04T12:00:00.000Z', 'created_at': '2014-02-14T02:14:40.567Z', 'updated_at': '2014-02-14T02:14:40.567Z', 'category_id': 14598, 'game_id': None, 'invalid_count': None, 'category': {'id': 14598, 'title': 'mixing apples & oranges', 'created_at': '2014-02-14T02:14:40.342Z', 'updated_at': '2014-02-14T02:14:40.342Z', 'clues_count': 5}}, {'id': 107834, 'answer': 'Agent Orange', 'question': 'This 2-word Vietnam War item consisted of 2 weedkillers--2,4-D & 2,4,5-T', 'value': 400, 'airdate': '2010-10-04T12:00:00.000Z', 'created_at': '2014-02-14T02:14:40.815Z', 'updated_at': '2014-02-14T02:14:40.815Z', 'category_id': 14598, 'game_id': None, 'invalid_count': None, 'category': {'id': 14598, 'title': 'mixing apples & oranges', 'created_at': '2014-02-14T02:14:40.342Z', 'updated_at': '2014-02-14T02:14:40.342Z', 'clues_count': 5}}, {'id': 107840, 'answer': 'mistletoe', 'question': 'The European type of this holiday plant seen here grows most often on apple trees', 'value': 600, 'airdate': '2010-10-04T12:00:00.000Z', 'created_at': '2014-02-14T02:14:41.097Z', 'updated_at': '2014-02-14T02:14:41.097Z', 'category_id': 14598, 'game_id': None, 'invalid_count': None, 'category': {'id': 14598, 'title': 'mixing apples & oranges', 'created_at': '2014-02-14T02:14:40.342Z', 'updated_at': '2014-02-14T02:14:40.342Z', 'clues_count': 5}}, {'id': 107846, 'answer': 'Tasmania', 'question': 'Have a devil of a time in this smallest state in Australia, often called the Apple Isle', 'value': 800, 'airdate': '2010-10-04T12:00:00.000Z', 'created_at': '2014-02-14T02:14:41.395Z', 'updated_at': '2014-02-14T02:14:41.395Z', 'category_id': 14598, 'game_id': None, 'invalid_count': None, 'category': {'id': 14598, 'title': 'mixing apples & oranges', 'created_at': '2014-02-14T02:14:40.342Z', 'updated_at': '2014-02-14T02:14:40.342Z', 'clues_count': 5}}, {'id': 107852, 'answer': 'the Orange Bowl Stadium', 'question': 'This Florida sports & concert venue was demolished in 2008', 'value': 1000, 'airdate': '2010-10-04T12:00:00.000Z', 'created_at': '2014-02-14T02:14:41.685Z', 'updated_at': '2014-02-14T02:14:41.685Z', 'category_id': 14598, 'game_id': None, 'invalid_count': None, 'category': {'id': 14598, 'title': 'mixing apples & oranges', 'created_at': '2014-02-14T02:14:40.342Z', 'updated_at': '2014-02-14T02:14:40.342Z', 'clues_count': 5}}], '"it" is a 7-letter word': [{'id': 92049, 'answer': 'brevity', 'question': 'Proverbially, this "is the soul of wit"', 'value': 200, 'airdate': '2008-12-31T12:00:00.000Z', 'created_at': '2014-02-14T01:57:40.927Z', 'updated_at': '2014-02-14T01:57:40.927Z', 'category_id': 12204, 'game_id': None, 'invalid_count': None, 'category': {'id': 12204, 'title': '"it" is a 7-letter word', 'created_at': '2014-02-14T01:57:40.721Z', 'updated_at': '2014-02-14T01:57:40.721Z', 'clues_count': 5}}, {'id': 92055, 'answer': 'a citizen', 'question': 'A native or naturalized member of a state or nation', 'value': 400, 'airdate': '2008-12-31T12:00:00.000Z', 'created_at': '2014-02-14T01:57:41.139Z', 'updated_at': '2014-02-14T01:57:41.139Z', 'category_id': 12204, 'game_id': None, 'invalid_count': None, 'category': {'id': 12204, 'title': '"it" is a 7-letter word', 'created_at': '2014-02-14T01:57:40.721Z', 'updated_at': '2014-02-14T01:57:40.721Z', 'clues_count': 5}}, {'id': 92061, 'answer': 'a blitzer', 'question': "A marauding linebacker, or CNN's Wolf", 'value': 600, 'airdate': '2008-12-31T12:00:00.000Z', 'created_at': '2014-02-14T01:57:41.353Z', 'updated_at': '2014-02-14T01:57:41.353Z', 'category_id': 12204, 'game_id': None, 'invalid_count': None, 'category': {'id': 12204, 'title': '"it" is a 7-letter word', 'created_at': '2014-02-14T01:57:40.721Z', 'updated_at': '2014-02-14T01:57:40.721Z', 'clues_count': 5}}, {'id': 92067, 'answer': 'an epitaph', 'question': 'A notable one of these read, "Here lies Ann Mann, who lived an old maid but died an old Mann"', 'value': 800, 'airdate': '2008-12-31T12:00:00.000Z', 'created_at': '2014-02-14T01:57:41.556Z', 'updated_at': '2014-02-14T01:57:41.556Z', 'category_id': 12204, 'game_id': None, 'invalid_count': None, 'category': {'id': 12204, 'title': '"it" is a 7-letter word', 'created_at': '2014-02-14T01:57:40.721Z', 'updated_at': '2014-02-14T01:57:40.721Z', 'clues_count': 5}}, {'id': 92073, 'answer': 'the Kitchen Cabinet', 'question': 'Nickname of Andrew Jackson\'s informal "cabinet", which included Martin Van Buren', 'value': 1000, 'airdate': '2008-12-31T12:00:00.000Z', 'created_at': '2014-02-14T01:57:41.801Z', 'updated_at': '2014-02-14T01:57:41.801Z', 'category_id': 12204, 'game_id': None, 'invalid_count': None, 'category': {'id': 12204, 'title': '"it" is a 7-letter word', 'created_at': '2014-02-14T01:57:40.721Z', 'updated_at': '2014-02-14T01:57:40.721Z', 'clues_count': 5}}], 'behind the songs': [{'id': 110677, 'answer': '"Hey There Delilah"', 'question': "Tom Higgenson's flirtation with a girl in New York & a promise to write her a song led to this megahit for the Plain White T's", 'value': 200, 'airdate': '2012-04-16T12:00:00.000Z', 'created_at': '2014-02-14T02:40:53.156Z', 'updated_at': '2014-02-14T02:40:53.156Z', 'category_id': 15025, 'game_id': None, 'invalid_count': None, 'category': {'id': 15025, 'title': 'behind the songs', 'created_at': '2014-02-14T02:40:52.987Z', 'updated_at': '2014-02-14T02:40:52.987Z', 'clues_count': 10}}, {'id': 110683, 'answer': 'Chicago', 'question': "It was a Saturday in the park--Central Park--that inspired Robert Lamm to write this group's first gold single", 'value': 400, 'airdate': '2012-04-16T12:00:00.000Z', 'created_at': '2014-02-14T02:40:53.354Z', 'updated_at': '2014-02-14T02:40:53.354Z', 'category_id': 15025, 'game_id': None, 'invalid_count': None, 'category': {'id': 15025, 'title': 'behind the songs', 'created_at': '2014-02-14T02:40:52.987Z', 'updated_at': '2014-02-14T02:40:52.987Z', 'clues_count': 10}}, {'id': 110689, 'answer': 'Clint Black', 'question': 'This country singer wrote "When I Said I Do" for wife Lisa Hartman, who then recorded the song with him as a duet', 'value': 600, 'airdate': '2012-04-16T12:00:00.000Z', 'created_at': '2014-02-14T02:40:53.554Z', 'updated_at': '2014-02-14T02:40:53.554Z', 'category_id': 15025, 'game_id': None, 'invalid_count': None, 'category': {'id': 15025, 'title': 'behind the songs', 'created_at': '2014-02-14T02:40:52.987Z', 'updated_at': '2014-02-14T02:40:52.987Z', 'clues_count': 10}}, {'id': 110695, 'answer': '"(Don\\\'t Fear) The Reaper"', 'question': "Blue Oyster Cult's Buck Dharma wrote this song after pondering about dying young & whether loved ones are reunited", 'value': 800, 'airdate': '2012-04-16T12:00:00.000Z', 'created_at': '2014-02-14T02:40:53.755Z', 'updated_at': '2014-02-14T02:40:53.755Z', 'category_id': 15025, 'game_id': None, 'invalid_count': None, 'category': {'id': 15025, 'title': 'behind the songs', 'created_at': '2014-02-14T02:40:52.987Z', 'updated_at': '2014-02-14T02:40:52.987Z', 'clues_count': 10}}, {'id': 110701, 'answer': 'Chris Isaak', 'question': 'A girl who he knew was trouble called & said she was coming over; he wrote "Wicked Game" by the time she got there', 'value': 1000, 'airdate': '2012-04-16T12:00:00.000Z', 'created_at': '2014-02-14T02:40:54.029Z', 'updated_at': '2014-02-14T02:40:54.029Z', 'category_id': 15025, 'game_id': None, 'invalid_count': None, 'category': {'id': 15025, 'title': 'behind the songs', 'created_at': '2014-02-14T02:40:52.987Z', 'updated_at': '2014-02-14T02:40:52.987Z', 'clues_count': 10}}], 'hidden': [{'id': 57336, 'answer': 'camouflage', 'question': 'From the French for "to disguise", soldiers wear this to conceal themselves from the enemy', 'value': 200, 'airdate': '2002-09-30T12:00:00.000Z', 'created_at': '2014-02-11T23:21:40.162Z', 'updated_at': '2014-02-11T23:21:40.162Z', 'category_id': 7318, 'game_id': None, 'invalid_count': None, 'category': {'id': 7318, 'title': 'hidden', 'created_at': '2014-02-11T23:21:40.068Z', 'updated_at': '2014-02-11T23:21:40.068Z', 'clues_count': 5}}, {'id': 57342, 'answer': 'invisible ink', 'question': 'If your junior spy kit has run out of this, lemon juice can be substituted', 'value': 400, 'airdate': '2002-09-30T12:00:00.000Z', 'created_at': '2014-02-11T23:21:40.325Z', 'updated_at': '2014-02-11T23:21:40.325Z', 'category_id': 7318, 'game_id': None, 'invalid_count': None, 'category': {'id': 7318, 'title': 'hidden', 'created_at': '2014-02-11T23:21:40.068Z', 'updated_at': '2014-02-11T23:21:40.068Z', 'clues_count': 5}}, {'id': 57348, 'answer': 'Easter eggs', 'question': 'Hidden features on DVDs are known as these "holiday" items', 'value': 600, 'airdate': '2002-09-30T12:00:00.000Z', 'created_at': '2014-02-11T23:21:40.481Z', 'updated_at': '2014-02-11T23:21:40.481Z', 'category_id': 7318, 'game_id': None, 'invalid_count': None, 'category': {'id': 7318, 'title': 'hidden', 'created_at': '2014-02-11T23:21:40.068Z', 'updated_at': '2014-02-11T23:21:40.068Z', 'clues_count': 5}}, {'id': 57354, 'answer': 'subliminal advertisements', 'question': 'In 1962 a Louisiana company got a patent for a device that added these to motion pictures in theaters', 'value': 800, 'airdate': '2002-09-30T12:00:00.000Z', 'created_at': '2014-02-11T23:21:40.638Z', 'updated_at': '2014-02-11T23:21:40.638Z', 'category_id': 7318, 'game_id': None, 'invalid_count': None, 'category': {'id': 7318, 'title': 'hidden', 'created_at': '2014-02-11T23:21:40.068Z', 'updated_at': '2014-02-11T23:21:40.068Z', 'clues_count': 5}}, {'id': 57360, 'answer': 'agenda', 'question': 'Latin for "things to be done", you have to watch out for a person\'s hidden one', 'value': 1000, 'airdate': '2002-09-30T12:00:00.000Z', 'created_at': '2014-02-11T23:21:40.791Z', 'updated_at': '2014-02-11T23:21:40.791Z', 'category_id': 7318, 'game_id': None, 'invalid_count': None, 'category': {'id': 7318, 'title': 'hidden', 'created_at': '2014-02-11T23:21:40.068Z', 'updated_at': '2014-02-11T23:21:40.068Z', 'clues_count': 5}}]}
    new_board = {}
    for key in board:
        new_board[key] = []
        for arr in board[key]:
            new_board[key].append({'id':arr['id'], 'value':arr['value'], 'question':arr['question'], 'answered':False})
    cur.execute("INSERT INTO rooms(room_name, board, player1, complete) VALUES (%s,%s,%s, 'False')",(room_name,json.dumps(new_board),connected_users[access_token]['username']))
    cur.execute('SELECT room_id FROM rooms WHERE room_name = %s',(room_name,))
    room_id = cur.fetchone()[0]
    room_list[room_id] = {
        'name':room_name,
        'room_id':room_id,
        'ping_time':'time',
        'board':new_board,
        'players':{
            'count':1,
            'one':{
                'name':connected_users[access_token]['username'],
                'score':0,
                'ping':0
            },
            'two':{
                'name':'',
                'score':0,
                'ping':0
            },
            'thee':{
                'name':'',
                'score':0,
                'ping':0
            }
        },
    'viewers':[]
    }

    return jsonify({"room_id":room_id})

@app.route('/api/roomlist/getboard', methods=['GET'])
@cross_origin(headers=['Content-Type', 'Authorization'])
@requires_auth
def get_board():
    global room_list, connected_users
    room_id = request.headers['room_id']
    try:
        board = room_list[room_id]['board']
    except:
        cur.execute("SELECT board FROM rooms WHERE room_id = %s",(room_id,))
        board = json.loads(cur.fetchone()[0])
        # Add adding the board to room_list
    return jsonify({'board':board})

class jeopardy_socket(Namespace):
    def on_connect(self):
        pass
    
    def on_disconnect(self):
        pass

if __name__ == '__main__':
    app.run(debug=True)
    # ,host= '0.0.0.0'
