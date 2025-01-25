from flask import Flask, request, jsonify
import mysql.connector

app = Flask(__name__)

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="password",
    database="classroom_scheduling"
)

@app.route('/classrooms', methods=['GET'])
def get_classrooms():
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Classrooms")
    classrooms = cursor.fetchall()
    return jsonify(classrooms)

if __name__ == '__main__':
    app.run(debug=True)