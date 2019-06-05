import psycopg2
import os

conn = psycopg2.connect(dbname=os.environ['DBNAME'], user=os.environ['USER'], password=os.environ['PASSWORD'], host=os.environ['HOST'])
cur = conn.cursor()

cur.execute("DROP TABLE IF EXISTS players")

cur.execute("""CREATE TABLE players(
  player_id SERIAL PRIMARY KEY,
  username TEXT NOT NULL,
  auth0_code TEXT NOT NULL
);""")

cur.execute("DROP TABLE IF EXISTS rooms")

cur.execute("""CREATE TABLE rooms(
  room_id SERIAL PRIMARY KEY,
  room_name TEXT NOT NULL,
  player1 TEXT,
  player1value INT,
  player2 TEXT,
  player2value INT,
  player3 TEXT,
  player3value INT,
  board_id INT,
  started INT NOT NULL,
  complete INT NOT NULL
);""")

cur.execute("DROP TABLE IF EXISTS boards")

cur.execute("""CREATE TABLE boards(
  board_id SERIAL PRIMARY KEY,
  cat_one INT NOT NULL,
  cat_two INT NOT NULL,
  cat_three INT NOT NULL,
  cat_four INT NOT NULL,
  cat_five INT NOT NULL
);""")

cur.execute("DROP TABLE IF EXISTS categories")

cur.execute("""CREATE TABLE categories(
  cat_id SERIAL PRIMARY KEY,
  cat_name TEXT NOT NULL,
  clue_one INT NOT NULL,
  clue_two INT NOT NULL,
  clue_three INT NOT NULL,
  clue_four INT NOT NULL,
  clue_five INT NOT NULL
);""")

cur.execute("DROP TABLE IF EXISTS clues")

cur.execute("""CREATE TABLE clues(
  clue_id SERIAL PRIMARY KEY,
  clue_api_id INT NOT NULL,
  clue_question TEXT NOT NULL,
  clue_answer TEXT NOT NULL,
  clue_value INT NOT NULL
)
""")


conn.commit()

cur.close()
conn.close()