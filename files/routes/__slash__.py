from flask import Flask, current_app as app

@app.route('/')
def index():
    return "<a href='https://Jeopardy.MattFisher.ca'>Jeopardy</a>"