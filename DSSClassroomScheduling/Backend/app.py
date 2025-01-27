from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector

app = Flask(
    __name__,
    template_folder='../Frontend/src/pages',  
    static_folder='../Frontend/src'         
)

app.secret_key = 'your_secret_key'

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="classroom_scheduling"
)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        cursor = db.cursor(dictionary=True)
        query = "SELECT * FROM users WHERE first_name = %s AND password = %s"
        cursor.execute(query, (username, password))
        user = cursor.fetchone()

        if user:
            print("המשתמש נמצא:", user)
            return redirect(url_for('home'))
        else:
            print("לא נמצא משתמש בשם:", username)
            flash('Invalid username or password!')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/home')
def home():
    return render_template('home.html')

if __name__ == '__main__':
    app.run(debug=True)
