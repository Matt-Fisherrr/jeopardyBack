from threading import Lock
from flask_socketio import SocketIO, Namespace, emit, join_room, leave_room, close_room, rooms, disconnect
# import files.global_vars as gv
from flask import current_app as app, request
from fuzzywuzzy import fuzz
import datetime, re, json

from __main__ import global_vars as gv
from __main__ import socketio

# Check the ping of all players every 10 seconds
ping_list = {}
thread = None
thread_lock = Lock()
def ping_check():
    global socketio, ping_list
    ping_count = 0
    while True:
        socketio.sleep(10)
        ping_list[ping_count] = datetime.datetime.now()
        socketio.emit('ping_check', {'ping_num':ping_count}, room='players', namespace='/jep')
        ping_count = ping_count + 1

# Wait 3 seconds before the buzz in button appears, simulates Trebek reading the question
def buzzIn(room_id):
    socketio.sleep(3)
    socketio.emit('buzzable', {'buzz':True, 'buzzable_players':gv.room_list[room_id].buzzable_players}, room=str(room_id), namespace='/jep')

# Waits 7 seconds for anyone to buzz in
def buzzBackground(args):
    try:
        room_id = args['room_id']
        catclue = args['screen_clicked']
        socketio.sleep(7)
        if gv.room_list[room_id].buzzedIn == 0:
            gv.room_list[room_id].buzzable_players = []
            category_num, clue = map(int,catclue.split('|'))
            category_name = list(gv.room_list[room_id].board[category_num].keys())[0]
            gv.room_list[room_id].answer_count += 1
            if gv.room_list[room_id].answer_count > 25:
                calculate_winner(room_id)
            socketio.emit('no_buzz', { 'screen_clicked':catclue}, room=str(room_id), namespace='/jep')
            socketio.emit('no_correct_answer', { 'position':gv.room_list[room_id].active_player, 'answer': gv.room_list[room_id].board[category_num][category_name][clue]['answer']}, room=str(room_id), namespace='/jep')
    except Exception as e:
        print(e)
        emit('error',{}, room=str(room_id), namespace='/jep')

# Waits 2 seconds for latency reasons before calculating who buzzed fastest
def buzz_in_background(room_id):
    if len(gv.room_list[room_id].buzzable_players) > 1:
        socketio.sleep(2)
    lowest_time = 99999999999999999
    lowest_player = ''
    for player in gv.room_list[room_id].buzzedPlayerTimes:
        if gv.room_list[room_id].buzzedPlayerTimes[player] != '':
            if gv.room_list[room_id].buzzedPlayerTimes[player] < lowest_time:
                lowest_time = gv.room_list[room_id].buzzedPlayerTimes[player]
                lowest_player = player
    gv.room_list[room_id].buzzedIn = lowest_player
    del gv.room_list[room_id].buzzable_players[gv.room_list[room_id].buzzable_players.index(lowest_player)]
    socketio.emit('fastest_buzz', {'buzzedIn':gv.room_list[room_id].buzzedIn}, room=str(room_id), namespace='/jep')
    thread_answer_timer = Lock()
    gv.room_list[room_id].answer_timer = None
    with thread_answer_timer:
        if gv.room_list[room_id].answer_timer == None:
            gv.room_list[room_id].answer_timer = socketio.start_background_task(answer_timer,room_id)

# Waits 7 seconds for fastest buzzer to type then gets anything they typed in
def answer_timer(room_id):
    try:
        pos = gv.room_list[room_id].buzzedIn
        question = gv.room_list[room_id].screen_clicked
        socketio.sleep(7)
        if gv.room_list[room_id].buzzedIn == pos and question == gv.room_list[room_id].screen_clicked:
            socketio.emit('take_too_long', {}, room=str(room_id), namespace='/jep')
    except Exception as e:
        print(e)
        emit('error',{}, room=str(room_id), namespace='/jep')

# Figure out who has the highest score after the board is cleared
def calculate_winner(room_id):
    highest_score = -99999999999
    highest_player = ''
    for player in gv.room_list[room_id].players:
        if gv.room_list[room_id].players[player]['username'] != '':
            if gv.room_list[room_id].players[player]['score'] > highest_score:
                highest_score = gv.room_list[room_id].players[player]['score']
                highest_player = gv.room_list[room_id].players[player]['username']
            elif gv.room_list[room_id].players[player]['score'] == highest_score:
                highest_player = [highest_player, gv.room_list[room_id].players[player]['username']]
    gv.cur.execute("UPDATE rooms SET complete=1 WHERE room_id=%s",(room_id,))
    gv.conn.commit()
    print(highest_player)
    socketio.emit('winner', {'username':highest_player}, room=str(room_id), namespace='/jep')

# Runs the 3 second timer before buzzing in available, then 7 second timer to buzz in
def screen_timer(room_id):
    gv.room_list[room_id].thread_lock_buzzed_in_back = Lock()
    with gv.room_list[room_id].thread_lock_buzzed_in_back:
        socketio.start_background_task(buzzIn,room_id)
        gv.room_list[room_id].buzzed_in_back = None
        gv.room_list[room_id].buzz_background = None
        gv.room_list[room_id].buzzedIn = 0
        gv.room_list[room_id].selected_time = datetime.datetime.now()
        gv.room_list[room_id].buzz_background = socketio.start_background_task(buzzBackground,{'room_id':room_id, 'screen_clicked':gv.room_list[room_id].screen_clicked})

# Uses fuzzing to check the answer that is typed in
def check_answer(answer, real_answer):
    ratio = fuzz.ratio(re.sub(r'[^A-Za-z0-9\s]','',answer.lower()), re.sub(r'[^A-Za-z0-9\s]','',real_answer.lower()))
    token_sort = fuzz.token_sort_ratio(re.sub(r'[^A-Za-z0-9\s]','',answer.lower()), re.sub(r'[^A-Za-z0-9\s]','',real_answer.lower()))
    token_set = fuzz.token_set_ratio(re.sub(r'[^A-Za-z0-9\s]','',answer.lower()), re.sub(r'[^A-Za-z0-9\s]','',real_answer.lower()))

    print_answer = re.sub(r'[^A-Za-z0-9\s]','',answer.lower())
    print_real_answer = re.sub(r'[^A-Za-z0-9\s]','',real_answer.lower())
    
    # print(fuzz.ratio(re.sub(r'[^A-Za-z0-9\s]','',match), re.sub(r'[^A-Za-z0-9\s]','',real_answer)))
    # print(fuzz.partial_ratio(re.sub(r'[^A-Za-z0-9\s]','',answer.lower()), re.sub(r'[^A-Za-z0-9\s]','',real_answer.lower())))
    # print(fuzz.token_sort_ratio(re.sub(r'[^A-Za-z0-9\s]','',match), re.sub(r'[^A-Za-z0-9\s]','',real_answer)))
    # print(fuzz.token_set_ratio(re.sub(r'[^A-Za-z0-9\s]','',match), re.sub(r'[^A-Za-z0-9\s]','',real_answer)))
    print(f"{print_answer} | {print_real_answer} | ratio: {ratio}%, sort: {token_sort}%, set: {token_set}% = {(ratio + token_sort + token_set) // 3}")
    # print(len(re.sub(r'[^A-Za-z0-9\s]','',match)) / len(re.sub(r'[^A-Za-z0-9\s]','',real_answer)) * 100)
    return (ratio + token_sort + token_set) // 3 > 50 and (ratio == 100 or token_sort == 100 or token_set == 100)

class jeopardy_socket(Namespace):

    # Take ping respone and add it to the players ping array
    def on_pong_res(self, message):
        room_id = gv.req_ids[request.sid]['room_id']
        pos = gv.req_ids[request.sid]['player_num']
        diff = datetime.datetime.now() - ping_list[message['ping_num']]
        ping = round((diff.microseconds / 10**6 + diff.seconds) * 1000)
        gv.room_list[room_id].players[pos].get('ping',[]).append(ping) 

    # Starts the ping check if it isn't already
    def on_connect(self):
        global thread
        with thread_lock:
            if thread is None:
                thread = socketio.start_background_task(ping_check)

    # Clears the room if the room is empty and clears the player cache
    def on_disconnect(self):
        room_id = gv.req_ids[request.sid]['room_id']
        username = gv.req_ids[request.sid]['username']
        print(gv.req_ids[request.sid]['username'] + ' disconnected from room ' + str(room_id))
        if gv.req_ids[request.sid].get('player_num', 0) != 0:
            gv.room_list[room_id].player_counts['count'] = gv.room_list[room_id].player_counts['count'] - 1
        if username in gv.room_list[room_id].viewers:
            del gv.room_list[room_id].viewers[gv.room_list[room_id].viewers.index(username)]
        if gv.room_list[room_id].player_counts['count'] == 0 and len(gv.room_list[room_id].viewers) == 0:
            print('closed room ' + str(room_id))
            del gv.room_list[room_id]
        del gv.connected_users[gv.req_ids[request.sid]['access_token']]
        del gv.req_ids[request.sid]

    # Sends player info and sets the player position if they were already in the room
    def on_join_room(self,message):
        try:
            # print(gv.req_ids)
            room_id = message['room_id']
            access_token = message['access_token']
            gv.req_ids[request.sid] = gv.connected_users[access_token]

            join_room(str(room_id))

            gv.room_list[room_id].viewers.append(gv.req_ids[request.sid]['username'])
            gv.req_ids[request.sid]['sid'] = request.sid
            gv.req_ids[request.sid]['room_id'] = room_id

            gv.cur.execute("SELECT player_id FROM players WHERE auth0_code = %s",(gv.req_ids[request.sid]['auth0_code'],))
            gv.req_ids[request.sid]['player_id'] = gv.cur.fetchone()[0]

            for num in gv.room_list[room_id].players:
                if gv.room_list[room_id].players[num]['auth0_code'] == gv.req_ids[request.sid]['auth0_code']:
                    gv.req_ids[request.sid]['player_num'] = num
                    gv.room_list[room_id].player_counts['count'] += 1

            # print(gv.req_ids)
            
            emit('has_joined_room', { 
                'players':gv.room_list[room_id].get_players(), 
                'position':gv.req_ids[request.sid].get('player_num',0), 
                'player_id':gv.req_ids[request.sid]['player_id'],
                'started': gv.room_list[room_id].started,
                'active_player':gv.room_list[room_id].active_player
                }
            )

        except Exception as e:
            print(e)
            emit('error')

    # Broadcasts the number of viewers
    def on_viewer_joined(self):
        room_id = gv.req_ids[request.sid]['room_id']
        emit('viewer_added', { 'viewers':len(gv.room_list[room_id].viewers)}, room=str(room_id))

    # Checks there is no one in the palyer slot and broadcasts player joining and position
    def on_player_select(self,message):
        # print(gv.req_ids)
        position = message['position']
        room_id = gv.req_ids[request.sid]['room_id']
        auth0_code = gv.req_ids[request.sid]['auth0_code']
        
        if gv.req_ids[request.sid].get('player_num',None) == None:
            if gv.room_list[room_id].players[position]['username'] == "" and gv.room_list[room_id].started == 0:
                gv.room_list[room_id].viewers.remove(gv.req_ids[request.sid]['username'])
                join_room('players')
                gv.room_list[room_id].players[position]['auth0_code'] = auth0_code
                gv.cur.execute("SELECT username FROM players WHERE auth0_code = %s",(gv.room_list[room_id].players[position].get('auth0_code','0'),))
                gv.room_list[room_id].players[position]['username'] = gv.cur.fetchone()[0]
                gv.req_ids[request.sid]['player_num'] = position
                gv.room_list[room_id].player_counts['count'] = gv.room_list[room_id].player_counts.get('count',0) + 1
                gv.room_list[room_id].player_counts['total_count'] = gv.room_list[room_id].player_counts.get('total_count',0) + 1
                emit('player_selected',{'username':gv.req_ids[request.sid]['username'], 'position':position, 'player_id':gv.req_ids[request.sid]['player_id']}, room=str(room_id))
                if position == 1:
                    gv.cur.execute("UPDATE rooms SET player1=%s, player1score=%s WHERE room_id=%s",(gv.req_ids[request.sid]['auth0_code'],0,room_id))
                elif position == 2:
                    gv.cur.execute("UPDATE rooms SET player2=%s, player2score=%s WHERE room_id=%s",(gv.req_ids[request.sid]['auth0_code'],0,room_id))
                elif position == 3:
                    gv.cur.execute("UPDATE rooms SET player3=%s, player3score=%s WHERE room_id=%s",(gv.req_ids[request.sid]['auth0_code'],0,room_id))
                gv.conn.commit()

    # Broad casts if player is ready and checks if all players are ready
    def on_player_ready(self, message):
        room_id = gv.req_ids[request.sid]['room_id']
        pos = gv.req_ids[request.sid]['player_num']
        if gv.room_list[room_id].players[pos].get('ready',False) == False:
            gv.room_list[room_id].players[pos]['ready'] = True
            gv.room_list[room_id].player_counts['ready_count'] = gv.room_list[room_id].player_counts['ready_count'] + 1
        else:
            gv.room_list[room_id].players[pos]['ready'] = False
            gv.room_list[room_id].player_counts['ready_count'] = gv.room_list[room_id].player_counts['ready_count'] - 1
        if gv.room_list[room_id].player_counts['ready_count'] == gv.room_list[room_id].player_counts['count']:
            gv.room_list[room_id].started = 1
            for pos in gv.room_list[room_id].players:
                print(pos,gv.room_list[room_id].players[pos]['auth0_code'])
                if gv.room_list[room_id].players[pos]['auth0_code'] != "":
                    gv.room_list[room_id].active_player = pos
                    break
            emit('ready_player', { 'position':pos,'ready':gv.room_list[room_id].players[pos]['ready'], 'started': gv.room_list[room_id].started, 'active_player': gv.room_list[room_id].active_player}, room=str(room_id))
            gv.cur.execute("UPDATE rooms SET started=1, activate_player=%s WHERE room_id=%s",(gv.room_list[room_id].active_player, room_id))
            gv.conn.commit()
        else:
            emit('ready_player', { 'position':pos,'ready':gv.room_list[room_id].players[pos]['ready'], 'started': gv.room_list[room_id].started}, room=str(room_id))

    # Checks if active player selected a screen and broadcasts the screen selected
    def on_screen_select(self, message):
        room_id = gv.req_ids[request.sid]['room_id']
        screen_clicked = message['screen_clicked']
        # print(gv.room_list[room_id].player_counts['count'],gv.room_list[room_id].player_counts['total_count'])
        if gv.req_ids[request.sid]['player_num'] == gv.room_list[room_id].active_player and gv.room_list[room_id].player_counts['count'] == gv.room_list[room_id].player_counts['total_count']:
            gv.room_list[room_id].screen_clicked = screen_clicked
            category_num, clue = map(int,gv.room_list[room_id].screen_clicked.split('|'))
            category_name = list(gv.room_list[room_id].board[category_num].keys())[0]
            if gv.room_list[room_id].board[category_num][category_name][clue]['answered'] == False:
                gv.room_list[room_id].board[category_num][category_name][clue]['answered'] = True
                gv.room_list[room_id].buzzable_players = []
                for pos in gv.room_list[room_id].players:
                    if pos == 1 or pos == 2 or pos == 3:
                        if gv.room_list[room_id].players[pos]['username'] != '':
                            gv.room_list[room_id].buzzable_players.append(pos)
                gv.room_list[room_id].selected_board = gv.room_list[room_id].screen_clicked
                gv.room_list[room_id].buzzedPlayerTimes = {1:'',2:'',3:''}
                emit('screen_selected', { 'category':category_num, 'clue':clue, 'screen_text': gv.room_list[room_id].board[category_num][category_name][clue]['question'], 'active_player':0, 'x_and_y':message['x_and_y']}, room=str(room_id))
                gv.cur.execute("UPDATE clues SET answered=True WHERE api_id=%s", (gv.room_list[room_id].board[category_num][category_name][clue]['id'],))
                gv.conn.commit()
                # print(gv.room_list[room_id].board[category_num][category_name][clue])
                screen_timer(room_id)

    # Adds players buzz in time and starts countdown for laggy player buzzes
    def on_buzz_in(self):
        room_id = gv.req_ids[request.sid]['room_id']
        pos = gv.req_ids[request.sid]['player_num']

        if pos in gv.room_list[room_id].buzzable_players:
            gv.room_list[room_id].buzzedIn = pos
            now = gv.room_list[room_id].selected_time
            diff = (datetime.datetime.now() - now)
            diff = round((diff.microseconds / 10**6 + diff.seconds) * 1000)
            try:
                gv.room_list[room_id].buzzedPlayerTimes[pos] = diff - (sum(gv.room_list[room_id]['players'][pos].get('ping',[])) / len(gv.room_list[room_id]['players'][pos].get('ping',[])))
            except:
                gv.room_list[room_id].buzzedPlayerTimes[pos] = diff

            with gv.room_list[room_id].thread_lock_buzz_background:
                if gv.room_list[room_id].buzzed_in_back == None:
                    gv.room_list[room_id].buzzed_in_back = socketio.start_background_task(buzz_in_background,room_id)

    # Broadcasts what buzzed in player types
    def on_answer_typed(self, message):
        room_id = gv.req_ids[request.sid]['room_id']
        if gv.req_ids[request.sid]['player_num'] == gv.room_list[room_id].buzzedIn:
            emit('typed_answer', {'answer_input':message['answer']}, room=str(room_id))

    # Checks the answer the player submitted and 
    # either: 
    #   Gives the other players the option to buzz in
    #   Ends the screen if all players have already buzzed in
    def on_answer_submit(self, message):
        room_id = gv.req_ids[request.sid]['room_id']
        answer = message['answer']
        pos = gv.req_ids[request.sid]['player_num']

        if gv.room_list[room_id].buzzedIn == gv.req_ids[request.sid]['player_num']:
            gv.room_list[room_id].buzzedIn = 0

            category_num, clue = map(int,gv.room_list[room_id].selected_board.split('|'))
            category_name = list(gv.room_list[room_id].board[category_num].keys())[0]

            real_answer = re.sub(r'<.+?>','',gv.room_list[room_id].board[category_num][category_name][clue]['answer'])
            real_answer = re.sub(r'(?<=\b)(the|a|an)\s?(?=\b)','',real_answer)

            if check_answer(answer, real_answer):
                gv.room_list[room_id].answer_count = gv.room_list[room_id].answer_count + 1
                if gv.room_list[room_id].answer_count > 25:
                    calculate_winner(room_id)
                else:
                    gv.room_list[room_id].players[pos]['score'] = gv.room_list[room_id].players[pos]['score'] + gv.room_list[room_id].board[category_num][category_name][clue]['value']
                    gv.room_list[room_id].active_player = pos
                    emit('answer_response', { 'correct':True, 'position': pos, 'new_score': gv.room_list[room_id].players[pos]['score'] }, room=str(room_id))
                    gv.cur.execute("UPDATE rooms SET player1score=%s, player2score=%s, player3score=%s, activate_player=%s WHERE room_id=%s", (gv.room_list[room_id].players[1]['score'], gv.room_list[room_id].players[2]['score'], gv.room_list[room_id].players[3]['score'], gv.room_list[room_id].active_player, room_id))
                    gv.conn.commit()
            else:
                gv.room_list[room_id].players[pos]['score'] = gv.room_list[room_id].players[pos]['score'] - gv.room_list[room_id].board[category_num][category_name][clue]['value']
                emit('answer_response', { 'correct':False, 'position': pos, 'new_score':gv.room_list[room_id].players[pos]['score'], 'buzzable_players':gv.room_list[room_id].buzzable_players }, room=str(room_id))
                gv.cur.execute("UPDATE rooms SET player1score=%s, player2score=%s,player3score=%s WHERE room_id=%s", (gv.room_list[room_id].players[1]['score'], gv.room_list[room_id].players[2]['score'], gv.room_list[room_id].players[3]['score'], room_id))
                gv.conn.commit()
                if len(gv.room_list[room_id].buzzable_players) == 0:
                    gv.room_list[room_id].answer_count = gv.room_list[room_id].answer_count + 1
                    if gv.room_list[room_id].answer_count > 25:
                        calculate_winner(room_id)
                    emit('no_buzz', { 'screen_clicked':gv.room_list[room_id].screen_clicked }, room=str(room_id))
                    emit('no_correct_answer', { 'position':gv.room_list[room_id].active_player, 'answer': gv.room_list[room_id].board[category_num][category_name][clue]['answer']}, room=str(room_id))
                else:
                    gv.room_list[room_id].buzzedPlayerTimes = {1:'',2:'',3:''}
                    screen_timer(room_id)


    # Socket test
    def on_test(self, message):
        print(message['data'])
        emit('test', {'test':'test'})
        

socketio.on_namespace(jeopardy_socket('/jep'))