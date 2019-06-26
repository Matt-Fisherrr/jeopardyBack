from flask import Flask
from flask_socketio import SocketIO
import psycopg2, os
from flask_cors import CORS

app = Flask(__name__, static_folder="build/static", template_folder="build")
app.secret_key = 'app secret key'
# CORS(app)
socketio = SocketIO(app, async_mode='eventlet')




if __name__ == '__main__':
    with app.app_context():
        from files.auth import Auth
        from files.global_vars import global_variables
        global_vars = global_variables()
        import files.routes
        from files.socketControl import jeopardy_socket
    
    socketio.run(app, debug=True, host='0.0.0.0', port=os.environ['PORT'])














#old imports

# from flask import Flask, request, jsonify, render_template, send_from_directory
# 
# from flask_socketio import SocketIO, Namespace, emit, join_room, leave_room, close_room, rooms, disconnect
# from threading import Lock
# from jose import jwt


# from fuzzywuzzy import fuzz
# import json, os, hashlib, requests, random, datetime, copy, re, psycopg2