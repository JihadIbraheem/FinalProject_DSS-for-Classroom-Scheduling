from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
import os
import mysql.connector

# יצירת אפליקציית Flask
app = Flask(__name__)

# הגדרת מיקום התבניות והסטטי בפרויקט
app.template_folder = '../Frontend/src/pages'
app.static_folder = '../Frontend/src'

# הגדרת מפתח סודי עבור Flask
app.secret_key = 'your_secret_key'

# חיבור למסד נתונים MySQL
db = mysql.connector.connect(
    host="localhost",  # שם השרת
    port=3307,         # פורט החיבור
    user="root",       # שם המשתמש במסד הנתונים
    password="212165351Hala",  # הסיסמה למסד הנתונים
    database="classroom_scheduling"  # שם מסד הנתונים
)

# מסלול לדף ההתחברות
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # קבלת נתוני המשתמש מהטופס
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        # בדיקת המשתמש במסד הנתונים
        cursor = db.cursor(dictionary=True)
        query = "SELECT * FROM users WHERE first_name = %s AND password = %s"
        cursor.execute(query, (username, password))
        user = cursor.fetchone()

        if user:
            print("The user is in the database:", user)
            return redirect(url_for('home'))
        else:
            print("No user found with the name:", username)
            flash('Invalid username or password!')
            return redirect(url_for('login'))

    return render_template('login.html')


# מסלול להתנתקות
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# מסלול לדף הבית
@app.route('/home')
def home():
    return render_template('home.html')

# מסלול לדף העלאת קבצים
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        file = request.files['file']
        if file:
            upload_folder = './uploads'
            os.makedirs(upload_folder, exist_ok=True)
            file.save(os.path.join(upload_folder, file.filename))
            flash('File uploaded successfully!')
            return redirect(url_for('home'))
        else:
            flash('No file selected!')
            return redirect(url_for('upload'))
    return render_template('upload.html')

# מסלול לבקשת מערכת שעות
@app.route('/request_schedule', methods=['GET', 'POST'])
def request_schedule():
    if request.method == 'POST':
        course_name = request.form['course-name']
        instructor_name = request.form['instructor-name']
        preferred_time = request.form['preferred-time']
        preferred_room = request.form['preferred-room']
        special_requirements = request.form['special-requirements']

        flash('Schedule request submitted successfully!')
        return redirect(url_for('home'))

    return render_template('request_schedule.html')

# מסלול ליצירת דוחות
@app.route('/generate_reports', methods=['GET', 'POST'])
def generate_reports():
    if request.method == 'POST':
        report_type = request.form['report-type']
        time_period = request.form['time-period']

        flash(f'Report "{report_type}" for "{time_period}" generated successfully!')
        return redirect(url_for('home'))

    return render_template('generate_reports.html')

if __name__ == '__main__':
    try:
        db.ping(reconnect=True)
        print("The database connection is active!")
    except mysql.connector.Error as err:
        print("Error connecting to the database:", err)
    app.run(debug=True)
