from flask import Flask, request, jsonify, _request_ctx_stack, render_template, send_from_directory
from flask_cors import cross_origin, CORS
from flask_socketio import SocketIO, Namespace, emit, join_room, leave_room, close_room, rooms, disconnect
from threading import Lock
from jose import jwt
from six.moves.urllib.request import urlopen
from functools import wraps
from fuzzywuzzy import fuzz
import json, psycopg2, os, hashlib, requests, random, datetime, copy, re

conn = psycopg2.connect(dbname=os.environ['DBNAME'], user=os.environ['USER'], password=os.environ['PASSWORD'], host=os.environ['HOST'])
cur = conn.cursor()

app = Flask(__name__, static_folder="build/static", template_folder="build")
socketio = SocketIO(app, async_mode='eventlet')
# CORS(app)

AUTH0_DOMAIN = 'dev-0fw6q03t.auth0.com'
API_AUDIENCE = 'localhost'
ALGORITHMS = ["RS256"]
jwks = json.loads(urlopen("https://"+AUTH0_DOMAIN + "/.well-known/jwks.json").read())
SALT = '8616b99be2344c82ad77f24977eac12e'.encode('utf-8')

connected_users = {}

room_list = {}
ping_list = {}
numbers = ['zero', 'one', 'two', 'three']

thread = None
thread_lock = Lock()
thread_lock_back = Lock()
thread_lock_buzz = Lock()
thread_answer_timer = Lock()

# Room list format
room_template = {
    'name':'',
    'room_id':0,
    'board': {},
    'selected_board':'',
    'answer_count':0,
    'active_player':0,
    'started':0,
    'selected_time':None,
    'screen_clicked':'',
    'buzzedIn':0,
    'buzz_background':None,
    'buzzed_in_back':None,
    'answer_timer':None,
    'buzzable_players':[],
    'buzzedPlayerTimes':{
        'one':'',
        'two':'',
        'three':''
    },
    'players':{
        'count':0,
        'total_count':0,
        'ready_count':0,
        'one':{
            'auth0_code':'',
            'score':0,
            'ping':0,
            'ready':False
        },
        'two':{
            'auth0_code':'',
            'score':0,
            'ping':0,
            'ready':False
        },
        'thee':{
            'auth0_code':'',
            'score':0,
            'ping':0,
            'ready':False
        }
    },
    'viewers':[]
}

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

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def index(path):
    if path == 'favicon.ico':
        return send_from_directory('build/',path)
    return render_template('index.html')
    # return "<h1>hi</h1>"

@app.route('/api/connect', methods=['POST'])
@cross_origin(headers=['Content-Type', 'Authorization'])
@requires_auth
def connect():
    global jwks, ALGORITHMS, SALT, connected_users
    id_token = request.get_json()['IDToken']
    access_token = get_token_auth_header()
    id_decode = jwt.decode(id_token, jwks, algorithms=ALGORITHMS, audience="3eCEPx9I6Wr0N3FIJAwXXi5caFdRfZzV", access_token=access_token)
    hashed_id = str(hashlib.sha512(id_decode['sub'].encode('utf-8') + SALT).hexdigest())
    cur.execute("SELECT username FROM players WHERE auth0_code = %s", (hashed_id,))
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
    cur.execute("SELECT count(auth0_code) FROM players WHERE auth0_code = %s", (connected_users[access_token]['auth0_code'],))
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO players(username, auth0_code) VALUES (%s, %s)", (username, connected_users[access_token]['auth0_code']))
    else:
        cur.execute("UPDATE players SET username = %s WHERE auth0_code = %s", (username, connected_users[access_token]['auth0_code']))
    connected_users[access_token]['username'] = (username,) # toupled because it's how it's sent from SQL and I didn't notice until too far in
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
        rooms.append({'name':room_list[room]['name'], 'id':room_list[room]['room_id'], 'players':'started' if room_list[room]['started'] else room_list[room]['players']['total_count'], 'old':False })
    cur.execute("SELECT room_name, room_id, player1, player2, player3, started FROM rooms WHERE player1 = %s AND complete = 0",(connected_users[access_token]['auth0_code'],))
    for room in cur.fetchall():
        if room[1] not in list(room_list.keys()):
            rooms.append({'name':room[0], 'id':room[1], 'players':'started' if room[5] == 1 else len([p for p in room[2:4] if p != None]), 'old':True })
    return jsonify(rooms)

@app.route('/api/roomlist/create', methods=['POST'])
@cross_origin(headers=['Content-Type', 'Authorization'])
@requires_auth
def make_room():
    global room_list, connected_users, room_template
    room_name = request.get_json()['roomName']
    access_token = get_token_auth_header()
    
    values = [200, 400, 600, 800, 1000]
    board = {}
    while len(board) < 5:
        category = requests.get(f'http://jservice.io/api/categories?count=1&offset={random.randint(1,18400)}').json()[0]
        holderList = []
        for value in values:
            r = requests.get(f'http://jservice.io/api/clues?category={category["id"]}&value={value}').json()
            try:
                holderList.append(r[0])
            except:
                break
        if len(holderList) == 5:
            board[category['title']] = holderList
        print(board.keys())
    new_board = {}
    for key in board:
        new_board[re.sub(r'[^A-Za-z]','',key)] = []
        for arr in board[key]:
            new_board[re.sub(r'[^A-Za-z]','',key)].append({'category':key, 'id':arr['id'], 'value':arr['value'], 'question':arr['question'], 'answer':arr['answer'], 'answered':False})
    
    # new_board = {'hairyit': [{'category': 'test column', 'id': 82119, 'value': 200, 'question': 'Italics test', 'answer': '<i>an anteater</i>', 'answered': False}, {'category': 'hairy it', 'id': 82125, 'value': 400, 'question': "woman / women", 'answer': 'a women', 'answered': False}, {'category': 'hairy it', 'id': 82131, 'value': 600, 'question': 'data / datum', 'answer': 'the datum', 'answered': False}, {'category': 'hairy it', 'id': 82137, 'value': 800, 'question': 'Millennia / mellennium', 'answer': 'a millennium', 'answered': False}, {'category': 'hairy it', 'id': 82143, 'value': 1000, 'question': 'Opera / opus', 'answer': 'an opus', 'answered': False}], 'mixingapplesoranges': [{'category': 'mixing apples & oranges', 'id': 107828, 'value': 200, 'question': 'An apple & a crossbow play important roles in this 1804 Schiller tale', 'answer': 'William Tell', 'answered': False}, {'category': 'mixing apples & oranges', 'id': 107834, 'value': 400, 'question': 'This 2-word Vietnam War item consisted of 2 weedkillers--2,4-D & 2,4,5-T', 'answer': 'Agent Orange', 'answered': False}, {'category': 'mixing apples & oranges', 'id': 107840, 'value': 600, 'question': 'The European type of this holiday plant seen here grows most often on apple trees', 'answer': 'mistletoe', 'answered': False}, {'category': 'mixing apples & oranges', 'id': 107846, 'value': 800, 'question': 'Have a devil of a time in this smallest state in Australia, often called the Apple Isle', 'answer': 'Tasmania', 'answered': False}, {'category': 'mixing apples & oranges', 'id': 107852, 'value': 1000, 'question': 'This Florida sports & concert venue was demolished in 2008', 'answer': 'the Orange Bowl Stadium', 'answered': False}], 'itisaletterword': [{'category': '"it" is a 7-letter word', 'id': 92049, 'value': 200, 'question': 'Proverbially, this "is the soul of wit"', 'answer': 'brevity', 'answered': False}, {'category': '"it" is a 7-letter word', 'id': 92055, 'value': 400, 'question': 'A native or naturalized member of a state or nation', 'answer': 'a citizen', 'answered': False}, {'category': '"it" is a 7-letter word', 'id': 92061, 'value': 600, 'question': "A marauding linebacker, or CNN's Wolf", 'answer': 'a blitzer', 'answered': False}, {'category': '"it" is a 7-letter word', 'id': 92067, 'value': 800, 'question': 'A notable one of these read, "Here lies Ann Mann, who lived an old maid but died an old Mann"', 'answer': 'an epitaph', 'answered': False}, {'category': '"it" is a 7-letter word', 'id': 92073, 'value': 1000, 'question': 'Nickname of Andrew Jackson\'s informal "cabinet", which included Martin Van Buren', 'answer': 'the Kitchen Cabinet', 'answered': False}], 'behindthesongs': [{'category': 'behind the songs', 'id': 110677, 'value': 200, 'question': "Tom Higgenson's flirtation with a girl in New York & a promise to write her a song led to this megahit for the Plain White T's", 'answer': '"Hey There Delilah"', 'answered': False}, {'category': 'behind the songs', 'id': 110683, 'value': 400, 'question': "It was a Saturday in the park--Central Park--that inspired Robert Lamm to write this group's first gold single", 'answer': 'Chicago', 'answered': False}, {'category': 'behind the songs', 'id': 110689, 'value': 600, 'question': 'This country singer wrote "When I Said I Do" for wife Lisa Hartman, who then recorded the song with him as a duet', 'answer': 'Clint Black', 'answered': False}, {'category': 'behind the songs', 'id': 110695, 'value': 800, 'question': "Blue Oyster Cult's Buck Dharma wrote this song after pondering about dying young & whether loved ones are reunited", 'answer': '"(Don\\\'t Fear) The Reaper"', 'answered': False}, {'category': 'behind the songs', 'id': 110701, 'value': 1000, 'question': 'A girl who he knew was trouble called & said she was coming over; he wrote "Wicked Game" by the time she got there', 'answer': 'Chris Isaak', 'answered': False}], 'hidden': [{'category': 'hidden', 'id': 57336, 'value': 200, 'question': 'From the French for "to disguise", soldiers wear this to conceal themselves from the enemy', 'answer': 'camouflage', 'answered': False}, {'category': 'hidden', 'id': 57342, 'value': 400, 'question': 'If your junior spy kit has run out of this, lemon juice can be substituted', 'answer': 'invisible ink', 'answered': False}, {'category': 'hidden', 'id': 57348, 'value': 600, 'question': 'Hidden features on DVDs are known as these "holiday" items', 'answer': 'Easter eggs', 'answered': False}, {'category': 'hidden', 'id': 57354, 'value': 800, 'question': 'In 1962 a Louisiana company got a patent for a device that added these to motion pictures in theaters', 'answer': 'subliminal advertisements', 'answered': False}, {'category': 'hidden', 'id': 57360, 'value': 1000, 'question': 'Latin for "things to be done", you have to watch out for a person\'s hidden one', 'answer': 'agenda', 'answered': False}]}
    
    cur.execute("INSERT INTO rooms(room_name, board, player1, started, complete) VALUES (%s,%s,%s, 0, 0)",(room_name,json.dumps(new_board),connected_users[access_token]['auth0_code']))
    cur.execute('SELECT room_id FROM rooms WHERE room_name = %s',(room_name,))
    room_id = int(cur.fetchone()[0])
    room_list[room_id] = copy.deepcopy(room_template)
    room_list[room_id].update({
        'name':room_name,
        'room_id':room_id,
        'board':new_board,
        'players':{
            'count':0,
            'total_count':1,
            'one':{
                'auth0_code':connected_users[access_token]['auth0_code'],
                'score':0
            },
        },
    })
    conn.commit()
    return jsonify({"room_id":room_id})

@app.route('/api/roomlist/getboard', methods=['GET'])
@cross_origin(headers=['Content-Type', 'Authorization'])
@requires_auth
def get_board():
    global room_list, connected_users
    access_token = get_token_auth_header()
    room_id = int(request.headers['room_id'])
    try:
        board = room_list[room_id]['board']
    except:
        cur.execute("SELECT board, room_name, player1, player1value, player2, player2value, player3, player3value, started FROM rooms WHERE room_id = %s",(room_id,))
        board, room_name, player1, player1value, player2, player2value, player3, player3value, started = cur.fetchone()
        board = json.loads(board)
        players = {
            'one':{},
            'two':{},
            'three':{}
        }
        if player1 != None:
            players['count'] = players.get('count',0)
            players['total_count'] = players.get('total_count',0) + 1
            players['one']['auth0_code'] = player1
            players['one']['score'] = player1value
            if players['one']['auth0_code'] == connected_users[access_token]['auth0_code']:
                connected_users['player_num'] = 'one'
        if player2 != None:
            players['count'] = players.get('count',0) + 1
            players['total_count'] = players.get('total_count',0) + 1
            players['two']['auth0_code'] = player2
            players['two']['score'] = player2value
            if players['two']['auth0_code'] == connected_users[access_token]['auth0_code']:
                connected_users['player_num'] = 'two'
        if player3 != None:
            players['count'] = players.get('count',0) + 1
            players['total_count'] = players.get('total_count',0) + 1
            players['three']['auth0_code'] = player3
            players['three']['score'] = player3value
            if players['three']['auth0_code'] == connected_users[access_token]['auth0_code']:
                connected_users['player_num'] = 'three'
        room_list[room_id] = copy.deepcopy(room_template)
        room_list[room_id].update({
            'name':room_name,
            'room_id':room_id,
            'board':board,
            'started':started,
            'players': players,
        })
    filtered_board = {}
    for key in board:
        filtered_board[key] = []
        for arr in board[key]:
            filtered_board[key].append({'category':arr['category'], 'id':arr['id'], 'value':arr['value'], 'answered':arr['answered']})
    return jsonify({'board': filtered_board})

req_ids = {}  

def ping_check():
    global room_list, ping_list, socketio
    ping_count = 0
    while True:
        socketio.sleep(10)
        ping_list[ping_count] = datetime.datetime.now()
        socketio.emit('ping_check', {'ping_num':ping_count}, namespace='/jep', room='players')
        ping_count = ping_count + 1

def buzzIn(room_id):
    socketio.sleep(3)
    socketio.emit('buzzable', {'buzz':True, 'buzzable_players':room_list[room_id]['buzzable_players']}, namespace='/jep', room=str(room_id))

def buzzBackground(args):
    global room_list
    room_id = args['room_id']
    catclue = args['screen_clicked']
    socketio.sleep(5)
    if room_list[room_id]['buzzedIn'] == 0:
        category, clue = catclue.split('|')
        clue = int(clue)
        room_list[room_id]['answer_count'] = room_list[room_id].get('answer_count', 0) + 1
        if room_list[room_id].get('answer_count', 0) >= 5:
            calculate_winner(room_id)
        socketio.emit('no_buzz', { 'screen_clicked':catclue}, namespace='/jep', room=str(room_id))
        socketio.emit('no_correct_answer', { 'position':room_list[room_id]['active_player'], 'answer': room_list[room_id]['board'][category][clue]['answer']}, namespace='/jep', room=str(room_id))

def buzz_in_background(room_id):
    global room_list
    if len(room_list[room_id]['buzzable_players']) > 1:
        socketio.sleep(2)
    lowest_time = 99999999999999999
    lowest_player = ''
    for player in room_list[room_id]['buzzedPlayerTimes']:
        if room_list[room_id]['buzzedPlayerTimes'][player] != '':
            if room_list[room_id]['buzzedPlayerTimes'][player] < lowest_time:
                lowest_time = room_list[room_id]['buzzedPlayerTimes'][player]
                lowest_player = player
    room_list[room_id]['buzzedIn'] = numbers.index(lowest_player)
    del room_list[room_id]['buzzable_players'][room_list[room_id]['buzzable_players'].index(lowest_player)]
    socketio.emit('fastest_buzz', {'buzzedIn':room_list[room_id]['buzzedIn']}, namespace='/jep', room=str(room_id))
    thread_answer_timer = Lock()
    room_list[room_id]['answer_timer'] = None
    with thread_answer_timer:
        if room_list[room_id]['answer_timer'] == None:
            room_list[room_id]['answer_timer'] = socketio.start_background_task(answer_timer,room_id)

def answer_timer(room_id):
    global room_list
    pos = room_list[room_id]['buzzedIn']
    question = room_list[room_id]['screen_clicked']
    socketio.sleep(7)
    if room_list[room_id]['buzzedIn'] == pos and question == room_list[room_id]['screen_clicked']:
        socketio.emit('take_too_long', {}, namespace='/jep', room=str(room_id))

def calculate_winner(room_id):
    global room_list
    highest_score = -99999999999
    highest_player = ''
    for player in room_list[room_id]['players']:
        if player == 'one' or player == 'two' or player == 'three':
            if room_list[room_id]['players'][player]['username'] != '':
                if room_list[room_id]['players'][player]['score'] > highest_score:
                    highest_score = room_list[room_id]['players'][player]['score']
                    highest_player = room_list[room_id]['players'][player]['username']
                elif room_list[room_id]['players'][player]['score'] == highest_score:
                    highest_player = [highest_player, room_list[room_id]['players'][player]['username']]
    socketio.emit('winner', {'username':highest_player}, namespace='/jep', room=str(room_id))

class jeopardy_socket(Namespace):

    def on_pong_res(self, message):
        global room_list, ping_list, req_ids
        pos = req_ids[request.sid]['player_num']
        diff = datetime.datetime.now() - ping_list[message['ping_num']]
        ping = round((diff.microseconds / 10**6 + diff.seconds) * 1000)
        room_list[req_ids[request.sid]['room_id']]['players'][pos].get('ping',[]).append(ping) 

    def on_connect(self):
        global thread
        with thread_lock:
            if thread is None:
                thread = socketio.start_background_task(ping_check)

    def on_disconnect(self):
        global room_list, req_ids, connected_users
        room_id = req_ids[request.sid]['room_id']
        username = req_ids[request.sid]['username'][0]
        print(req_ids[request.sid]['username'][0] + ' disconnected from room ' + str(room_id))
        if req_ids[request.sid].get('player_num', 0) != 0:
            room_list[room_id]['players']['count'] = room_list[room_id]['players']['count'] - 1
        if username in room_list[room_id]['viewers']:
            del room_list[room_id]['viewers'][room_list[room_id]['viewers'].index(username)]
        if room_list[room_id]['players']['count'] == 0 and len(room_list[room_id]['viewers']) == 0:
            print('closed room ' + str(room_id))
            del room_list[room_id]
        del connected_users[req_ids[request.sid]['access_token']]
        del req_ids[request.sid]

    def on_join_room(self,message):
        try:
            global room_list, connected_users, req_ids


            room_id = message['room_id']
            access_token = message['access_token']
            req_ids[request.sid] = connected_users[access_token]

            join_room(str(room_id))

            room_list[room_id]['viewers'].append(req_ids[request.sid]['username'][0])
            req_ids[request.sid]['sid'] = request.sid
            req_ids[request.sid]['room_id'] = room_id

            cur.execute("SELECT player_id FROM players WHERE auth0_code = %s",(req_ids[request.sid]['auth0_code'],))
            req_ids[request.sid]['player_id'] = cur.fetchone()[0]

            if room_list[room_id].get('started', False,) == False:
                room_list[room_id]['active_player'] = 0
            if room_list[room_id].get('players',None) == None:
                room_list[room_id]['players'] = room_list[room_id].get('players',{})
            room_list[room_id]['players']['one'] = room_list[room_id]['players'].get('one',{})
            room_list[room_id]['players']['two'] = room_list[room_id]['players'].get('two',{})
            room_list[room_id]['players']['three'] = room_list[room_id]['players'].get('three',{})
            if room_list[room_id].get('init', None) == None:
                for pos in room_list[room_id]['players']:
                    if pos == 'one' or pos == 'two' or pos == 'three':
                        room_list[req_ids[request.sid]['room_id']]['players'][pos]['ping'] = []
                        cur.execute("SELECT username FROM players WHERE auth0_code = %s",(room_list[room_id]['players'][pos].get('auth0_code','0'),))
                        try:
                            room_list[room_id]['players'][pos]['username'] = cur.fetchone()[0]
                            room_list[room_id]['players'][pos]['score'] = 0
                        except:
                            room_list[room_id]['players'][pos]['username'] = ""
                            room_list[room_id]['players'][pos]['score'] = 0
                room_list[room_id]['init'] = True
            room = json.loads(json.dumps(room_list[room_id]))
            for pos in room['players']:
                if pos == 'one' or pos == 'two' or pos == 'three':
                    if room['players'][pos].get('auth0_code', None) != None:
                        del room['players'][pos]['auth0_code']
                        if room_list[room_id]['players'][pos]['auth0_code'] == req_ids[request.sid]['auth0_code']:
                            req_ids[request.sid]['player_num'] = pos
                            room_list[room_id]['viewers'].remove(req_ids[request.sid]['username'][0])
                            room_list[room_id]['players']['count'] = room_list[room_id]['players']['count'] + 1
                            join_room('players')
            emit('has_joined_room', { 
                'players':{ 
                    'one':room['players']['one'],
                    'two':room['players']['two'],
                    'three':room['players']['three'] 
                }, 
                'position':req_ids[request.sid].get('player_num',0), 
                'player_id':req_ids[request.sid]['player_id'],
                'started': room['started'],
                'active_player':room['active_player']
                }
            )
        except Exception as e:
            print(e)
            emit('error')

    def on_viewer_joined(self):
        global req_ids, room_list
        room_id = req_ids[request.sid]['room_id']
        emit('viewer_added', { 'viewers':len(room_list[room_id]['viewers'])}, room=str(room_id))

    def on_player_select(self,message):
        global room_list, connected_users ,req_ids

        position = message['position']
        room_id = req_ids[request.sid]['room_id']
        auth0_code = req_ids[request.sid]['auth0_code']
        
        if req_ids[request.sid].get('player_num',None) == None:
            if room_list[room_id]['players'][position]['username'] == "" and room_list[room_id].get('started', False) == False:
                room_list[room_id]['viewers'].remove(req_ids[request.sid]['username'][0])
                join_room('players')
                room_list[room_id]['players'][position]['auth0_code'] = auth0_code
                cur.execute("SELECT username FROM players WHERE auth0_code = %s",(room_list[room_id]['players'][position].get('auth0_code','0'),))
                room_list[room_id]['players'][position]['username'] = cur.fetchone()[0]
                req_ids[request.sid]['player_num'] = position
                room_list[room_id]['players']['count'] = room_list[room_id]['players'].get('count',0) + 1
                room_list[room_id]['players']['total_count'] = room_list[room_id]['players'].get('total_count',0) + 1
                emit('player_selected',{'username':req_ids[request.sid]['username'],'position':position, 'player_id':req_ids[request.sid]['player_id']}, room=str(room_id))

    def on_player_ready(self, message):
        global room_list, req_ids
        room_id = req_ids[request.sid]['room_id']
        pos = req_ids[request.sid]['player_num']
        if room_list[room_id]['players'][pos].get('ready',False) == False:
            room_list[room_id]['players'][pos]['ready'] = True
            room_list[room_id]['players']['ready_count'] = room_list[room_id]['players'].get('ready_count', 0) + 1
        else:
            room_list[room_id]['players'][pos]['ready'] = False
            room_list[room_id]['players']['ready_count'] = room_list[room_id]['players']['ready_count'] - 1
        if room_list[room_id]['players'].get('ready_count', 0) == room_list[room_id]['players']['count']:
            room_list[room_id]['started'] = 1
            room_list[room_id]['active_player'] = 1
            emit('ready_player', { 'position':pos,'ready':room_list[room_id]['players'][pos]['ready'], 'started': room_list[room_id]['started'], 'active_player': room_list[room_id]['active_player']}, room=str(room_id))
        else:
            emit('ready_player', { 'position':pos,'ready':room_list[room_id]['players'][pos]['ready'], 'started': room_list[room_id]['started']}, room=str(room_id))

    def on_screen_select(self, message):
        global room_list, req_ids
        room_id = req_ids[request.sid]['room_id']
        screen_clicked = message['screen_clicked']
        if numbers.index(req_ids[request.sid]['player_num']) == room_list[room_id]['active_player']:
            room_list[room_id]['screen_clicked'] = screen_clicked
            category, clue = room_list[room_id]['screen_clicked'].split('|')
            clue = int(clue)
            if room_list[room_id]['board'][re.sub(r'[^A-Za-z]','',category)][clue]['answered'] == False:
                room_list[room_id]['board'][re.sub(r'[^A-Za-z]','',category)][clue]['answered'] = True
                room_list[room_id]['buzzable_players'] = []
                for pos in room_list[room_id]['players']:
                    if pos == 'one' or pos == 'two' or pos == 'three':
                        if room_list[room_id]['players'][pos]['username'] != '':
                            room_list[room_id]['buzzable_players'].append(pos)
                room_list[room_id]['selected_board'] = room_list[room_id]['screen_clicked']
                room_list[room_id]['buzzedPlayerTimes'] = {'one':'','two':'','three':''}
                emit('screen_selected', { 'category':category, 'clue':clue, 'screen_text': room_list[room_id]['board'][category][clue]['question'], 'active_player':0, 'x_and_y':message['x_and_y']}, room=str(room_id))
                thread_lock_back = Lock()
                with thread_lock_back:
                    socketio.start_background_task(buzzIn,room_id)
                    room_list[room_id]['buzzed_in_back'] = None
                    room_list[room_id]['buzz_background'] = None
                    room_list[room_id]['buzzedIn'] = 0
                    room_list[room_id]['selected_time'] = datetime.datetime.now()
                    room_list[room_id]['buzz_background'] = socketio.start_background_task(buzzBackground,{'room_id':room_id, 'screen_clicked':room_list[room_id]['screen_clicked']})

    def on_buzz_in(self):
        global room_list, req_ids
        room_id = req_ids[request.sid]['room_id']
        pos = req_ids[request.sid]['player_num']

        if pos in room_list[room_id]['buzzable_players']:
            room_list[room_id]['buzzedIn'] = pos
            now = room_list[room_id]['selected_time']
            diff = (datetime.datetime.now() - now)
            diff = round((diff.microseconds / 10**6 + diff.seconds) * 1000)
            try:
                room_list[room_id]['buzzedPlayerTimes'][pos] = diff - (sum(room_list[room_id]['players'][pos].get('ping',[])) / len(room_list[room_id]['players'][pos].get('ping',[])))
            except:
                room_list[room_id]['buzzedPlayerTimes'][pos] = diff

            with thread_lock_buzz:
                if room_list[room_id]['buzzed_in_back'] == None:
                    room_list[room_id]['buzzed_in_back'] = socketio.start_background_task(buzz_in_background,room_id)

    def on_answer_typed(self, message):
        global room_list, req_ids, numbers
        room_id = req_ids[request.sid]['room_id']
        if numbers.index(req_ids[request.sid]['player_num']) == room_list[room_id]['buzzedIn']:
            emit('typed_answer', {'answer_input':message['answer']}, room=str(room_id))

    def on_answer_submit(self, message):
        global room_list, req_ids, numbers
        room_id = req_ids[request.sid]['room_id']
        answer = message['answer']
        pos = req_ids[request.sid]['player_num']
        if numbers[room_list[room_id]['buzzedIn']] == req_ids[request.sid]['player_num']:
            room_list[room_id]['buzzedIn'] = 0
            category, clue = room_list[room_id]['selected_board'].split('|')
            clue = int(clue)
            real_answer = re.sub(r'<.+?>','',room_list[room_id]['board'][category][clue]['answer'])
            real_answer = re.sub(r'(?<=\b)(the|a|an)\s?(?=\b)','',real_answer)
            # match = re.search(re.sub(r'[^A-Za-z0-9\s]','',answer.lower()),re.sub(r'[^A-Za-z0-9\s]','',real_answer.lower()))
            # if match != None:
            #     match = match.group()
            # else:
            #     match = ''

            ratio = fuzz.ratio(re.sub(r'[^A-Za-z0-9\s]','',answer.lower()), re.sub(r'[^A-Za-z0-9\s]','',real_answer.lower()))
            token_sort = fuzz.token_sort_ratio(re.sub(r'[^A-Za-z0-9\s]','',answer.lower()), re.sub(r'[^A-Za-z0-9\s]','',real_answer.lower()))
            token_set = fuzz.token_set_ratio(re.sub(r'[^A-Za-z0-9\s]','',answer.lower()), re.sub(r'[^A-Za-z0-9\s]','',real_answer.lower()))

            print_answer = re.sub(r'[^A-Za-z0-9\s]','',answer.lower())
            pint_real_answer = re.sub(r'[^A-Za-z0-9\s]','',real_answer.lower())
            
            # print(fuzz.ratio(re.sub(r'[^A-Za-z0-9\s]','',match), re.sub(r'[^A-Za-z0-9\s]','',real_answer)))
            # print(fuzz.partial_ratio(re.sub(r'[^A-Za-z0-9\s]','',answer.lower()), re.sub(r'[^A-Za-z0-9\s]','',real_answer.lower())))
            # print(fuzz.token_sort_ratio(re.sub(r'[^A-Za-z0-9\s]','',match), re.sub(r'[^A-Za-z0-9\s]','',real_answer)))
            # print(fuzz.token_set_ratio(re.sub(r'[^A-Za-z0-9\s]','',match), re.sub(r'[^A-Za-z0-9\s]','',real_answer)))
            print(f"{print_answer} | {pint_real_answer} | ratio: {ratio}%, sort: {token_sort}%, set: {token_set}% = {(ratio + token_sort + token_set) // 3}")
            # print(len(re.sub(r'[^A-Za-z0-9\s]','',match)) / len(re.sub(r'[^A-Za-z0-9\s]','',real_answer)) * 100)
            if (ratio + token_sort + token_set) // 3 > 50 and (ratio == 100 or token_sort == 100 or token_set == 100) :
                print('correct')
                room_list[room_id]['answer_count'] = room_list[room_id].get('answer_count', 0) + 1
                if room_list[room_id].get('answer_count', 0) >= 5:
                    calculate_winner(room_id)
                room_list[room_id]['players'][pos]['score'] = room_list[room_id]['players'][pos]['score'] + room_list[room_id]['board'][category][clue]['value']
                room_list[room_id]['active_player'] = numbers.index(pos)
                emit('answer_response', { 'correct':True, 'position': pos, 'new_score': room_list[room_id]['players'][pos]['score'] }, room=str(room_id))
            else:
                print('wrong')
                room_list[room_id]['players'][pos]['score'] = room_list[room_id]['players'][pos]['score'] - room_list[room_id]['board'][category][clue]['value']
                emit('answer_response', { 'correct':False, 'position': pos, 'new_score':room_list[room_id]['players'][pos]['score'], 'buzzable_players':room_list[room_id]['buzzable_players'] }, room=str(room_id))
                if len(room_list[room_id]['buzzable_players']) == 0:
                    room_list[room_id]['answer_count'] = room_list[room_id].get('answer_count', 0) + 1
                    if room_list[room_id].get('answer_count', 0) >= 5:
                        calculate_winner(room_id)
                    emit('no_buzz', { 'screen_clicked':room_list[room_id]['screen_clicked'] }, room=str(room_id))
                    emit('no_correct_answer', { 'position':room_list[room_id]['active_player'], 'answer': room_list[room_id]['board'][category][clue]['answer']}, room=str(room_id))
                else:
                    room_list[room_id]['buzzedPlayerTimes'] = {'one':'','two':'','three':''}
                    thread_lock_back = Lock()
                    with thread_lock_back:
                        socketio.start_background_task(buzzIn,room_id)
                        room_list[room_id]['buzzed_in_back'] = None
                        room_list[room_id]['buzz_background'] = None
                        room_list[room_id]['buzzedIn'] = 0
                        room_list[room_id]['selected_time'] = datetime.datetime.now()
                        room_list[room_id]['buzz_background'] = socketio.start_background_task(buzzBackground,{'room_id':room_id, 'screen_clicked':room_list[room_id]['screen_clicked']})



    def on_test(self, message):
        print(message['data'])
        emit('test', {'test':'test'})
        

socketio.on_namespace(jeopardy_socket('/jep'))

if __name__ == '__main__':
    socketio.run(app, debug=True, host= '10.44.22.86')
    # , host= '0.0.0.0'
