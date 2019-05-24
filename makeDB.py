import psycopg2
import os

conn = psycopg2.connect(dbname=os.environ['DBNAME'], user=os.environ['USER'], password=os.environ['PASSWORD'], host=os.environ['HOST'])
cur = conn.cursor()

cur.execute("DROP TABLE players")

cur.execute("""CREATE TABLE players(
  player_id SERIAL PRIMARY KEY,
  username TEXT NOT NULL,
  auth0_code TEXT NOT NULL
);""")

cur.execute("DROP TABLE rooms")

cur.execute("""CREATE TABLE rooms(
  room_id SERIAL PRIMARY KEY,
  room_name TEXT NOT NULL,
  player1 TEXT,
  player1value INT,
  player2 TEXT,
  player2value INT,
  player3 TEXT,
  player3value INT,
  board TEXT NOT NULL,
  started INT NOT NULL,
  complete INT NOT NULL
);""")



conn.commit()

cur.close()
conn.close()