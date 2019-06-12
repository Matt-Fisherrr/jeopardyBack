from flask import Flask, request, jsonify, render_template, send_from_directory, current_app as app
from flask_cors import cross_origin
# import files.global_vars as gv
from jose import jwt
from .room import Room
import hashlib, re, requests, random

from main import global_vars as gv

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
    gv.cur.execute("SELECT room_name, room_id, player1, player2, player3, started FROM rooms WHERE room_owner = %s AND complete = 0",(gv.connected_users[access_token]['auth0_code'],))
    for room in gv.cur.fetchall():
        if room[1] not in list(gv.room_list.keys()):
            rooms.append({'name':room[0], 'id':room[1], 'players':'started' if room[5] == 1 else len([p for p in room[2:4] if p != None]), 'old':True })
    return jsonify(rooms)

@app.route('/api/roomlist/create', methods=['POST'])
@cross_origin(allow_headers=['authorization', 'content-type'], allow_methods=['POST, OPTIONS'])
@gv.auth.auth_required(request)
def make_room():
    room_name = request.get_json()['roomName']
    access_token = gv.auth.get_token_auth_header(request)

    gv.cur.execute("INSERT INTO rooms(room_name, room_owner, started, complete) VALUES (%s, %s, 0, 0)",(room_name, gv.connected_users[access_token]['auth0_code']))
    gv.cur.execute('SELECT room_id FROM rooms WHERE room_name = %s',(room_name,))
    room_id = int(gv.cur.fetchone()[0])
    
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
    # # board = {'tv through the years': [{'id': 28455, 'answer': '<i>My Favorite Martian</i>', 'question': 'Ray Walston played an inventive alien stranded on Earth in this 1960s TV sitcom hit', 'value': 200, 'airdate': '1999-06-16T12:00:00.000Z', 'created_at': '2014-02-11T23:02:46.162Z', 'updated_at': '2014-02-11T23:02:46.162Z', 'category_id': 3195, 'game_id': None, 'invalid_count': None, 'category': {'id': 3195, 'title': 'tv through the years', 'created_at': '2014-02-11T23:02:45.925Z', 'updated_at': '2014-02-11T23:02:45.925Z', 'clues_count': 15}}, {'id': 28467, 'answer': '<i>The Untouchables</i>', 'question': '"JAG"\'s David James Elliott starred in the TV series version of this 1987 film that starred Kevin Costner', 'value': 400, 'airdate': '1999-06-16T12:00:00.000Z', 'created_at': '2014-02-11T23:02:46.372Z', 'updated_at': '2014-02-11T23:02:46.372Z', 'category_id': 3195, 'game_id': None, 'invalid_count': None, 'category': {'id': 3195, 'title': 'tv through the years', 'created_at': '2014-02-11T23:02:45.925Z', 'updated_at': '2014-02-11T23:02:45.925Z', 'clues_count': 15}}, {'id': 128404, 'answer': '<i>The Wire</i>', 'question': 'Omar, played by Michael K. Williams, relieved Baltimore drug dealers of their profits on this HBO drama debuting in 2002', 'value': 600, 'airdate': '2013-10-22T12:00:00.000Z', 'created_at': '2015-01-18T18:15:12.804Z', 'updated_at': '2015-01-18T18:15:12.804Z', 'category_id': 3195, 'game_id': None, 'invalid_count': None, 'category': {'id': 3195, 'title': 'tv through the years', 'created_at': '2014-02-11T23:02:45.925Z', 'updated_at': '2014-02-11T23:02:45.925Z', 'clues_count': 15}}, {'id': 128410, 'answer': 'Jack Paar', 'question': '"I kid you not" was the catchphrase of this "Tonight Show" host before Johnny Carson', 'value': 800, 'airdate': '2013-10-22T12:00:00.000Z', 'created_at': '2015-01-18T18:15:13.083Z', 'updated_at': '2015-01-18T18:15:13.083Z', 'category_id': 3195, 'game_id': None, 'invalid_count': None, 'category': {'id': 3195, 'title': 'tv through the years', 'created_at': '2014-02-11T23:02:45.925Z', 'updated_at': '2014-02-11T23:02:45.925Z', 'clues_count': 15}}, {'id': 128416, 'answer': '<i>Northern Exposure</i>', 'question': "That's Morty the moose, not star Rob Morrow, in the opening credits of this Alaska-set '90s show", 'value': 1000, 'airdate': '2013-10-22T12:00:00.000Z', 'created_at': '2015-01-18T18:15:13.326Z', 'updated_at': '2015-01-18T18:15:13.326Z', 'category_id': 3195, 'game_id': None, 'invalid_count': None, 'category': {'id': 3195, 'title': 'tv through the years', 'created_at': '2014-02-11T23:02:45.925Z', 'updated_at': '2014-02-11T23:02:45.925Z', 'clues_count': 15}}], 'dinosaurs': [{'id': 62436, 'answer': 'the <i>Tyrannosaurus rex</i>', 'question': 'This dinosaur "king" could run as fast as 25 MPH & recent evidence suggests it was warm-blooded', 'value': 200, 'airdate': '2003-09-26T12:00:00.000Z', 'created_at': '2014-02-11T23:25:31.281Z', 'updated_at': '2014-02-11T23:25:31.281Z', 'category_id': 7999, 'game_id': None, 'invalid_count': None, 'category': {'id': 7999, 'title': 'dinosaurs', 'created_at': '2014-02-11T23:25:31.176Z', 'updated_at': '2014-02-11T23:25:31.176Z', 'clues_count': 30}}, {'id': 63880, 'answer': 'Cretaceous', 'question': 'Scientists believe that dinosaurs lived through 3 geologic periods: Triassic, Jurassic, then this next one', 'value': 400, 'airdate': '2005-05-25T12:00:00.000Z', 'created_at': '2014-02-11T23:26:47.097Z', 'updated_at': '2014-02-11T23:26:47.097Z', 'category_id': 7999, 'game_id': None, 'invalid_count': None, 'category': {'id': 7999, 'title': 'dinosaurs', 'created_at': '2014-02-11T23:25:31.176Z', 'updated_at': '2014-02-11T23:25:31.176Z', 'clues_count': 30}}, {'id': 62448, 'answer': 'the <i>Stegosaurus</i>', 'question': 'One theory says the triangular plates on its back helped control body temperature; another says they attracted mates', 'value': 600, 'airdate': '2003-09-26T12:00:00.000Z', 'created_at': '2014-02-11T23:25:31.597Z', 'updated_at': '2014-02-11T23:25:31.597Z', 'category_id': 7999, 'game_id': None, 'invalid_count': None, 'category': {'id': 7999, 'title': 'dinosaurs', 'created_at': '2014-02-11T23:25:31.176Z', 'updated_at': '2014-02-11T23:25:31.176Z', 'clues_count': 30}}, {'id': 62454, 'answer': 'a <i>Velociraptor</i>', 'question': 'Made famous by "Jurassic Park", this 6-foot-long "swift robber" had a "killing claw" on each foot', 'value': 800, 'airdate': '2003-09-26T12:00:00.000Z', 'created_at': '2014-02-11T23:25:31.803Z', 'updated_at': '2014-02-11T23:25:31.803Z', 'category_id': 7999, 'game_id': None, 'invalid_count': None, 'category': {'id': 7999, 'title': 'dinosaurs', 'created_at': '2014-02-11T23:25:31.176Z', 'updated_at': '2014-02-11T23:25:31.176Z', 'clues_count': 30}}, {'id': 63898, 'answer': 'Brachiosaurus', 'question': 'Similar to an Apatosaurus, this 52\'-tall herbivore whose name means "arm lizard" had longer forelegs than hindlegs', 'value': 1000, 'airdate': '2005-05-25T12:00:00.000Z', 'created_at': '2014-02-11T23:26:47.614Z', 'updated_at': '2014-02-11T23:26:47.614Z', 'category_id': 7999, 'game_id': None, 'invalid_count': None, 'category': {'id': 7999, 'title': 'dinosaurs', 'created_at': '2014-02-11T23:25:31.176Z', 'updated_at': '2014-02-11T23:25:31.176Z', 'clues_count': 30}}], "in black's law dictionary": [{'id': 99428, 'answer': 'arson', 'question': '"The malicious burning of someone else\'s dwelling house or outhouse" (glad the outhouse is protected, too)', 'value': 200, 'airdate': '2009-12-15T12:00:00.000Z', 'created_at': '2014-02-14T02:05:23.202Z', 'updated_at': '2014-02-14T02:05:23.202Z', 'category_id': 13310, 'game_id': None, 'invalid_count': None, 'category': {'id': 13310, 'title': "in black's law dictionary", 'created_at': '2014-02-14T02:05:22.993Z', 'updated_at': '2014-02-14T02:05:22.993Z', 'clues_count': 5}}, {'id': 99434, 'answer': 'possession', 'question': '"The fact of having or holding property in one\'s power" (it\'s not 9/10 of Black\'s, it\'s only 1 entry)', 'value': 400, 'airdate': '2009-12-15T12:00:00.000Z', 'created_at': '2014-02-14T02:05:23.425Z', 'updated_at': '2014-02-14T02:05:23.425Z', 'category_id': 13310, 'game_id': None, 'invalid_count': None, 'category': {'id': 13310, 'title': "in black's law dictionary", 'created_at': '2014-02-14T02:05:22.993Z', 'updated_at': '2014-02-14T02:05:22.993Z', 'clues_count': 5}}, {'id': 99440, 'answer': 'act of God', 'question': 'This 3-word term is an "unpreventable event caused exclusively by forces of nature"', 'value': 600, 'airdate': '2009-12-15T12:00:00.000Z', 'created_at': '2014-02-14T02:05:23.690Z', 'updated_at': '2014-02-14T02:05:23.690Z', 'category_id': 13310, 'game_id': None, 'invalid_count': None, 'category': {'id': 13310, 'title': "in black's law dictionary", 'created_at': '2014-02-14T02:05:22.993Z', 'updated_at': '2014-02-14T02:05:22.993Z', 'clues_count': 5}}, {'id': 99446, 'answer': 'a plea', 'question': '"An accused person\'s formal response... to a criminal charge"', 'value': 800, 'airdate': '2009-12-15T12:00:00.000Z', 'created_at': '2014-02-14T02:05:23.913Z', 'updated_at': '2014-02-14T02:05:23.913Z', 'category_id': 13310, 'game_id': None, 'invalid_count': None, 'category': {'id': 13310, 'title': "in black's law dictionary", 'created_at': '2014-02-14T02:05:22.993Z', 'updated_at': '2014-02-14T02:05:22.993Z', 'clues_count': 5}}, {'id': 99452, 'answer': 'an arraignment', 'question': '"The initial step in... prosecution whereby the defendant is brought before the court to hear the charges"', 'value': 1000, 'airdate': '2009-12-15T12:00:00.000Z', 'created_at': '2014-02-14T02:05:24.139Z', 'updated_at': '2014-02-14T02:05:24.139Z', 'category_id': 13310, 'game_id': None, 'invalid_count': None, 'category': {'id': 13310, 'title': "in black's law dictionary", 'created_at': '2014-02-14T02:05:22.993Z', 'updated_at': '2014-02-14T02:05:22.993Z', 'clues_count': 5}}], 'dear john': [{'id': 71346, 'answer': 'John Major', 'question': "He was Tony Blair's immediate predecessor as prime minister", 'value': 200, 'airdate': '2006-05-04T12:00:00.000Z', 'created_at': '2014-02-11T23:32:20.619Z', 'updated_at': '2014-02-11T23:32:20.619Z', 'category_id': 9276, 'game_id': None, 'invalid_count': None, 'category': {'id': 9276, 'title': 'dear john', 'created_at': '2014-02-11T23:32:20.500Z', 'updated_at': '2014-02-11T23:32:20.500Z', 'clues_count': 10}}, {'id': 71352, 'answer': 'John Dillinger', 'question': 'He once said, "I don\'t smoke much, and I drink very little.  I guess my only bad habit is robbing banks"', 'value': 400, 'airdate': '2006-05-04T12:00:00.000Z', 'created_at': '2014-02-11T23:32:20.774Z', 'updated_at': '2014-02-11T23:32:20.774Z', 'category_id': 9276, 'game_id': None, 'invalid_count': None, 'category': {'id': 9276, 'title': 'dear john', 'created_at': '2014-02-11T23:32:20.500Z', 'updated_at': '2014-02-11T23:32:20.500Z', 'clues_count': 10}}, {'id': 71358, 'answer': '(John) Sutter', 'question': 'This man at whose mill gold was discovered in 1848 later ran for governor of California', 'value': 600, 'airdate': '2006-05-04T12:00:00.000Z', 'created_at': '2014-02-11T23:32:20.931Z', 'updated_at': '2014-02-11T23:32:20.931Z', 'category_id': 9276, 'game_id': None, 'invalid_count': None, 'category': {'id': 9276, 'title': 'dear john', 'created_at': '2014-02-11T23:32:20.500Z', 'updated_at': '2014-02-11T23:32:20.500Z', 'clues_count': 10}}, {'id': 71364, 'answer': '(John D.) Rockefeller', 'question': 'In 1946 he gave the United Nations a gift of $8.5 million to buy land for its NYC headquarters', 'value': 800, 'airdate': '2006-05-04T12:00:00.000Z', 'created_at': '2014-02-11T23:32:21.081Z', 'updated_at': '2014-02-11T23:32:21.081Z', 'category_id': 9276, 'game_id': None, 'invalid_count': None, 'category': {'id': 9276, 'title': 'dear john', 'created_at': '2014-02-11T23:32:20.500Z', 'updated_at': '2014-02-11T23:32:20.500Z', 'clues_count': 10}}, {'id': 71370, 'answer': 'John Cheever', 'question': 'This author of the novel "Falconer" won a 1979 Pulitzer Prize for some of his short stories', 'value': 1000, 'airdate': '2006-05-04T12:00:00.000Z', 'created_at': '2014-02-11T23:32:21.263Z', 'updated_at': '2014-02-11T23:32:21.263Z', 'category_id': 9276, 'game_id': None, 'invalid_count': None, 'category': {'id': 9276, 'title': 'dear john', 'created_at': '2014-02-11T23:32:20.500Z', 'updated_at': '2014-02-11T23:32:20.500Z', 'clues_count': 10}}], 'makes scents to me!': [{'id': 66188, 'answer': 'a heart', 'question': "Perfect for Valentine's Day, Fiorucci Loves You comes in a bottle shaped like one of these pierced with an arrow", 'value': 200, 'airdate': '2005-02-07T12:00:00.000Z', 'created_at': '2014-02-11T23:28:37.944Z', 'updated_at': '2014-02-11T23:28:37.944Z', 'category_id': 8557, 'game_id': None, 'invalid_count': None, 'category': {'id': 8557, 'title': 'makes scents to me!', 'created_at': '2014-02-11T23:28:37.791Z', 'updated_at': '2014-02-11T23:28:37.791Z', 'clues_count': 5}}, {'id': 66194, 'answer': 'Dazzle', 'question': 'Stacked Style makes 2 fragrances that rhyme: Razzle & this one', 'value': 400, 'airdate': '2005-02-07T12:00:00.000Z', 'created_at': '2014-02-11T23:28:38.100Z', 'updated_at': '2014-02-11T23:28:38.100Z', 'category_id': 8557, 'game_id': None, 'invalid_count': None, 'category': {'id': 8557, 'title': 'makes scents to me!', 'created_at': '2014-02-11T23:28:37.791Z', 'updated_at': '2014-02-11T23:28:37.791Z', 'clues_count': 5}}, {'id': 66200, 'answer': 'apple', 'question': "Dolce & Gabbana's light blue perfume smells like bluebell, bamboo & the Granny Smith type of this", 'value': 600, 'airdate': '2005-02-07T12:00:00.000Z', 'created_at': '2014-02-11T23:28:38.250Z', 'updated_at': '2014-02-11T23:28:38.250Z', 'category_id': 8557, 'game_id': None, 'invalid_count': None, 'category': {'id': 8557, 'title': 'makes scents to me!', 'created_at': '2014-02-11T23:28:37.791Z', 'updated_at': '2014-02-11T23:28:37.791Z', 'clues_count': 5}}, {'id': 66206, 'answer': 'Jessica Simpson', 'question': "Taste is this singer's own personal fragrance creation for her Dessert Beauty line", 'value': 800, 'airdate': '2005-02-07T12:00:00.000Z', 'created_at': '2014-02-11T23:28:38.447Z', 'updated_at': '2014-02-11T23:28:38.447Z', 'category_id': 8557, 'game_id': None, 'invalid_count': None, 'category': {'id': 8557, 'title': 'makes scents to me!', 'created_at': '2014-02-11T23:28:37.791Z', 'updated_at': '2014-02-11T23:28:37.791Z', 'clues_count': 5}}, {'id': 66212, 'answer': 'Burberry', 'question': "Bottles of this company's Brit perfume feature its famous plaid pattern", 'value': 1000, 'airdate': '2005-02-07T12:00:00.000Z', 'created_at': '2014-02-11T23:28:38.604Z', 'updated_at': '2018-08-02T10:05:26.843Z', 'category_id': 8557, 'game_id': None, 'invalid_count': 1, 'category': {'id': 8557, 'title': 'makes scents to me!', 'created_at': '2014-02-11T23:28:37.791Z', 'updated_at': '2014-02-11T23:28:37.791Z', 'clues_count': 5}}]}
    # new_board = []
    # for i, key in enumerate(board):
    #     new_board.append({key:[]})
    #     for arr in board[key]:
    #         new_board[i][key].append({'id':arr['id'], 'value':arr['value'], 'question':arr['question'], 'answer':arr['answer'], 'answered':False})
    
    new_board = [{'tv through the years': [{'id': 28455, 'value': 200, 'question': 'Ray Walston played an inventive alien stranded on Earth in this 1960s TV sitcom hit', 'answer': '<i>My Favorite Martian</i>', 'answered': False}, {'id': 28467, 'value': 400, 'question': '"JAG"\'s David James Elliott starred in the TV series version of this 1987 film that starred Kevin Costner', 'answer': '<i>The Untouchables</i>', 'answered': False}, {'id': 128404, 'value': 600, 'question': 'Omar, played by Michael K. Williams, relieved Baltimore drug dealers of their profits on this HBO drama debuting in 2002', 'answer': '<i>The Wire</i>', 'answered': False}, {'id': 128410, 'value': 800, 'question': '"I kid you not" was the catchphrase of this "Tonight Show" host before Johnny Carson', 'answer': 'Jack Paar', 'answered': False}, {'id': 128416, 'value': 1000, 'question': "That's Morty the moose, not star Rob Morrow, in the opening credits of this Alaska-set '90s show", 'answer': '<i>Northern Exposure</i>', 'answered': False}]}, {'dinosaurs': [{'id': 62436, 'value': 200, 'question': 'This dinosaur "king" could run as fast as 25 MPH & recent evidence suggests it was warm-blooded', 'answer': 'the <i>Tyrannosaurus rex</i>', 'answered': False}, {'id': 63880, 'value': 400, 'question': 'Scientists believe that dinosaurs lived through 3 geologic periods: Triassic, Jurassic, then this next one', 'answer': 'Cretaceous', 'answered': False}, {'id': 62448, 'value': 600, 'question': 'One theory says the triangular plates on its back helped control body temperature; another says they attracted mates', 'answer': 'the <i>Stegosaurus</i>', 'answered': False}, {'id': 62454, 'value': 800, 'question': 'Made famous by "Jurassic Park", this 6-foot-long "swift robber" had a "killing claw" on each foot', 'answer': 'a <i>Velociraptor</i>', 'answered': False}, {'id': 63898, 'value': 1000, 'question': 'Similar to an Apatosaurus, this 52\'-tall herbivore whose name means "arm lizard" had longer forelegs than hindlegs', 'answer': 'Brachiosaurus', 'answered': False}]}, {"in black's law dictionary": [{'id': 99428, 'value': 200, 'question': '"The malicious burning of someone else\'s dwelling house or outhouse" (glad the outhouse is protected, too)', 'answer': 'arson', 'answered': False}, {'id': 99434, 'value': 400, 'question': '"The fact of having or holding property in one\'s power" (it\'s not 9/10 of Black\'s, it\'s only 1 entry)', 'answer': 'possession', 'answered': False}, {'id': 99440, 'value': 600, 'question': 'This 3-word term is an "unpreventable event caused exclusively by forces of nature"', 'answer': 'act of God', 'answered': False}, {'id': 99446, 'value': 800, 'question': '"An accused person\'s formal response... to a criminal charge"', 'answer': 'a plea', 'answered': False}, {'id': 99452, 'value': 1000, 'question': '"The initial step in... prosecution whereby the defendant is brought before the court to hear the charges"', 'answer': 'an arraignment', 'answered': False}]}, {'dear john': [{'id': 71346, 'value': 200, 'question': "He was Tony Blair's immediate predecessor as prime minister", 'answer': 'John Major', 'answered': False}, {'id': 71352, 'value': 400, 'question': 'He once said, "I don\'t smoke much, and I drink very little.  I guess my only bad habit is robbing banks"', 'answer': 'John Dillinger', 'answered': False}, {'id': 71358, 'value': 600, 'question': 'This man at whose mill gold was discovered in 1848 later ran for governor of California', 'answer': '(John) Sutter', 'answered': False}, {'id': 71364, 'value': 800, 'question': 'In 1946 he gave the United Nations a gift of $8.5 million to buy land for its NYC headquarters', 'answer': '(John D.) Rockefeller', 'answered': False}, {'id': 71370, 'value': 1000, 'question': 'This author of the novel "Falconer" won a 1979 Pulitzer Prize for some of his short stories', 'answer': 'John Cheever', 'answered': False}]}, {'makes scents to me!': [{'id': 66188, 'value': 200, 'question': "Perfect for Valentine's Day, Fiorucci Loves You comes in a bottle shaped like one of these pierced with an arrow", 'answer': 'a heart', 'answered': False}, {'id': 66194, 'value': 400, 'question': 'Stacked Style makes 2 fragrances that rhyme: Razzle & this one', 'answer': 'Dazzle', 'answered': False}, {'id': 66200, 'value': 600, 'question': "Dolce & Gabbana's light blue perfume smells like bluebell, bamboo & the Granny Smith type of this", 'answer': 'apple', 'answered': False}, {'id': 66206, 'value': 800, 'question': "Taste is this singer's own personal fragrance creation for her Dessert Beauty line", 'answer': 'Jessica Simpson', 'answered': False}, {'id': 66212, 'value': 1000, 'question': "Bottles of this company's Brit perfume feature its famous plaid pattern", 'answer': 'Burberry', 'answered': False}]}]

    # print(new_board)

    gv.room_list[room_id] = Room()
    gv.room_list[room_id].name = room_name
    gv.room_list[room_id].room_id = room_id
    gv.room_list[room_id].board = new_board
    gv.room_list[room_id].room_owner = gv.connected_users[access_token]['auth0_code']

    gv.room_list[room_id].save_new_board()
    
    gv.conn.commit()
    return jsonify({"room_id":room_id})

@app.route('/api/roomlist/getboard', methods=['GET'])
@cross_origin(allow_headers=['authorization', 'content-type', 'room_id'], allow_methods=['GET, OPTIONS'])
@gv.auth.auth_required(request)
def get_board():
    access_token = gv.auth.get_token_auth_header(request)
    room_id = int(request.headers['room_id'])
    try:
        board = gv.room_list[room_id].board
    except:
        print('except')
        gv.cur.execute("SELECT board_id, room_name, player1, player1score, player2, player2score, player3, player3score, started FROM rooms WHERE room_id = %s",(room_id,))
        board_id, room_name, player1, player1score, player2, player2score, player3, player3score, started = gv.cur.fetchone()
        
        gv.room_list[room_id] = Room()
        gv.room_list[room_id].players[1]['auth0_code'] = player1
        gv.room_list[room_id].players[1]['score'] = player1score
        gv.room_list[room_id].players[2]['auth0_code'] = player2
        gv.room_list[room_id].players[2]['score'] = player2score
        gv.room_list[room_id].players[3]['auth0_code'] = player3
        gv.room_list[room_id].players[3]['score'] = player3score

        gv.room_list[room_id].name = room_name
        gv.room_list[room_id].room_id = room_id
        gv.room_list[room_id].started = started
        try:
            gv.room_list[room_id].room_owner = gv.connected_users[access_token]['auth0_code']
        except:
            del gv.room_list[room_id]
            return jsonify({'board':'board'})
    

        board = []
        gv.cur.execute("SELECT * FROM boards WHERE board_id = %s", (board_id,))
        cats = gv.cur.fetchone()[1:]
        for i, cat in enumerate(cats):
            gv.cur.execute("SELECT * FROM categories WHERE cat_id = %s", (cat,))
            curr_cat = gv.cur.fetchone()[1:]
            board.append({curr_cat[0]:[]})
            for clue in curr_cat[1:]:
                gv.cur.execute("SELECT * FROM clues WHERE clue_id = %s", (clue,))
                curr_clue = gv.cur.fetchone()[1:]
                board[i][curr_cat[0]].append({ 'id':curr_clue[0], 'question':curr_clue[1], 'answer':curr_clue[2], 'value':curr_clue[3], 'answered':curr_clue[4]})
        gv.room_list[room_id].board = board
        
    return jsonify({'board': board})