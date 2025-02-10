from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask import jsonify, Response
import os
import pandas as pd
import mysql.connector
from datetime import datetime, time, timedelta
from io import BytesIO
from fpdf import FPDF


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

# מסלול ברירת מחדל - עמוד הבית
@app.route('/')
def default_home():
    return redirect(url_for('login'))

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
# עדיין לא פועל
@app.route('/generate_reports', methods=['GET', 'POST'])
def generate_reports():
    if request.method == 'POST':
        classroom_id = request.form.get('classroom_id')
        report_format = request.form.get('report_format')

        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM schedules WHERE classroom_id = %s", (classroom_id,))
        schedules = cursor.fetchall()
        cursor.close()

        if not schedules:
            flash('No schedules found for the selected classroom!')
            return redirect(url_for('generate_reports'))

        if report_format == 'pdf':
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()
            pdf.set_font("Arial", size=12)

            pdf.cell(200, 10, txt="Schedules Report", ln=True, align='C')

            for schedule in schedules:
                line = ", ".join([f"{key}: {value}" for key, value in schedule.items()])
                pdf.multi_cell(0, 10, txt=line)

            # שימוש באובייקט BytesIO
            output = BytesIO()
            pdf.output(output, 'F')  # שמירת הקובץ בזיכרון
            output.seek(0)

            return Response(output, mimetype="application/pdf",
                            headers={"Content-Disposition": "attachment;filename=schedules_report.pdf"})

        elif report_format == 'excel':
            df = pd.DataFrame(schedules)
            output = BytesIO()
            writer = pd.ExcelWriter(output, engine='xlsxwriter')
            df.to_excel(writer, index=False, sheet_name='Schedules')
            writer.save()
            output.seek(0)

            return Response(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            headers={"Content-Disposition": "attachment;filename=schedules_report.xlsx"})

    return render_template('generate_reports.html')

# מסלול להתנתקות
@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!')
    return redirect(url_for('login'))

# מסלול להצגת שיבוצים קיימים
@app.route('/get_schedules', methods=['GET'])
def get_schedules():
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM schedules")
    schedules = cursor.fetchall()
    cursor.close()

    # המרה של datetime, time, timedelta למחרוזות והוספת ערכים קבועים ברירת מחדל
    for schedule in schedules:
        if 'schedule_datetime' in schedule and isinstance(schedule['schedule_datetime'], datetime):
            schedule['schedule_datetime'] = schedule['schedule_datetime'].strftime("%Y-%m-%d %H:%M:%S")
        else:
            schedule['schedule_datetime'] = "2025-01-01 00:00:00"  # ערך ברירת מחדל
        
        if 'time_start' in schedule and isinstance(schedule['time_start'], time):
            schedule['time_start'] = schedule['time_start'].strftime("%H:%M:%S")
        else:
            schedule['time_start'] = "08:00:00"  # ערך ברירת מחדל

        if 'time_end' in schedule and isinstance(schedule['time_end'], time):
            schedule['time_end'] = schedule['time_end'].strftime("%H:%M:%S")
        else:
            schedule['time_end'] = "10:00:00"  # ערך ברירת מחדל

        if 'time_diff' in schedule and isinstance(schedule['time_diff'], timedelta):
            schedule['time_diff'] = str(schedule['time_diff'])
        else:
            schedule['time_diff'] = "2:00:00"  # ערך ברירת מחדל

        if 'status' not in schedule or not schedule['status']:
            schedule['status'] = "Pending"  # ערך ברירת מחדל למצב

    return jsonify({'schedules': schedules})


# מסלול לעדכון שיבוץ
@app.route('/update_schedule', methods=['POST'])
def update_schedule():
    schedule_id = request.form['schedule_id']
    classroom_id = request.form['classroom_id']
    course_id = request.form['course_id']
    schedule_datetime = request.form['schedule_datetime']
    status = request.form['status']
    time_start = request.form['time_start']
    time_end = request.form['time_end']

    try:
        cursor = db.cursor()
        cursor.execute("""
            UPDATE schedules
            SET classroom_id = %s, course_id = %s, schedule_datetime = %s, status = %s, time_start = %s, time_end = %s
            WHERE schedule_id = %s
        """, (classroom_id, course_id, schedule_datetime, status, time_start, time_end, schedule_id))
        db.commit()
        cursor.close()
        flash('Schedule updated successfully!')
    except Exception as e:
        flash(f'Error updating schedule: {e}')
    return redirect(url_for('request_schedule'))


if __name__ == '__main__':
    app.run(debug=True)
