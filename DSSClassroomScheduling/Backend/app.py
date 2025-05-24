from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask import jsonify, Response, send_from_directory

import os
import pandas as pd
import mysql.connector
from datetime import time
from datetime import datetime
import re
from datetime import date,  timedelta
import re 

app = Flask(__name__)

app.template_folder = '../Frontend/src/pages'
app.static_folder = '../Frontend/src'

app.secret_key = 'your_secret_key'

db = mysql.connector.connect(
    host="localhost",
    port=3307,
    user="root",
    password="212165351Hala",
    database="classroom_scheduling"
)

@app.route('/')
def default_home():
    return redirect(url_for('login'))

def is_data_existing():
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM schedules")
    result = cursor.fetchone()[0]
    cursor.close()
    return result > 0

def delete_existing_data():
    cursor = db.cursor()
    cursor.execute("DELETE FROM schedules")
    cursor.execute("DELETE FROM courses")
    db.commit()
    cursor.close()


def extract_course_id(text):
    match = re.search(r'\d{4}-\d{2}', text)
    return match.group(0) if match else '0000-00'

def extract_course_details(text):
    match = re.search(r"(?P<course_id>.*?)\(\s*(?P<students_num>\d+)\)\[(?P<lecturer_name>.*?)\]\{(?P<course_name>.*?)\}", str(text))
    if match:
        data = match.groupdict()
        if data['course_id'].startswith(('א-', 'ב-', 'ג-', 'ד-', 'ה-', 'ו-', 'ש-')):
            data['course_id'] = data['course_id'][2:]  # הסר את שני התווים הראשונים
        return data
    return None


def process_file(file):
    df = pd.read_excel(file)
    df.columns = df.columns.map(lambda x: str(x).strip())

    required_columns = {'יום', 'חדר', 'בניין', 'קיבולת'}
    if not required_columns.issubset(set(df.columns)):
        raise ValueError(f"Invalid file format. Found columns: {list(df.columns)}. Expected: {list(required_columns)} and hourly slots")

    time_slots = [col for col in df.columns if col not in required_columns]
    schedule_rows = []
    course_rows = []

    for _, row in df.iterrows():
        weekday = row['יום']
        classroom_id = str(row['חדר']).strip()

        for slot in time_slots:
            course_info = str(row[slot]).strip()
            if pd.notna(course_info) and course_info != '':
                try:
                    start_time, end_time = slot.split('-')
                except ValueError:
                    continue

                # שליפת כל פרטי הקורס
                course_data = extract_course_details(course_info)
                if not course_data:
                    continue

                schedule_rows.append({
                    'classroom_id': classroom_id,
                    'course_id': course_data['course_id'],
                    'weekday': weekday,
                    'status': 'Confirmed',
                    'time_start': start_time + ':00',
                    'time_end': end_time + ':00'
                })

                course_rows.append(course_data)

    # הפוך ל-DataFrame
    schedule_df = pd.DataFrame(schedule_rows)
    courses_df = pd.DataFrame(course_rows).drop_duplicates(subset='course_id')
    courses_df["students_num"] = courses_df["students_num"].astype(int)
    
    schedule_df = merge_continuous_schedules(schedule_df)

    return schedule_df, courses_df


def merge_continuous_schedules(df):
    df['time_start'] = df['time_start'].astype(str).apply(lambda x: re.sub(r'[^\d:]', '', x))
    df['time_end'] = df['time_end'].astype(str).apply(lambda x: re.sub(r'[^\d:]', '', x))
    df['time_start'] = pd.to_datetime(df['time_start'], format='%H:%M:%S')
    df['time_end'] = pd.to_datetime(df['time_end'], format='%H:%M:%S')

    df.sort_values(by=['course_id', 'weekday', 'classroom_id', 'time_start'], inplace=True)

    merged = []
    current = None

    for row in df.itertuples():
        if current is None:
            current = row
        elif (row.course_id == current.course_id and
              row.weekday == current.weekday and
              row.classroom_id == current.classroom_id and
              row.time_start == current.time_end):
            current = current._replace(time_end=row.time_end)
        else:
            merged.append({
                'classroom_id': current.classroom_id,
                'course_id': current.course_id,
                'weekday': current.weekday,
                'status': current.status,
                'time_start': current.time_start.strftime('%H:%M:%S'),
                'time_end': current.time_end.strftime('%H:%M:%S')
            })
            current = row

    if current:
        merged.append({
            'classroom_id': current.classroom_id,
            'course_id': current.course_id,
            'weekday': current.weekday,
            'status': current.status,
            'time_start': current.time_start.strftime('%H:%M:%S'),
            'time_end': current.time_end.strftime('%H:%M:%S')
        })

    return pd.DataFrame(merged)


def insert_data_to_db(data):
    cursor = db.cursor()
    failed_rows = []

    for idx, row in data.iterrows():
        # חיפוש classroom_id לפי classroom_num
        try:
            classroom_number = str(row['classroom_id']).strip()
            cursor.execute("SELECT classroom_id FROM classrooms WHERE classroom_num = %s", (classroom_number,))
            result = cursor.fetchone()
            if result:
                classroom_id = result[0]
            else:
                failed_rows.append((idx + 1, f"Classroom number '{classroom_number}' not found in database."))
                continue
        except Exception as e:
            failed_rows.append((idx + 1, f"Error fetching classroom_id: {e}"))
            continue

        # שמירה של course_id כמות שהוא
        course_id = row['course_id']


        # עיבוד זמנים
        try:
            time_start_cleaned = re.sub(r'[^\d:]', '', str(row['time_start']))
            time_end_cleaned = re.sub(r'[^\d:]', '', str(row['time_end']))


            time_start = datetime.strptime(time_start_cleaned, "%H:%M:%S").time()
            time_end = datetime.strptime(time_end_cleaned, "%H:%M:%S").time()
        except Exception as e:
            failed_rows.append((idx + 1, f"Invalid time format: {e}"))
            continue

        # הכנסת הנתונים לטבלה schedules
        try:
            cursor.execute("""
                           INSERT INTO schedules (classroom_id, course_id, weekday, time_start, time_end)
                           VALUES (%s, %s, %s, %s, %s)
                           """, (
                               classroom_id,
                               course_id,
                               row['weekday'],
                               time_start,
                               time_end
                               ))
        except Exception as e:
            failed_rows.append((idx + 1, str(e)))

    print(f"Rows prepared for insert: {len(data)}")
    print(f"Total inserted: {len(data) - len(failed_rows)}")
    print(f"Failed rows: {failed_rows}")
    db.commit()
    cursor.close()

    if failed_rows:
        message = f"{len(failed_rows)} rows failed to insert. Check terminal for details."
        raise Exception(message)

def insert_courses_to_db(courses_df):
    cursor = db.cursor()
    for _, row in courses_df.iterrows():
        try:
            cursor.execute("""
                INSERT INTO courses (course_id, course_name, students_num, lecturer_name)
                VALUES (%s, %s, %s, %s)
            """, (
                row['course_id'],
                row['course_name'],
                row['students_num'],
                row['lecturer_name']
            ))
        except Exception as e:
            print(f"Failed to insert course {row['course_id']}: {e}")
            continue
    db.commit()
    cursor.close()

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory('uploads', filename)


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
            schedule_data, course_data = process_file(file)
            insert_courses_to_db(course_data)
            insert_data_to_db(schedule_data)

            flash('File uploaded and data inserted successfully!')
            return redirect(url_for('home'))
        except Exception as e:
            flash(f'An error occurred: {e}')
            return redirect(url_for('upload'))

    return render_template('upload.html')

@app.route('/delete_data', methods=['POST'])
def delete_data():
    if not is_data_existing():
        flash('No data found to delete.')
        return redirect(url_for('upload'))

    delete_existing_data()
    flash('Existing data deleted successfully!')
    return redirect(url_for('upload'))

@app.route('/home')
def home():
    return render_template('home.html')

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

@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        permissions = request.form['permissions']

        try:
            cursor = db.cursor()
            cursor.execute("""
                INSERT INTO users (first_name, last_name, email, password, role, permissions)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (first_name, last_name, email, password, role, permissions))
            db.commit()
            cursor.close()
            flash('User added successfully!')
        except Exception as e:
            flash(f'Error adding user: {e}')
        return redirect(url_for('home'))
    
    return render_template('add_user.html')

@app.route('/api/update_schedule_fields', methods=['POST'])
def update_schedule_fields():
    data = request.get_json()
    schedule_id = data['schedule_id']
    weekday = data['weekday']
    time_start = data['time_start']
    time_end = data['time_end']
    lecturer_name = data['lecturer_name']
    classroom_num = data['classroom_num']

    cursor = db.cursor(dictionary=True)

    # שליפת classroom_id
    cursor.execute("SELECT classroom_id FROM classrooms WHERE classroom_num = %s", (classroom_num,))
    classroom = cursor.fetchone()
    if not classroom:
        return jsonify(success=False, message="Classroom not found")
    classroom_id = classroom['classroom_id']

    # שליפת course_id כדי לזהות את המרצה
    cursor.execute("SELECT course_id FROM schedules WHERE schedule_id = %s", (schedule_id,))
    course = cursor.fetchone()
    if not course:
        return jsonify(success=False, message="Course not found")
    course_id = course['course_id']

    # בדיקה של התנגשות בכיתה
    cursor.execute("""
        SELECT * FROM schedules
        WHERE schedule_id != %s
          AND classroom_id = %s
          AND weekday = %s
          AND (
            (time_start <= %s AND time_end > %s) OR
            (time_start < %s AND time_end >= %s) OR
            (time_start >= %s AND time_end <= %s)
          )
    """, (schedule_id, classroom_id, weekday,
          time_start, time_start, time_end, time_end, time_start, time_end))
    room_conflict = cursor.fetchone()
    if room_conflict:
        return jsonify(success=False, message="Time conflict in the same classroom")

    # בדיקה של התנגשות למרצה
    cursor.execute("""
        SELECT s.* FROM schedules s
        JOIN courses c ON s.course_id = c.course_id
        WHERE s.schedule_id != %s
          AND c.lecturer_name = %s
          AND s.weekday = %s
          AND (
            (s.time_start <= %s AND s.time_end > %s) OR
            (s.time_start < %s AND s.time_end >= %s) OR
            (s.time_start >= %s AND s.time_end <= %s)
          )
    """, (schedule_id, lecturer_name, weekday,
          time_start, time_start, time_end, time_end, time_start, time_end))
    lecturer_conflict = cursor.fetchone()
    if lecturer_conflict:
        return jsonify(success=False, message="Lecturer has another class at that time")

    # עדכון בפועל
    cursor.execute("""
        UPDATE schedules
        SET weekday = %s, time_start = %s, time_end = %s
        WHERE schedule_id = %s
    """, (weekday, time_start, time_end, schedule_id))
    db.commit()
    cursor.close()

    return jsonify(success=True)


@app.route('/api/schedules')
def api_schedules():
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
    SELECT 
        s.schedule_id,
        c.classroom_num,
        b.building_name,
        s.course_id,
        cr.course_name,
        cr.lecturer_name,
        s.weekday,
        s.time_start,
        s.time_end
    FROM schedules s
    JOIN classrooms c ON s.classroom_id = c.classroom_id
    JOIN buildings b ON c.building_id = b.building_id
    JOIN courses cr ON s.course_id = cr.course_id
                   """)

    rows = cursor.fetchall()
    cursor.close()

    for row in rows:
        for key in row:
            val = row[key]
            if isinstance(val, (datetime, date)):
                row[key] = val.isoformat()
            elif isinstance(val, time):
                row[key] = val.strftime("%H:%M")
            elif isinstance(val, timedelta):
                row[key] = str(val)  # המרה של timedelta למחרוזת
            elif val is None:
                row[key] = ""

    return jsonify(schedules=rows)



@app.route('/interactive_schedule')
def interactive_schedule():
    return render_template('interactive_schedule.html')


@app.route('/update_schedule', methods=['POST'])
def update_schedule():
    try:
        schedule_id = request.form['schedule_id']
        classroom_id = request.form['classroom_id']
        course_id = request.form['course_id']
        schedule_datetime = request.form['schedule_datetime']
        status = request.form['status']
        time_start = request.form['time_start']
        time_end = request.form['time_end']

        # בדיקת התנגשויות - האם יש כבר שיעור באותה כיתה ובאותו זמן
        cursor = db.cursor(dictionary=True)
        conflict_query = '''
            SELECT * FROM schedules
            WHERE classroom_id = %s
              AND schedule_id != %s
              AND schedule_datetime = %s
              AND (
                    (time_start <= %s AND time_end > %s) OR
                    (time_start < %s AND time_end >= %s) OR
                    (time_start >= %s AND time_end <= %s)
              )
        '''
        cursor.execute(conflict_query, (
            classroom_id, schedule_id, schedule_datetime,
            time_start, time_start,
            time_end, time_end,
            time_start, time_end
        ))
        conflict = cursor.fetchone()

        if conflict:
            flash("Conflict detected: Room is already booked during that time.")
            return redirect(url_for('request_schedule'))

        # עדכון בטבלת schedules
        update_query = '''
            UPDATE schedules
            SET classroom_id = %s, course_id = %s, schedule_datetime = %s,
                status = %s, time_start = %s, time_end = %s, updated_at = NOW()
            WHERE schedule_id = %s
        '''
        cursor.execute(update_query, (
            classroom_id, course_id, schedule_datetime,
            status, time_start, time_end, schedule_id
        ))
        db.commit()
        cursor.close()

        flash("Schedule updated successfully.")
        return redirect(url_for('request_schedule'))

    except Exception as e:
        flash(f"Error updating schedule: {str(e)}")
        return redirect(url_for('request_schedule'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!')
    return redirect(url_for('login'))


@app.route('/api/schedule_details/<int:schedule_id>')
def get_schedule_details(schedule_id):
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
    SELECT s.*, c.classroom_num, c.capacity, c.is_remote_learning, c.is_sheltered,
           cr.course_name, cr.lecturer_name,
           b.building_name
                   FROM schedules s
                   JOIN classrooms c ON s.classroom_id = c.classroom_id
                   JOIN buildings b ON c.building_id = b.building_id
                   JOIN courses cr ON s.course_id = cr.course_id
                WHERE s.schedule_id = %s
            """, (schedule_id,))

    schedule = cursor.fetchone()

    if not schedule:
        return jsonify(success=False, message="Schedule not found")

    cursor.execute("SELECT board_id, board_size FROM boards WHERE classroom_id = %s", (schedule['classroom_id'],))
    boards = cursor.fetchall()
    schedule['boards'] = boards

    for key in schedule:
        val = schedule[key]
        if isinstance(val, (datetime, date)):
            schedule[key] = val.isoformat()
        elif isinstance(val, time):
            schedule[key] = val.strftime('%H:%M')
        elif isinstance(val, timedelta):
            schedule[key] = str(val)
        elif val is None:
            schedule[key] = ""

    return jsonify(schedule)

# ==============================================
@app.route('/api/save_schedule_update', methods=['POST'])
def save_schedule_update():
    data = request.get_json()
    schedule_id = data['schedule_id']
    weekday = data['weekday']
    time_start = data['time_start']
    time_end = data['time_end']
    capacity = int(data['capacity'])
    is_remote = data['is_remote_learning']
    is_sheltered = data['is_sheltered']
    board_count = int(data.get('board_count', 0))
    selected_classroom_num = data.get('selected_classroom_num')

    cursor = db.cursor(dictionary=True)

    try:
        # שליפת שיבוץ קיים
        cursor.execute("SELECT classroom_id, course_id FROM schedules WHERE schedule_id = %s", (schedule_id,))
        sched = cursor.fetchone()
        if not sched:
            return jsonify(success=False, message="Schedule not found")

        old_classroom_id = sched['classroom_id']
        course_id = sched['course_id']

        # בדיקת שינוי בזמן
        cursor.execute("SELECT weekday, time_start, time_end FROM schedules WHERE schedule_id = %s", (schedule_id,))
        original = cursor.fetchone()
        time_changed = (
            original['weekday'] != weekday or
            str(original['time_start']) != time_start or
            str(original['time_end']) != time_end
        )

        # בדיקת זמינות מרצה רק אם קיים מרצה
        if time_changed:
            cursor.execute("SELECT lecturer_name FROM courses WHERE course_id = %s", (course_id,))
            lecturer_row = cursor.fetchone()
            lecturer = lecturer_row['lecturer_name'] if lecturer_row and lecturer_row['lecturer_name'] else None

            if lecturer:
                cursor.execute("""
                    SELECT 1 FROM schedules s
                    JOIN courses c ON s.course_id = c.course_id
                    WHERE s.schedule_id != %s AND c.lecturer_name = %s AND s.weekday = %s
                    AND (
                        (s.time_start <= %s AND s.time_end > %s) OR
                        (s.time_start < %s AND s.time_end >= %s) OR
                        (s.time_start >= %s AND s.time_end <= %s)
                    )
                """, (
                    schedule_id, lecturer, weekday,
                    time_start, time_start, time_end, time_end, time_start, time_end
                ))
                if cursor.fetchone():
                    return jsonify(success=False, message="Lecturer not available at this time")

        # סינון כיתות זמינות
        sheltered_filter = "AND is_sheltered = %s" if is_sheltered == "yes" else ""
        query = f"""
            SELECT * FROM classrooms c
            WHERE capacity >= %s
            AND is_remote_learning = %s
            {sheltered_filter}
            AND (
                SELECT COUNT(*) FROM boards b WHERE b.classroom_id = c.classroom_id
            ) >= %s
            AND NOT EXISTS (
                SELECT 1 FROM schedules s
                WHERE s.classroom_id = c.classroom_id AND s.schedule_id != %s
                AND s.weekday = %s
                AND (
                    (s.time_start <= %s AND s.time_end > %s) OR
                    (s.time_start < %s AND s.time_end >= %s) OR
                    (s.time_start >= %s AND s.time_end <= %s)
                )
            )
        """
        params = [capacity, is_remote]
        if is_sheltered == "yes":
            params.append(is_sheltered)
        params += [
            board_count, schedule_id, weekday,
            time_start, time_start, time_end, time_end, time_start, time_end
        ]
        cursor.execute(query, tuple(params))
        available = cursor.fetchall()

        # אין כיתות זמינות
        if not available:
            return jsonify(success=False, message="No available classrooms found")

        # שליחת אופציות בחירה
        if not selected_classroom_num:
            classroom_options = []
            for c in available:
                cursor.execute("""
                    SELECT c.classroom_num, c.capacity, c.is_remote_learning, c.is_sheltered,
                           b.building_name,
                           (SELECT COUNT(*) FROM boards WHERE classroom_id = c.classroom_id) AS board_count
                    FROM classrooms c
                    JOIN buildings b ON c.building_id = b.building_id
                    WHERE c.classroom_id = %s
                """, (c['classroom_id'],))
                option = cursor.fetchone()
                if option:
                    classroom_options.append(option)
                else:
                    _ = cursor.fetchall()  # מניעת שגיאת unread result

            return jsonify(success=False, message="No available classroom matches the new constraints", available_classrooms=classroom_options)

        # עדכון שיבוץ
        cursor.execute("SELECT classroom_id FROM classrooms WHERE classroom_num = %s", (selected_classroom_num,))
        classroom_row = cursor.fetchone()
        if not classroom_row:
            return jsonify(success=False, message="Selected classroom not found")

        new_classroom_id = classroom_row['classroom_id']

        cursor.execute("""
            UPDATE schedules
            SET classroom_id=%s, weekday=%s, time_start=%s, time_end=%s
            WHERE schedule_id = %s
        """, (new_classroom_id, weekday, time_start, time_end, schedule_id))

        cursor.execute("""
            UPDATE classrooms
            SET capacity=%s, is_remote_learning=%s, is_sheltered=%s
            WHERE classroom_id = %s
        """, (capacity, is_remote, is_sheltered, new_classroom_id))

        cursor.execute("DELETE FROM boards WHERE classroom_id = %s", (new_classroom_id,))
        for _ in range(board_count):
            cursor.execute("INSERT INTO boards (board_size, classroom_id) VALUES (%s, %s)", (1, new_classroom_id))

        db.commit()
        return jsonify(success=True)

    finally:
        try:
            cursor.fetchall()
        except:
            pass
        cursor.close()

@app.route('/reports_statistics')
def reports_schedule():
    return render_template('reports_statistics.html')

@app.route('/second_schedule')
def second_schedule():
    return render_template('second_schedule.html')

if __name__ == '__main__':
    app.run(debug=True)