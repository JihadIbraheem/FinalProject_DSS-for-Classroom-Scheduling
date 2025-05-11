import pandas as pd
import mysql.connector

# קריאת גיליון Boards מתוך קובץ האקסל
df_boards = pd.read_excel(
    r"DSSClassroomScheduling\Backend\uploads\classroom_scheduling.xlsx", 
    sheet_name="Boards"
)

# התחברות למסד הנתונים
db = mysql.connector.connect(
    host="localhost",
    port=3307,
    user="root",
    password="212165351Hala",
    database="classroom_scheduling"
)
cursor = db.cursor()

# הכנסת הנתונים לטבלה boards
for _, row in df_boards.iterrows():
    try:
        cursor.execute("""
            INSERT INTO boards (board_id, board_size, classroom_id)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                board_size = VALUES(board_size),
                classroom_id = VALUES(classroom_id)
        """, (
            int(row["board_id"]),
            int(row["board_size"]),
            int(row["classroom_id"]),
        ))
    except Exception as e:
        print(f"שגיאה בהכנסת לוח {row['board_id']}: {e}")

db.commit()
db.close()
print("הטבלה boards הוזנה בהצלחה.")
