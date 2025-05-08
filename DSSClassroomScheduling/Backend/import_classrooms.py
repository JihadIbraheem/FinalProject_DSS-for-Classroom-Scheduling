import pandas as pd
import mysql.connector

df = pd.read_excel(r"DSSClassroomScheduling\Backend\uploads\classroom_scheduling.xlsx", sheet_name="Classrooms")


# התחברות למסד הנתונים
db = mysql.connector.connect(
    host="localhost",
    port=3307,
    user="root",
    password="212165351Hala",
    database="classroom_scheduling"
)
cursor = db.cursor()

# קריאת גיליון buildings
df_buildings = pd.read_excel(
    r"DSSClassroomScheduling\Backend\uploads\classroom_scheduling.xlsx", 
    sheet_name="Buildings"
)

# הכנסת הנתונים לטבלה buildings
for _, row in df_buildings.iterrows():
    try:
        cursor.execute("""
            INSERT INTO buildings (building_id, building_name, num_floors)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                building_name = VALUES(building_name),
                num_floors = VALUES(num_floors)
        """, (
            int(row["building_id"]),
            row["building_name"],
            int(row["num_floors"]),
        ))
    except Exception as e:
        print(f"שגיאה בהכנסת בניין {row['building_id']}: {e}")


# הכנסת הנתונים
for _, row in df.iterrows():
    try:
        cursor.execute("""
            INSERT INTO classrooms (classroom_id, classroom_num, floor_num, capacity,
                                    is_remote_learning, is_sheltered, building_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                classroom_num = VALUES(classroom_num),
                floor_num = VALUES(floor_num),
                capacity = VALUES(capacity),
                is_remote_learning = VALUES(is_remote_learning),
                is_sheltered = VALUES(is_sheltered),
                building_id = VALUES(building_id)
        """, (
            int(row["classroom_id"]),
            row["classroom_num"],
            int(row["floor_num"]),
            int(row["capacity"]),
            row["is_remote_learning"] if pd.notna(row["is_remote_learning"]) else None,
            row["is_sheltered"] if pd.notna(row["is_sheltered"]) else None,
            int(row["building_id"]),
        ))
    except Exception as e:
        print(f"שגיאה בהכנסת כיתה {row['classroom_id']}: {e}")

db.commit()
db.close()
print("הטבלה classrooms הוזנה בהצלחה.")
