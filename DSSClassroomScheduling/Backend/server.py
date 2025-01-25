from flask import Flask, request, jsonify
import mysql.connector
from werkzeug.security import check_password_hash

app = Flask(__name__)

# חיבור למסד הנתונים
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",  
    database="classroom_scheduling"
)

cursor = db.cursor(dictionary=True)

# מסלול התחברות
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    # בדיקת שם משתמש וסיסמה
    cursor.execute("SELECT * FROM Users WHERE email = %s", (username,))
    user = cursor.fetchone()

    if user and check_password_hash(user['password'], password):
        return jsonify({"message": "Login successful", "role": user['role']})
    else:
        return jsonify({"message": "Invalid username or password"}), 401

if __name__ == '__main__':
    app.run(debug=True)
