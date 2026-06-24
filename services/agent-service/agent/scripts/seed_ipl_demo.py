"""Seed the IPL SQLite demo database with consistent data."""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "resources/databases/sqlite/IPL/ipl.sqlite"

conn = sqlite3.connect(str(DB))
cur = conn.cursor()

for t in ["extra_runs","wicket_taken","batsman_scored","ball_by_ball","player_match","match","team","player"]:
    cur.execute(f"DELETE FROM {t}")

players = [
    (1, "Lasith Malinga",    "1983-08-28", "Right-hand bat", "Right-arm fast",        "Sri Lanka"),
    (2, "Jasprit Bumrah",    "1993-12-06", "Right-hand bat", "Right-arm fast",        "India"),
    (3, "Dwayne Bravo",      "1983-10-07", "Right-hand bat", "Right-arm medium-fast", "West Indies"),
    (4, "Amit Mishra",       "1982-11-24", "Right-hand bat", "Legbreak googly",       "India"),
    (5, "Shane Warne",       "1969-09-13", "Right-hand bat", "Legbreak googly",       "Australia"),
    (6, "Rohit Sharma",      "1987-04-30", "Right-hand bat", "Right-arm medium",      "India"),
    (7, "Virat Kohli",       "1988-11-05", "Right-hand bat", "Right-arm medium",      "India"),
    (8, "MS Dhoni",          "1981-07-07", "Right-hand bat", "Right-arm medium",      "India"),
    (9, "AB de Villiers",    "1984-02-17", "Right-hand bat", "Right-arm medium",      "South Africa"),
    (10,"Suresh Raina",      "1986-11-27", "Left-hand bat",  "Offbreak",              "India"),
]
cur.executemany("INSERT OR REPLACE INTO player VALUES (?,?,?,?,?,?)", players)

teams = [(1,"Mumbai Indians"),(2,"Chennai Super Kings"),(3,"Royal Challengers Bangalore"),
         (4,"Kolkata Knight Riders"),(5,"Delhi Capitals")]
cur.executemany("INSERT OR REPLACE INTO team VALUES (?,?)", teams)

matches = [
    (101,1,2,"2023-04-05",16,"Wankhede",       1,"bat",  "runs",   18,"result",1,6),
    (102,2,3,"2023-04-08",16,"Chepauk",         2,"bat",  "wickets", 4,"result",3,9),
    (103,3,4,"2023-04-12",16,"Chinnaswamy",     3,"field","runs",   23,"result",3,7),
    (104,1,4,"2023-04-16",16,"Wankhede",        4,"bat",  "wickets", 6,"result",1,2),
    (105,2,5,"2023-04-20",16,"Chepauk",         2,"bat",  "runs",   11,"result",2,3),
]
cur.executemany("INSERT OR REPLACE INTO match VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", matches)

pm = [
    (101,1,"Bowler",1),(101,2,"Bowler",1),(101,6,"Batsman",1),(101,8,"Batsman",1),(101,10,"All-rounder",1),
    (101,3,"Bowler",2),(101,4,"Bowler",2),(101,7,"Batsman",2),(101,9,"Batsman",2),(101,5,"Bowler",2),
    (102,3,"Bowler",2),(102,4,"Bowler",2),(102,7,"Batsman",2),(102,8,"Batsman",2),(102,10,"Batsman",2),
    (102,1,"Bowler",3),(102,2,"Bowler",3),(102,6,"Batsman",3),(102,9,"Batsman",3),(102,5,"Bowler",3),
    (103,1,"Bowler",3),(103,2,"Bowler",3),(103,6,"Batsman",3),(103,7,"Batsman",3),(103,9,"Batsman",3),
    (103,3,"Bowler",4),(103,4,"Bowler",4),(103,5,"Bowler",4),(103,8,"Batsman",4),(103,10,"Batsman",4),
    (104,1,"Bowler",1),(104,2,"Bowler",1),(104,6,"Batsman",1),(104,8,"Batsman",1),(104,10,"Batsman",1),
    (104,3,"Bowler",4),(104,4,"Bowler",4),(104,5,"Bowler",4),(104,7,"Batsman",4),(104,9,"Batsman",4),
    (105,3,"Bowler",2),(105,4,"Bowler",2),(105,7,"Batsman",2),(105,8,"Batsman",2),(105,10,"All-rounder",2),
    (105,1,"Bowler",5),(105,2,"Bowler",5),(105,6,"Batsman",5),(105,9,"Batsman",5),(105,5,"Bowler",5),
]
cur.executemany("INSERT OR REPLACE INTO player_match VALUES (?,?,?,?)", pm)

# ball_by_ball: match_id, over_id, ball_id, innings_no, team_batting, team_bowling, bat_pos, striker, non_striker, bowler
bbb = [
    # M101 inn1 (MI bat, CSK bowl: bowlers 3,4,5)
    (101,1,1,1,1,2,1,6,10,3),(101,1,2,1,1,2,2,7,6,3),(101,1,3,1,1,2,1,6,7,3),
    (101,1,4,1,1,2,2,9,6,4),(101,1,5,1,1,2,1,6,9,4),
    (101,2,1,1,1,2,3,8,10,5),(101,2,2,1,1,2,1,6,8,5),(101,2,3,1,1,2,2,9,6,5),
    (101,2,4,1,1,2,1,6,9,3),(101,3,1,1,1,2,2,10,6,4),(101,3,2,1,1,2,1,6,10,4),
    (101,3,3,1,1,2,3,8,6,5),
    # M101 inn2 (CSK bat, MI bowl: bowlers 1,2)
    (101,1,1,2,2,1,1,7,9,1),(101,1,2,2,2,1,2,9,7,1),(101,1,3,2,2,1,1,7,9,2),
    (101,1,4,2,2,1,2,9,7,2),(101,2,1,2,2,1,1,7,10,1),(101,2,2,2,2,1,2,10,7,2),
    # M102 inn1 (CSK bat, RCB bowl: bowlers 1,2,5)
    (102,1,1,1,2,3,1,7,10,1),(102,1,2,1,2,3,2,9,7,2),(102,1,3,1,2,3,1,7,9,5),
    (102,2,1,1,2,3,2,8,7,1),(102,2,2,1,2,3,1,7,8,2),(102,2,3,1,2,3,3,10,7,5),
    # M102 inn2 (RCB bat, CSK bowl: bowlers 3,4)
    (102,1,1,2,3,2,1,6,9,3),(102,1,2,2,3,2,2,9,6,4),(102,1,3,2,3,2,1,6,9,3),
    (102,2,1,2,3,2,2,7,6,4),(102,2,2,2,3,2,1,6,7,3),
    # M103 inn1 (RCB bat, KKR bowl: bowlers 3,4,5)
    (103,1,1,1,3,4,1,6,7,3),(103,1,2,1,3,4,2,9,6,4),(103,2,1,1,3,4,1,7,6,5),
    (103,2,2,1,3,4,2,6,7,3),(103,3,1,1,3,4,3,9,7,4),
    # M104 inn1 (MI bat, KKR bowl: bowlers 3,4,5)
    (104,1,1,1,1,4,1,6,10,3),(104,1,2,1,1,4,2,8,6,4),(104,2,1,1,1,4,1,6,8,5),
    (104,2,2,1,1,4,2,10,6,3),
    # M105 inn1 (CSK bat, DC bowl: bowlers 1,2,5)
    (105,1,1,1,2,5,1,7,10,1),(105,1,2,1,2,5,2,8,7,2),(105,2,1,1,2,5,1,7,8,5),
    (105,2,2,1,2,5,2,10,7,1),
]
cur.executemany("INSERT OR REPLACE INTO ball_by_ball VALUES (?,?,?,?,?,?,?,?,?,?)", bbb)

# batsman_scored: match_id, over_id, ball_id, runs_scored, innings_no
bs = [
    (101,1,1,4,1),(101,1,2,0,1),(101,1,3,6,1),(101,1,4,1,1),(101,1,5,3,1),
    (101,2,1,2,1),(101,2,2,4,1),(101,2,3,1,1),(101,2,4,0,1),(101,3,1,4,1),(101,3,2,6,1),(101,3,3,2,1),
    (101,1,1,3,2),(101,1,2,6,2),(101,1,3,0,2),(101,1,4,4,2),(101,2,1,2,2),(101,2,2,1,2),
    (102,1,1,4,1),(102,1,2,1,1),(102,1,3,6,1),(102,2,1,0,1),(102,2,2,4,1),(102,2,3,3,1),
    (102,1,1,6,2),(102,1,2,4,2),(102,1,3,0,2),(102,2,1,2,2),(102,2,2,1,2),
    (103,1,1,4,1),(103,1,2,0,1),(103,2,1,6,1),(103,2,2,4,1),(103,3,1,1,1),
    (104,1,1,4,1),(104,1,2,6,1),(104,2,1,0,1),(104,2,2,4,1),
    (105,1,1,1,1),(105,1,2,4,1),(105,2,1,6,1),(105,2,2,0,1),
]
cur.executemany("INSERT OR REPLACE INTO batsman_scored VALUES (?,?,?,?,?)", bs)

# wicket_taken: match_id, over_id, ball_id, player_out, kind_out, innings_no
wk = [
    (101,1,2,7,"caught",1),(101,2,3,9,"bowled",1),(101,3,3,8,"lbw",1),
    (101,1,4,9,"caught",2),(101,2,2,10,"bowled",2),
    (102,1,3,10,"caught",1),(102,2,3,7,"bowled",1),
    (102,1,3,9,"lbw",2),(102,2,1,7,"caught",2),
    (103,1,2,9,"caught",1),(103,3,1,7,"bowled",1),
    (104,1,2,8,"stumped",1),(104,2,2,10,"run out",1),
    (105,1,2,8,"caught",1),(105,2,2,10,"bowled",1),
]
cur.executemany("INSERT OR REPLACE INTO wicket_taken VALUES (?,?,?,?,?,?)", wk)

# extra_runs: match_id, over_id, ball_id, extra_type, extra_runs, innings_no
er = [
    (101,1,3,"wide",1,1),(101,2,1,"no ball",1,1),
    (102,1,2,"wide",1,1),(103,2,2,"wide",1,1),
    (104,1,1,"no ball",1,1),
]
cur.executemany("INSERT OR REPLACE INTO extra_runs VALUES (?,?,?,?,?,?)", er)

conn.commit()

# Verify all three predefined queries
print("=== Bowler Average ===")
cur.execute("""
    SELECT p.player_name, ROUND(CAST(SUM(bs.runs_scored) AS FLOAT) / COUNT(w.player_out), 2) AS bowling_avg
    FROM player p
    JOIN ball_by_ball b ON p.player_id = b.bowler
    JOIN batsman_scored bs ON b.match_id = bs.match_id AND b.over_id = bs.over_id AND b.ball_id = bs.ball_id AND b.innings_no = bs.innings_no
    JOIN wicket_taken w ON b.match_id = w.match_id AND b.over_id = w.over_id AND b.ball_id = w.ball_id AND b.innings_no = w.innings_no
    WHERE w.kind_out NOT IN ('run out', 'retired hurt', 'obstructing the field')
    GROUP BY p.player_id, p.player_name ORDER BY bowling_avg ASC LIMIT 5
""")
for r in cur.fetchall(): print(r)

print("=== Top Over Runs ===")
cur.execute("""
    SELECT p.player_name, b.match_id, b.over_id,
        (SUM(COALESCE(bs.runs_scored, 0)) + SUM(COALESCE(er.extra_runs, 0))) AS over_runs
    FROM player p JOIN ball_by_ball b ON p.player_id = b.bowler
    LEFT JOIN batsman_scored bs ON b.match_id = bs.match_id AND b.over_id = bs.over_id AND b.ball_id = bs.ball_id AND b.innings_no = bs.innings_no
    LEFT JOIN extra_runs er ON b.match_id = er.match_id AND b.over_id = er.over_id AND b.ball_id = er.ball_id AND b.innings_no = er.innings_no
    GROUP BY p.player_id, p.player_name, b.match_id, b.over_id ORDER BY over_runs DESC LIMIT 3
""")
for r in cur.fetchall(): print(r)

conn.close()
print("Done - IPL demo database seeded successfully.")
