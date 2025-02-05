from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
import pandas as pd
import mysql.connector
from datetime import datetime

app = Flask(__name__)

# הגדרת מיקום התבניות והסטטי בפרויקט
app.template_folder = '../Frontend/src/pages'
app.static_folder = '../Frontend/src'

app.secret_key = 'your_secret_key'

# חיבור למסד הנתונים
db = mysql.connector.connect(
    host="localhost",
    port=3307,
    user="root",
    password="212165351Hala",
    database="classroom_scheduling"
)

# פונקציה לבדיקה אם יש נתונים קיימים בטבלה
def is_data_existing():
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM schedules")
    result = cursor.fetchone()[0]
    cursor.close()
    return result > 0

# פונקציה למחיקת כל הנתונים הקיימים בטבלה
def delete_existing_data():
    cursor = db.cursor()
    cursor.execute("DELETE FROM schedules")
    db.commit()
    cursor.close()

# פונקציה לקריאת ועיבוד קובץ
def process_file(file):
    data = pd.read_excel(file)
    required_columns = {'classroom_id', 'course_id', 'date', 'status', 'start_time', 'end_time'}

    if not required_columns.issubset(data.columns):
        raise ValueError("Invalid file format. Missing required columns.")

    # עיבוד הקובץ אם נדרש
    data['date'] = pd.to_datetime(data['date'], errors='coerce')
    data.dropna(inplace=True)  # מחיקת שורות עם נתונים חסרים
    return data

# פונקציה להוספת נתונים חדשים לטבלת schedules
def insert_data_to_db(data):
    cursor = db.cursor()
    for _, row in data.iterrows():
        cursor.execute("""
            INSERT INTO schedules (classroom_id, course_id, schedule_datetime, status, time_start, time_end)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            int(row['classroom_id']),
            int(row['course_id']),
            row['date'].strftime("%Y-%m-%d"),
            row['status'],
            row['start_time'],
            row['end_time']
        ))
    db.commit()
    cursor.close()

# מסלול להעלאת קובץ
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if is_data_existing():
            flash('Data already exists. Please delete existing data before uploading a new file.')
            return redirect(url_for('upload'))

        file = request.files['file']
        if not file:
            flash('No file selected!')
            return redirect(url_for('upload'))

        try:
            data = process_file(file)
            insert_data_to_db(data)
            flash('File uploaded and data inserted successfully!')
            return redirect(url_for('home'))
        except Exception as e:
            flash(f'An error occurred: {e}')
            return redirect(url_for('upload'))

    return render_template('upload.html')

# מסלול למחיקת נתונים קיימים
@app.route('/delete_data', methods=['POST'])
def delete_data():
    if not is_data_existing():
        flash('No data found to delete.')
        return redirect(url_for('upload'))

    delete_existing_data()
    flash('Existing data deleted successfully!')
    return redirect(url_for('upload'))

# מסלול לדף הבית
@app.route('/home')
def home():
    return render_template('home.html')

# מסלול לדף התחברות
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
            session['user_id'] = user['user_id']
            flash('Logged in successfully!')
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password!')
            return redirect(url_for('login'))

    return render_template('login.html')

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

# מסלול להתנתקות
@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
