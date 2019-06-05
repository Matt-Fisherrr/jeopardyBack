from flask import Flask, request, jsonify, render_template, send_from_directory, current_app as app
from flask_cors import cross_origin
import files.global_vars as gv
from jose import jwt
from .room import Room
import hashlib

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def index(path):
    if path == 'favicon.ico':
        return send_from_directory('build/',path)
    return render_template('index.html')

@app.route('/api/connect', methods=['POST'])
@cross_origin(allow_headers=['authorization', 'content-type'], allow_methods=['POST, OPTIONS'])
@gv.auth.auth_required(request)
def connect():
    id_token = request.get_json()['IDToken']
    access_token = gv.auth.get_token_auth_header(request)

    id_decode = jwt.decode(id_token, gv.jwks, algorithms=gv.auth.ALGORITHMS, audience="3eCEPx9I6Wr0N3FIJAwXXi5caFdRfZzV", access_token=access_token)
    hashed_id = str(hashlib.sha512(id_decode['sub'].encode('utf-8') + '8616b99be2344c82ad77f24977eac12e'.encode('utf-8')).hexdigest())
    gv.cur.execute("SELECT username FROM players WHERE auth0_code = %s", (hashed_id,))
    username = gv.cur.fetchone()

    gv.connected_users[access_token] = {'access_token':access_token, 'id_token':id_token, 'auth0_code':hashed_id}
    if username == None:
        return jsonify({'response': 'username'})

    gv.connected_users[access_token]['username'] = username[0]
    return jsonify({'response': True, 'username': username[0]})

@app.route('/api/connect/reg', methods=['POST'])
@cross_origin(allow_headers=['authorization', 'content-type'], allow_methods=['POST, OPTIONS'])
@gv.auth.auth_required(request)
def set_username():
    access_token = gv.auth.get_token_auth_header(request)
    username = request.get_json()['user']
    gv.cur.execute("SELECT count(auth0_code) FROM players WHERE auth0_code = %s", (gv.connected_users[access_token]['auth0_code'],))
    if gv.cur.fetchone()[0] == 0:
        gv.cur.execute("INSERT INTO players(username, auth0_code) VALUES (%s, %s)", (username, gv.connected_users[access_token]['auth0_code']))
    else:
        gv.cur.execute("UPDATE players SET username = %s WHERE auth0_code = %s", (username, gv.connected_users[access_token]['auth0_code']))
    gv.connected_users[access_token]['username'] = username
    gv.conn.commit()
    return jsonify({'response': True, 'username': username})

@app.route('/api/roomlist', methods=['GET'])
@cross_origin(allow_headers=['authorization', 'content-type'], allow_methods=['GET, OPTIONS'])
@gv.auth.auth_required(request)
def get_room_list():
    access_token = gv.auth.get_token_auth_header(request)
    rooms = []
    for room in gv.room_list:
        rooms.append({'name':gv.room_list[room].name, 'id':gv.room_list[room].room_id, 'players':'started' if gv.room_list[room].started else gv.room_list[room].player_counts['total_count'], 'old':False })
    gv.cur.execute("SELECT room_name, room_id, player1, player2, player3, started FROM rooms WHERE player1 = %s AND complete = 0",(gv.connected_users[access_token]['auth0_code'],))
    for room in gv.cur.fetchall():
        if room[1] not in list(gv.room_list.keys()):
            rooms.append({'name':room[0], 'id':room[1], 'players':'started' if room[5] == 1 else len([p for p in room[2:4] if p != None]), 'old':True })
    return jsonify(rooms)

@app.route('/api/roomlist/create', methods=['POST'])
@cross_origin(allow_headers=['authorization', 'content-type'], allow_methods=['POST, OPTIONS'])
@gv.auth.auth_required(request)
def make_room():
    room_name = request.get_json()['roomName']

    gv.cur.execute("INSERT INTO rooms(room_name, started, complete) VALUES (%s,0, 0)",(room_name, ))
    gv.cur.execute('SELECT room_id FROM rooms WHERE room_name = %s',(room_name,))
    
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
    #     print(board.keys())
    # new_board = {}
    # for key in board:
    #     new_board[re.sub(r'[^A-Za-z]','',key)] = []
    #     for arr in board[key]:
    #         new_board[re.sub(r'[^A-Za-z]','',key)].append({'category':key, 'id':arr['id'], 'value':arr['value'], 'question':arr['question'], 'answer':arr['answer'], 'answered':False})
    
    new_board = {'hairyit': [{'category': 'test column', 'id': 82119, 'value': 200, 'question': 'Italics test', 'answer': '<i>an anteater</i>', 'answered': False}, {'category': 'hairy it', 'id': 82125, 'value': 400, 'question': "woman / women", 'answer': 'a women', 'answered': False}, {'category': 'hairy it', 'id': 82131, 'value': 600, 'question': 'data / datum', 'answer': 'the datum', 'answered': False}, {'category': 'hairy it', 'id': 82137, 'value': 800, 'question': 'Millennia / mellennium', 'answer': 'a millennium', 'answered': False}, {'category': 'hairy it', 'id': 82143, 'value': 1000, 'question': 'Opera / opus', 'answer': 'an opus', 'answered': False}], 'mixingapplesoranges': [{'category': 'mixing apples & oranges', 'id': 107828, 'value': 200, 'question': 'An apple & a crossbow play important roles in this 1804 Schiller tale', 'answer': 'William Tell', 'answered': False}, {'category': 'mixing apples & oranges', 'id': 107834, 'value': 400, 'question': 'This 2-word Vietnam War item consisted of 2 weedkillers--2,4-D & 2,4,5-T', 'answer': 'Agent Orange', 'answered': False}, {'category': 'mixing apples & oranges', 'id': 107840, 'value': 600, 'question': 'The European type of this holiday plant seen here grows most often on apple trees', 'answer': 'mistletoe', 'answered': False}, {'category': 'mixing apples & oranges', 'id': 107846, 'value': 800, 'question': 'Have a devil of a time in this smallest state in Australia, often called the Apple Isle', 'answer': 'Tasmania', 'answered': False}, {'category': 'mixing apples & oranges', 'id': 107852, 'value': 1000, 'question': 'This Florida sports & concert venue was demolished in 2008', 'answer': 'the Orange Bowl Stadium', 'answered': False}], 'itisaletterword': [{'category': '"it" is a 7-letter word', 'id': 92049, 'value': 200, 'question': 'Proverbially, this "is the soul of wit"', 'answer': 'brevity', 'answered': False}, {'category': '"it" is a 7-letter word', 'id': 92055, 'value': 400, 'question': 'A native or naturalized member of a state or nation', 'answer': 'a citizen', 'answered': False}, {'category': '"it" is a 7-letter word', 'id': 92061, 'value': 600, 'question': "A marauding linebacker, or CNN's Wolf", 'answer': 'a blitzer', 'answered': False}, {'category': '"it" is a 7-letter word', 'id': 92067, 'value': 800, 'question': 'A notable one of these read, "Here lies Ann Mann, who lived an old maid but died an old Mann"', 'answer': 'an epitaph', 'answered': False}, {'category': '"it" is a 7-letter word', 'id': 92073, 'value': 1000, 'question': 'Nickname of Andrew Jackson\'s informal "cabinet", which included Martin Van Buren', 'answer': 'the Kitchen Cabinet', 'answered': False}], 'behindthesongs': [{'category': 'behind the songs', 'id': 110677, 'value': 200, 'question': "Tom Higgenson's flirtation with a girl in New York & a promise to write her a song led to this megahit for the Plain White T's", 'answer': '"Hey There Delilah"', 'answered': False}, {'category': 'behind the songs', 'id': 110683, 'value': 400, 'question': "It was a Saturday in the park--Central Park--that inspired Robert Lamm to write this group's first gold single", 'answer': 'Chicago', 'answered': False}, {'category': 'behind the songs', 'id': 110689, 'value': 600, 'question': 'This country singer wrote "When I Said I Do" for wife Lisa Hartman, who then recorded the song with him as a duet', 'answer': 'Clint Black', 'answered': False}, {'category': 'behind the songs', 'id': 110695, 'value': 800, 'question': "Blue Oyster Cult's Buck Dharma wrote this song after pondering about dying young & whether loved ones are reunited", 'answer': '"(Don\\\'t Fear) The Reaper"', 'answered': False}, {'category': 'behind the songs', 'id': 110701, 'value': 1000, 'question': 'A girl who he knew was trouble called & said she was coming over; he wrote "Wicked Game" by the time she got there', 'answer': 'Chris Isaak', 'answered': False}], 'hidden': [{'category': 'hidden', 'id': 57336, 'value': 200, 'question': 'From the French for "to disguise", soldiers wear this to conceal themselves from the enemy', 'answer': 'camouflage', 'answered': False}, {'category': 'hidden', 'id': 57342, 'value': 400, 'question': 'If your junior spy kit has run out of this, lemon juice can be substituted', 'answer': 'invisible ink', 'answered': False}, {'category': 'hidden', 'id': 57348, 'value': 600, 'question': 'Hidden features on DVDs are known as these "holiday" items', 'answer': 'Easter eggs', 'answered': False}, {'category': 'hidden', 'id': 57354, 'value': 800, 'question': 'In 1962 a Louisiana company got a patent for a device that added these to motion pictures in theaters', 'answer': 'subliminal advertisements', 'answered': False}, {'category': 'hidden', 'id': 57360, 'value': 1000, 'question': 'Latin for "things to be done", you have to watch out for a person\'s hidden one', 'answer': 'agenda', 'answered': False}]}

    room_id = int(gv.cur.fetchone()[0])
    gv.room_list[room_id] = Room()
    gv.room_list[room_id].name = room_name
    gv.room_list[room_id].room_id = room_id
    gv.room_list[room_id].board = new_board
    
    gv.conn.commit()
    return jsonify({"room_id":room_id})

# @app.route('/api/roomlist/getboard', methods=['GET'])
# @cross_origin(headers=['Content-Type', 'Authorization'])
# @gv.auth.auth_required(request)
# def get_board():
#     access_token = auth.get_token_auth_header(request)
#     room_id = int(request.headers['room_id'])
#     try:
#         board = room_list[room_id]['board']
#     except:
#         cur.execute("SELECT board, room_name, player1, player1value, player2, player2value, player3, player3value, started FROM rooms WHERE room_id = %s",(room_id,))
#         board, room_name, player1, player1value, player2, player2value, player3, player3value, started = cur.fetchone()
#         board = json.loads(board)
#         players = {
#             'one':{},
#             'two':{},
#             'three':{}
#         }
#         if player1 != None:
#             players['count'] = players.get('count',0)
#             players['total_count'] = players.get('total_count',0) + 1
#             players['one']['auth0_code'] = player1
#             players['one']['score'] = player1value
#             if players['one']['auth0_code'] == connected_users[access_token]['auth0_code']:
#                 connected_users['player_num'] = 'one'
#         if player2 != None:
#             players['count'] = players.get('count',0) + 1
#             players['total_count'] = players.get('total_count',0) + 1
#             players['two']['auth0_code'] = player2
#             players['two']['score'] = player2value
#             if players['two']['auth0_code'] == connected_users[access_token]['auth0_code']:
#                 connected_users['player_num'] = 'two'
#         if player3 != None:
#             players['count'] = players.get('count',0) + 1
#             players['total_count'] = players.get('total_count',0) + 1
#             players['three']['auth0_code'] = player3
#             players['three']['score'] = player3value
#             if players['three']['auth0_code'] == connected_users[access_token]['auth0_code']:
#                 connected_users['player_num'] = 'three'
#         # room_list[room_id] = copy.deepcopy(room_template)
#         # room_list[room_id].update({
#         #     'name':room_name,
#         #     'room_id':room_id,
#         #     'board':board,
#         #     'started':started,
#         #     'players': players,
#         # })
#     filtered_board = {}
#     for key in board:
#         filtered_board[key] = []
#         for arr in board[key]:
#             filtered_board[key].append({'category':arr['category'], 'id':arr['id'], 'value':arr['value'], 'answered':arr['answered']})
#     return jsonify({'board': filtered_board})