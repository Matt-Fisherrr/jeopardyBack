from threading import Lock
from flask_socketio import SocketIO, Namespace, emit, join_room, leave_room, close_room, rooms, disconnect
# import files.global_vars as gv
from flask import current_app as app, request
from fuzzywuzzy import fuzz
import datetime, re, json

from main import global_vars as gv
from __main__ import socketio

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

def buzzIn(room_id):
    socketio.sleep(3)
    socketio.emit('buzzable', {'buzz':True, 'buzzable_players':gv.room_list[room_id].buzzable_players}, room=str(room_id), namespace='/jep')

def buzzBackground(args):
    try:
        room_id = args['room_id']
        catclue = args['screen_clicked']
        socketio.sleep(7)
        if gv.room_list[room_id].buzzedIn == 0:
            category_num, clue = map(int,catclue.split('|'))
            category_name = list(gv.room_list[room_id].board[category_num].keys())[0]
            gv.room_list[room_id].answer_count += 1
            if gv.room_list[room_id].answer_count >= 5:
                calculate_winner(room_id)
            socketio.emit('no_buzz', { 'screen_clicked':catclue}, room=str(room_id), namespace='/jep')
            socketio.emit('no_correct_answer', { 'position':gv.room_list[room_id].active_player, 'answer': gv.room_list[room_id].board[category_num][category_name][clue]['answer']}, room=str(room_id), namespace='/jep')
    except Exception as e:
        print(e)
        emit('error',{}, room=str(room_id), namespace='/jep')

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

def calculate_winner(room_id):
    highest_score = -99999999999
    highest_player = ''
    for player in gv.room_list[room_id].players:
        if player == 'one' or player == 'two' or player == 'three':
            if gv.room_list[room_id].players[player]['username'] != '':
                if gv.room_list[room_id].players[player]['score'] > highest_score:
                    highest_score = gv.room_list[room_id].players[player]['score']
                    highest_player = gv.room_list[room_id].players[player]['username']
                elif gv.room_list[room_id].players[player]['score'] == highest_score:
                    highest_player = [highest_player, gv.room_list[room_id].players[player]['username']]
    socketio.emit('winner', {'username':highest_player}, room=str(room_id), namespace='/jep')

def screen_timer(room_id):
    gv.room_list[room_id].thread_lock_buzzed_in_back = Lock()
    with gv.room_list[room_id].thread_lock_buzzed_in_back:
        socketio.start_background_task(buzzIn,room_id)
        gv.room_list[room_id].buzzed_in_back = None
        gv.room_list[room_id].buzz_background = None
        gv.room_list[room_id].buzzedIn = 0
        gv.room_list[room_id].selected_time = datetime.datetime.now()
        gv.room_list[room_id].buzz_background = socketio.start_background_task(buzzBackground,{'room_id':room_id, 'screen_clicked':gv.room_list[room_id].screen_clicked})

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

    def on_pong_res(self, message):
        room_id = gv.req_ids[request.sid]['room_id']
        pos = gv.req_ids[request.sid]['player_num']
        diff = datetime.datetime.now() - ping_list[message['ping_num']]
        ping = round((diff.microseconds / 10**6 + diff.seconds) * 1000)
        gv.room_list[room_id].players[pos].get('ping',[]).append(ping) 

    def on_connect(self):
        print('connect')
        global thread
        with thread_lock:
            if thread is None:
                thread = socketio.start_background_task(ping_check)

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

    def on_join_room(self,message):
        try:
            room_id = message['room_id']
            access_token = message['access_token']
            gv.req_ids[request.sid] = gv.connected_users[access_token]

            join_room(str(room_id))

            gv.room_list[room_id].viewers.append(gv.req_ids[request.sid]['username'])
            gv.req_ids[request.sid]['sid'] = request.sid
            gv.req_ids[request.sid]['room_id'] = room_id

            gv.cur.execute("SELECT player_id FROM players WHERE auth0_code = %s",(gv.req_ids[request.sid]['auth0_code'],))
            gv.req_ids[request.sid]['player_id'] = gv.cur.fetchone()[0]

            # if gv.room_list[room_id].get('started', False,) == False:
            #     gv.room_list[room_id]['active_player'] = 0
            # if gv.room_list[room_id].get('players',None) == None:
            #     gv.room_list[room_id]['players'] = gv.room_list[room_id].get('players',{})
            # gv.room_list[room_id]['players']['one'] = gv.room_list[room_id]['players'].get('one',{})
            # gv.room_list[room_id]['players']['two'] = gv.room_list[room_id]['players'].get('two',{})
            # gv.room_list[room_id]['players']['three'] = gv.room_list[room_id]['players'].get('three',{})
            # if gv.room_list[room_id].get('init', None) == None:
            #     for pos in gv.room_list[room_id]['players']:
            #         if pos == 'one' or pos == 'two' or pos == 'three':
            #             gv.room_list[gv.req_ids[request.sid]['room_id']]['players'][pos]['ping'] = []
            #             gv.cur.execute("SELECT username FROM players WHERE auth0_code = %s",(gv.room_list[room_id]['players'][pos].get('auth0_code','0'),))
            #             try:
            #                 gv.room_list[room_id]['players'][pos]['username'] = cur.fetchone()[0]
            #                 gv.room_list[room_id]['players'][pos]['score'] = 0
            #             except:
            #                 gv.room_list[room_id]['players'][pos]['username'] = ""
            #                 gv.room_list[room_id]['players'][pos]['score'] = 0
            #     gv.room_list[room_id]['init'] = True
            # room = json.loads(json.dumps(gv.room_list[room_id]))
            # for pos in room['players']:
            #     if pos == 'one' or pos == 'two' or pos == 'three':
            #         if room['players'][pos].get('auth0_code', None) != None:
            #             del room['players'][pos]['auth0_code']
            #             if gv.room_list[room_id]['players'][pos]['auth0_code'] == gv.req_ids[request.sid]['auth0_code']:
            #                 gv.req_ids[request.sid]['player_num'] = pos
            #                 gv.room_list[room_id]['viewers'].remove(gv.req_ids[request.sid]['username'])
            #                 gv.room_list[room_id]['players']['count'] = gv.room_list[room_id]['players']['count'] + 1
            #                 join_room('players')
            # print(gv.req_ids[request.sid])
            for num in gv.room_list[room_id].players:
                if gv.room_list[room_id].players[num]['auth0_code'] == gv.req_ids[request.sid]['auth0_code']:
                    gv.req_ids[request.sid]['player_num'] = num
                    gv.room_list[room_id].player_counts['count'] += 1
            
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

    def on_viewer_joined(self):
        room_id = gv.req_ids[request.sid]['room_id']
        emit('viewer_added', { 'viewers':len(gv.room_list[room_id].viewers)}, room=str(room_id))

    def on_player_select(self,message):
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
            gv.room_list[room_id].active_player = 1
            emit('ready_player', { 'position':pos,'ready':gv.room_list[room_id].players[pos]['ready'], 'started': gv.room_list[room_id].started, 'active_player': gv.room_list[room_id].active_player}, room=str(room_id))
        else:
            emit('ready_player', { 'position':pos,'ready':gv.room_list[room_id].players[pos]['ready'], 'started': gv.room_list[room_id].started}, room=str(room_id))

    def on_screen_select(self, message):
        room_id = gv.req_ids[request.sid]['room_id']
        screen_clicked = message['screen_clicked']
        if gv.req_ids[request.sid]['player_num'] == gv.room_list[room_id].active_player:
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
                screen_timer(room_id)

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

    def on_answer_typed(self, message):
        room_id = gv.req_ids[request.sid]['room_id']
        if gv.req_ids[request.sid]['player_num'] == gv.room_list[room_id].buzzedIn:
            emit('typed_answer', {'answer_input':message['answer']}, room=str(room_id))

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
                if gv.room_list[room_id].answer_count >= 5:
                    calculate_winner(room_id)
                else:
                    gv.room_list[room_id].players[pos]['score'] = gv.room_list[room_id].players[pos]['score'] + gv.room_list[room_id].board[category_num][category_name][clue]['value']
                    gv.room_list[room_id].active_player = pos
                    emit('answer_response', { 'correct':True, 'position': pos, 'new_score': gv.room_list[room_id].players[pos]['score'] }, room=str(room_id))
            else:
                gv.room_list[room_id].players[pos]['score'] = gv.room_list[room_id].players[pos]['score'] - gv.room_list[room_id].board[category_num][category_name][clue]['value']
                emit('answer_response', { 'correct':False, 'position': pos, 'new_score':gv.room_list[room_id].players[pos]['score'], 'buzzable_players':gv.room_list[room_id].buzzable_players }, room=str(room_id))
                if len(gv.room_list[room_id].buzzable_players) == 0:
                    gv.room_list[room_id].answer_count = gv.room_list[room_id].answer_count + 1
                    if gv.room_list[room_id].answer_count >= 5:
                        calculate_winner(room_id)
                    emit('no_buzz', { 'screen_clicked':gv.room_list[room_id].screen_clicked }, room=str(room_id))
                    emit('no_correct_answer', { 'position':gv.room_list[room_id].active_player, 'answer': gv.room_list[room_id].board[category_num][category_name][clue]['answer']}, room=str(room_id))
                else:
                    gv.room_list[room_id].buzzedPlayerTimes = {1:'',2:'',3:''}
                    screen_timer(room_id)



    def on_test(self, message):
        print(message['data'])
        emit('test', {'test':'test'})
        

socketio.on_namespace(jeopardy_socket('/jep'))