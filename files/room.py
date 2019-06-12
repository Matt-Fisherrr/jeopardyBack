# import files.global_vars as gv
from threading import Lock
from main import global_vars as gv

class Room():
    def __init__(self):
        # Basic information
        self.name = ''
        self.room_id = 0

        # Board related information
        self.board = {}
        self.started = 0
        self.screen_clicked = ''
        self.selected_time = None
        self.answer_count = 0
        self.answer_timer = None
        self.thread_answer_timer = Lock()

        # Players
        self.active_player = 0
        self.room_owner = ''
        self.players = {
            1: {
                'auth0_code': '',
                'username':'',
                'score': 0,
                'ping': [],
                'ready': False
            },
            2: {
                'auth0_code': '',
                'username':'',
                'score': 0,
                'ping': [],
                'ready': False
            },
            3: {
                'auth0_code': '',
                'username':'',
                'score': 0,
                'ping': [],
                'ready': False
            }
        }
        self.player_counts = {
            'count': 0,
            'total_count': 0,
            'ready_count': 0
        }

        #Buzz in related
        self.buzzedIn = 0
        self.buzz_background = None
        self.thread_lock_buzz_background = Lock()
        self.buzzed_in_back = None
        self.thread_lock_buzzed_in_back = Lock()
        self.buzzable_players = []
        self.buzzedPlayerTimes = {
            1: '',
            2: '',
            3: ''
        }

        # Viewers
        self.viewers = []

    def save_new_board(self):
        cat_id = []
        for column in self.board:
            for title in column:
                clue_id = []
                for clue in column[title]:
                    gv.cur.execute("INSERT INTO clues(api_id, question, answer, value, answered) VALUES (%s, %s, %s, %s, FALSE) RETURNING clue_id", (clue['id'], clue['question'], clue['answer'], clue['value']))
                    clue_id.append(gv.cur.fetchone()[0])
            gv.cur.execute("INSERT INTO categories(cat_name, clue_one, clue_two, clue_three, clue_four, clue_five) VALUES (%s, %s, %s, %s, %s, %s) RETURNING cat_id", (title, clue_id[0], clue_id[1], clue_id[2], clue_id[3], clue_id[4]))
            cat_id.append(gv.cur.fetchone()[0])
        gv.cur.execute("INSERT INTO boards(cat_one, cat_two, cat_three, cat_four, cat_five) VALUES (%s, %s, %s, %s, %s) RETURNING board_id", (cat_id[0], cat_id[1], cat_id[2], cat_id[3], cat_id[4]))
        board_id = gv.cur.fetchone()[0]
        gv.cur.execute("UPDATE rooms SET board_id=%s WHERE room_id = %s", (board_id, self.room_id))
        gv.conn.commit()

    def get_players(self):
        players = {}
        for num in range(1,4):
            self.players[num]['score']
            if self.players[num]['username'] == '':
                gv.cur.execute("SELECT username FROM players WHERE auth0_code = %s",(self.players[num]['auth0_code'],))
                try:
                    username = gv.cur.fetchone()[0]
                    self.players[num]['username'] = username
                    players[num] = {
                        'username':username,
                        'score':self.players[num]['score'],
                        'ready':self.players[num]['ready']
                    }
                except Exception as e:
                    players[num] = {
                        'username':'',
                        'score':0,
                        'ready':False
                    }
            else:
                players[num] = {
                    'username':self.players[num]['username'],
                    'score':self.players[num]['score'],
                    'ready':self.players[num]['ready']
                    }
        return players
