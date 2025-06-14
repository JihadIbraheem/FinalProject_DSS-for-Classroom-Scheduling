from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask import jsonify, Response, send_from_directory
##########################
from flask import send_file
import io
###########################
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


###########################
def get_connection():
    return mysql.connector.connect(
    host="localhost",
    port=3307,
    user="root",
    password="212165351Hala",
    database="classroom_scheduling"
    )

@app.route("/reports_statistics")
def reports_statistics():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM buildings")
    buildings = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("reports_statistics.html", buildings=buildings)

@app.route('/generate_report', methods=['POST'])
def generate_report():
    report_type = request.form.get('report_type')
    building_id = request.form.get('building_id')
    day = request.form.get('day')
    start_time = request.form.get('start_time')
    end_time = request.form.get('end_time')

    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        output = io.BytesIO()

        if report_type == 'utilization':
            cursor.execute("SELECT COUNT(*) AS total FROM classrooms")
            total = cursor.fetchone()['total']
            cursor.execute("SELECT COUNT(DISTINCT classroom_id) AS used FROM schedules")
            used = cursor.fetchone()['used']
            cursor.execute("""
                SELECT AVG(used_count) as avg_daily
                FROM (
                    SELECT COUNT(DISTINCT classroom_id) AS used_count, weekday
                    FROM schedules GROUP BY weekday
                ) as daily
            """)
            avg_daily = round(cursor.fetchone()['avg_daily'], 2)
            cursor.execute("""
                SELECT HOUR(time_start) as hour, COUNT(*) as count
                FROM schedules GROUP BY hour ORDER BY count DESC LIMIT 1
            """)
            peak_hour = f"{cursor.fetchone()['hour']}:00"
            cursor.execute("""
                SELECT COUNT(*) AS underutilized FROM classrooms
                WHERE classroom_id NOT IN (SELECT DISTINCT classroom_id FROM schedules)
            """)
            underutilized = cursor.fetchone()['underutilized']

            summary_df = pd.DataFrame([{
                "Total Classrooms": total,
                "Utilized Classrooms": used,
                "Average Daily Usage Rate": avg_daily,
                "Peak Usage Hour": peak_hour,
                "Underutilized Classrooms": underutilized
            }])

            building_df = pd.read_sql("""
                SELECT b.building_name, COUNT(c.classroom_id) AS classrooms,
                    ROUND(AVG(s_count), 2) AS avg_utilization,
                    weekday AS peak_day,
                    GROUP_CONCAT(IF(s_count=0, c.classroom_num, NULL)) AS underutilized_rooms
                FROM buildings b
                JOIN classrooms c ON c.building_id = b.building_id
                LEFT JOIN (
                    SELECT classroom_id, COUNT(*) AS s_count, weekday
                    FROM schedules GROUP BY classroom_id, weekday
                ) s ON s.classroom_id = c.classroom_id
                GROUP BY b.building_id, s.weekday
            """, conn)

            time_slot_df = pd.read_sql("""
                SELECT 
                    CONCAT(LPAD(HOUR(time_start), 2, '0'), ':00-', LPAD(HOUR(time_end), 2, '0'), ':00') AS time_slot,
                    weekday, COUNT(*) AS 'usage'
                FROM schedules
                WHERE HOUR(time_start) BETWEEN 8 AND 21
                GROUP BY time_slot, weekday
            """, conn).pivot(index='time_slot', columns='weekday', values='usage').fillna(0)

            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
                building_df.to_excel(writer, sheet_name='Building Breakdown', index=False)
                time_slot_df.to_excel(writer, sheet_name='Time Slot Usage')

        elif report_type == 'estimated_students':
            df = pd.read_sql("""
                SELECT b.building_name,
                    SUM(c2.students_num) AS estimated_students,
                    ROUND(AVG(c2.students_num), 2) AS avg_per_room,
                    s.weekday AS peak_day
                FROM buildings b
                JOIN classrooms c ON c.building_id = b.building_id
                JOIN schedules s ON s.classroom_id = c.classroom_id
                JOIN courses c2 ON c2.course_id = s.course_id
                GROUP BY b.building_id, s.weekday
            """, conn)
            df.to_excel(output, index=False)

        elif report_type == 'reschedule_needed':
            df = pd.read_sql("""
                SELECT * FROM schedules s
                WHERE s.classroom_id NOT IN (SELECT classroom_id FROM classrooms)
            """, conn)
            df.to_excel(output, index=False)

        elif report_type == 'history':
            df = pd.read_sql("SELECT * FROM schedule_history", conn)
            df.to_excel(output, index=False)

        else:
            return "Invalid report type", 400

        output.seek(0)
        return send_file(
            output,
            download_name=f"{report_type}_report.xlsx",
            as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    finally:
        cursor.close()
        conn.close()

###########################


@app.route('/')
def default_home():
    return redirect(url_for('login'))

@app.route('/manual_schedule', methods=['POST'])
def manual_schedule():
    if is_data_existing():
        flash("Please delete existing data before adding new schedule manually.")
        return redirect(url_for('upload'))

    course_names = request.form.getlist('course_name[]')
    lecturer_names = request.form.getlist('lecturer_name[]')
    capacities = request.form.getlist('students_num[]')
    remote_flags = request.form.getlist('is_remote_learning[]')
    sheltered_flags = request.form.getlist('is_sheltered[]')
    course_ids = request.form.getlist('course_id[]')
    weekdays = request.form.getlist('weekday[]')
    durations = request.form.getlist('duration[]')

    if not (course_names and lecturer_names and capacities):
        flash("Missing course data.")
        return redirect(url_for('upload'))

    WEEKDAY_MAP = {
        "א": "א'", "ב": "ב'", "ג": "ג'", "ד": "ד'", "ה": "ה'", "ו": "ו'"
    }

    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    for i in range(len(course_names)):
        course_id = course_ids[i] if course_ids[i] else f"auto_{i+1}"
        course_name = course_names[i]
        lecturer_name = lecturer_names[i]
        students_num = int(capacities[i])

        # המרת ערכים לבוליאן/אינט (0/1)
        is_remote = 1 if remote_flags[i] in ['1', 'true', 'True', True] else 0
        is_sheltered = 1 if sheltered_flags[i] in ['1', 'true', 'True', True] else 0

        raw_day = weekdays[i].strip() if weekdays[i] else 'א'
        preferred_day = WEEKDAY_MAP.get(raw_day, raw_day)

        duration_hours = float(durations[i])
        duration_minutes = int(duration_hours * 60)

        try:
            cursor.execute("""
                INSERT INTO courses (course_id, course_name, students_num, lecturer_name)
                VALUES (%s, %s, %s, %s)
            """, (course_id, course_name, students_num, lecturer_name))
        except Exception as e:
            flash(f"⚠️ Failed to insert course '{course_name}': {e}")
            continue

        def try_schedule_with_classrooms(classroom_query, allow_relaxation=False):
            for classroom in classroom_query:
                classroom_id = classroom[0]
                cursor.execute("""
                    SELECT time_start, time_end FROM schedules
                    WHERE classroom_id = %s AND weekday = %s
                    ORDER BY time_start
                """, (classroom_id, preferred_day))
                busy_times = cursor.fetchall()

                current_time = datetime.strptime("08:00:00", "%H:%M:%S")
                end_of_day = datetime.strptime("18:00:00", "%H:%M:%S")

                for bt in busy_times + [(end_of_day.time(), end_of_day.time())]:
                    next_start = datetime.strptime(str(bt[0]), "%H:%M:%S")
                    potential_end = current_time + timedelta(minutes=duration_minutes)

                    if potential_end <= next_start:
                        cursor.execute("""
                            INSERT INTO schedules (classroom_id, course_id, weekday, time_start, time_end)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (
                            classroom_id, course_id, preferred_day,
                            current_time.time(), potential_end.time()
                        ))
                        return True, classroom_id

                    current_time = datetime.strptime(str(bt[1]), "%H:%M:%S")
            return False, None

        # המרה בטוחה לבוליאנים מספריים (0/1)
        is_remote = 1 if str(remote_flags[i]).strip() in ['1', 'true', 'True', 'on'] else 0
        is_sheltered = 1 if str(sheltered_flags[i]).strip() in ['1', 'true', 'True', 'on'] else 0
        
        cursor.execute("""
         SELECT classroom_id FROM classrooms
         WHERE capacity >= %s
         AND CAST(is_remote_learning AS UNSIGNED) = %s
         AND CAST(is_sheltered AS UNSIGNED) = %s
         ORDER BY capacity ASC
         """, (students_num, is_remote, is_sheltered))

        classrooms = cursor.fetchall()
        scheduled, classroom_used = try_schedule_with_classrooms(classrooms)

        if not scheduled:
            cursor.execute("""
                SELECT classroom_id, capacity, is_remote_learning, is_sheltered FROM classrooms
                WHERE capacity >= %s
                ORDER BY capacity ASC
            """, (students_num,))
            relaxed_classrooms = cursor.fetchall()
            scheduled, classroom_used = try_schedule_with_classrooms([(c[0],) for c in relaxed_classrooms], allow_relaxation=True)

            if scheduled:
                for c in relaxed_classrooms:
                    if c[0] == classroom_used:
                        mismatches = []
                        if str(c[2]) != str(is_remote):
                            mismatches.append("remote learning mismatch")
                        if str(c[3]) != str(is_sheltered):
                            mismatches.append("sheltered room mismatch")
                        msg = f"⚠️ Course '{course_name}' was scheduled in a non-ideal classroom: {', '.join(mismatches)}."
                        flash(msg)
                        break
            else:
                flash(f"❌ No classroom found for '{course_name}' on {preferred_day}.")

    conn.commit()
    cursor.close()
    conn.close()

    return render_template('upload.html', data_exists=True, upload_status='success')



def is_data_existing():
    with db.cursor(buffered=True) as cursor:  
        cursor.execute("SELECT COUNT(*) FROM schedules")
        result = cursor.fetchone()
        return result[0] > 0


def delete_existing_data():
    with db.cursor(buffered=True) as cursor:
        cursor.execute("DELETE FROM schedule_history")
        cursor.execute("DELETE FROM schedules")
        cursor.execute("DELETE FROM courses")
        db.commit()



def extract_course_id(text):
    match = re.search(r'\d{4}-\d{2}', text)
    return match.group(0) if match else '0000-00'


def extract_course_details(text):
    match = re.search(
        r"(?P<course_id>.*?)\(\s*(?P<students_num>\d+)\)\[(?P<lecturer_name>.*?)\]\{(?P<course_name>.*?)\}",
        str(text)
    )
    if match:
        data = match.groupdict()
        if data['course_id'].startswith(('א-', 'ב-', 'ג-', 'ד-', 'ה-', 'ו-', 'ש-')):
            data['course_id'] = data['course_id'][2:]  # הסרת קידומת יום
        return data
    return None

@app.route('/api/max_capacity')
def max_capacity():
    with db.cursor() as cursor:
        cursor.execute("SELECT MAX(capacity) FROM classrooms")
        result = cursor.fetchone()
        return jsonify(max_capacity=result[0] if result else 100)

def process_file(file):
    df = pd.read_excel(file)
    df.columns = df.columns.map(lambda x: str(x).strip())

    # ✅ בדיקה 1: עמודות חובה
    required_columns = {'יום', 'חדר', 'בניין', 'קיבולת'}
    if not required_columns.issubset(set(df.columns)):
        raise ValueError(f"Missing required columns. Found columns: {list(df.columns)}. Required: {list(required_columns)}")

    # ✅ בדיקה 2: תאים ריקים בעמודות חיוניות
    for col in ['יום', 'חדר', 'בניין']:
        if df[col].isnull().any() or (df[col].astype(str).str.strip() == "").any():
            raise ValueError(f"Empty values found in required column: '{col}'")

    # ✅ בדיקה 3: עמודות שעות נדרשות
    hourly_columns = [
        "08:00 - 09:00", "09:00 - 10:00", "10:00 - 11:00", "11:00 - 12:00",
        "12:00 - 13:00", "13:00 - 14:00", "14:00 - 15:00", "15:00 - 16:00",
        "16:00 - 17:00", "17:00 - 18:00", "18:00 - 19:00", "19:00 - 20:00",
        "20:00 - 21:00", "21:00 - 22:00"
    ]
    missing_slots = [col for col in hourly_columns if col not in df.columns]
    if missing_slots:
        raise ValueError(f"Missing time slot columns: {missing_slots}")

    time_slots = [col for col in df.columns if col not in required_columns]
    schedule_rows = []
    course_rows = []

    for i, row in df.iterrows():
        weekday = row['יום']
        classroom_id = str(row['חדר']).strip()

        for slot in time_slots:
            course_info = row[slot]
            if pd.notna(course_info):
                course_info = str(course_info).strip()
                if course_info == '' or course_info == slot:
                    continue  # דלג על שורה ריקה או תא שמכיל את שם העמודה

                try:
                    start_time, end_time = slot.split('-')
                except ValueError:
                    continue

                # ✅ בדיקה 4: פורמט תקין של תא
                course_data = extract_course_details(course_info)
                if not course_data:
                    raise ValueError(f"Invalid course format at row {i+2}, column '{slot}': '{course_info}'")

                # ✅ בדיקה 5: שדות חובה בקורס
                required_fields = ['course_id', 'students_num', 'course_name']
                for field in required_fields:
                    if field not in course_data or str(course_data[field]).strip() == '':
                        raise ValueError(f"Missing required field '{field}' at row {i+2}, column '{slot}': '{course_info}'")

                schedule_rows.append({
                    'classroom_id': classroom_id,
                    'course_id': course_data['course_id'],
                    'weekday': weekday,
                    'status': 'Confirmed',
                    'time_start': start_time + ':00',
                    'time_end': end_time + ':00'
                })

                course_rows.append(course_data)

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
    failed_rows = []

    with db.cursor() as cursor:
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

        db.commit()

    print(f"Rows prepared for insert: {len(data)}")
    print(f"Total inserted: {len(data) - len(failed_rows)}")
    print(f"Failed rows: {failed_rows}")

    if failed_rows:
        message = f"{len(failed_rows)} rows failed to insert. Check terminal for details."
        raise Exception(message)


def insert_courses_to_db(courses_df):
    with db.cursor() as cursor:
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


@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory('uploads', filename)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    upload_status = None  # New flag

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

            upload_status = 'success'
            flash('File uploaded and data inserted successfully!')
        except Exception as e:
            upload_status = 'error'
            flash(f'An error occurred: {e}')

    data_exists = is_data_existing()
    return render_template('upload.html', data_exists=data_exists, upload_status=upload_status)

@app.route('/api/add_schedule_from_ui', methods=['POST'])
def add_schedule_from_ui():
    data = request.get_json()

    try:
        course_id = data['course_id']
        course_name = data['course_name']
        lecturer_name = data['lecturer_name']
        students_num = int(data['students_num'])
        duration_hours = float(data['duration'])
        weekday = data['weekday']
        is_remote = data['is_remote_learning']
        is_sheltered = data['is_sheltered']
        schedule_end_date = data.get('schedule_end_date')

        duration_minutes = int(duration_hours * 60)

        with db.cursor(buffered=True) as cursor:
            # Try to find available classroom first
            cursor.execute("""
                SELECT classroom_id FROM classrooms
                WHERE capacity >= %s AND is_remote_learning = %s AND is_sheltered = %s
                ORDER BY capacity ASC
            """, (students_num, is_remote, is_sheltered))
            classrooms = cursor.fetchall()

            def try_schedule():
                for classroom in classrooms:
                    classroom_id = classroom[0]
                    cursor.execute("""
                        SELECT time_start, time_end FROM schedules
                        WHERE classroom_id = %s AND weekday = %s
                        ORDER BY time_start
                    """, (classroom_id, weekday))
                    busy_times = cursor.fetchall()

                    current_time = datetime.strptime("08:00:00", "%H:%M:%S")
                    end_of_day = datetime.strptime("18:00:00", "%H:%M:%S")

                    for bt in busy_times + [(end_of_day.time(), end_of_day.time())]:
                        next_start = datetime.strptime(str(bt[0]), "%H:%M:%S")
                        potential_end = current_time + timedelta(minutes=duration_minutes)

                        if potential_end <= next_start:
                            return classroom_id, current_time.time(), potential_end.time()
                        current_time = datetime.strptime(str(bt[1]), "%H:%M:%S")
                return None, None, None

            classroom_id, time_start, time_end = try_schedule()

            if not classroom_id:
                return jsonify(success=False, message="No available classroom found. The schedule was not saved.")

            # Only insert course and schedule if slot was found
            cursor.execute("""
                INSERT INTO courses (course_id, course_name, students_num, lecturer_name)
                VALUES (%s, %s, %s, %s)
            """, (course_id, course_name, students_num, lecturer_name))

            cursor.execute("""
                INSERT INTO schedules (classroom_id, course_id, weekday, time_start, time_end, schedule_datetime)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                classroom_id,
                course_id,
                weekday,
                time_start,
                time_end,
                schedule_end_date if schedule_end_date else None
            ))

            db.commit()
            return jsonify(success=True)

    except Exception as e:
        return jsonify(success=False, message=str(e))



@app.route('/delete_data', methods=['POST'])
def delete_data():
    if not is_data_existing():
        flash('No data found to delete.')
        return redirect(url_for('upload'))

    delete_existing_data()
    flash('Existing data deleted successfully!')
    return redirect(url_for('upload'))


@app.route('/api/get_max_capacity')
def get_max_capacity():
    cursor = db.cursor()
    cursor.execute("SELECT MAX(capacity) FROM classrooms")
    result = cursor.fetchone()
    cursor.close()
    return jsonify({'max_capacity': result[0] or 0})

@app.route('/home')
def home():
    today = datetime.today().date()
    with db.cursor() as cursor:
        cursor.execute("DELETE FROM schedules WHERE schedule_datetime IS NOT NULL AND schedule_datetime < %s", (today,))
        db.commit()

    user_first_name = None
    if 'user_id' in session:
        with db.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT first_name FROM users WHERE user_id = %s", (session['user_id'],))
            user = cursor.fetchone()
            if user:
                user_first_name = user['first_name']

    return render_template('home.html', user_first_name=user_first_name)



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        with db.cursor(dictionary=True, buffered=True) as cursor:
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
        role = 'admin'
        permissions = 'standard'

        try:
            with db.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO users (first_name, last_name, email, password, role, permissions)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (first_name, last_name, email, password, role, permissions))
                db.commit()
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

    try:
        with db.cursor(dictionary=True) as cursor:
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

        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e))


@app.route('/interactive_schedule')
def interactive_schedule():
    return render_template('interactive_schedule.html')

@app.route('/api/update_course_info', methods=['POST'])
def update_course_info():
    data = request.get_json()
    course_id = data.get('course_id')
    course_name = data.get('course_name')
    lecturer_name = data.get('lecturer_name')
    students_num = data.get('students_num')

    try:
        with db.cursor() as cursor:
            cursor.execute("""
                UPDATE courses 
                SET course_name = %s, lecturer_name = %s, students_num = %s
                WHERE course_id = %s
            """, (course_name, lecturer_name, students_num, course_id))
        db.commit()
        return jsonify(success=True)
    except Exception as e:
        print(f"Error updating course info: {e}")
        return jsonify(success=False, message=str(e)), 500


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

        with db.cursor(dictionary=True) as cursor:
            # בדיקת התנגשויות
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
    with db.cursor(dictionary=True) as cursor:
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

    # עיבוד סוגי ערכים
    for key in schedule:
        val = schedule[key]
        if key in ["is_remote_learning", "is_sheltered"]:
            schedule[key] = "yes" if val in (1, "1", "yes", True) else "no"
        elif isinstance(val, (datetime, date)):
            schedule[key] = val.isoformat()
        elif isinstance(val, time):
            schedule[key] = val.strftime('%H:%M')
        elif isinstance(val, timedelta):
            schedule[key] = str(val)
        elif val is None:
            schedule[key] = ""

    # הוספת תמונות
    image_dir = os.path.join('uploads', 'img', schedule['building_name'], schedule['classroom_num'])
    images = []
    if os.path.exists(image_dir):
        for filename in sorted(os.listdir(image_dir)):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                encoded_building = schedule['building_name'].replace(" ", "%20")
                img_path = f"/uploads/img/{encoded_building}/{schedule['classroom_num']}/{filename}"
                images.append(img_path)
    schedule['images'] = images

    # גרסה שנייה של בדיקת תמונות
    classroom_num = schedule['classroom_num'].split('-')[-1]
    building_name = schedule['building_name']
    base_path = os.path.join('uploads', 'img', building_name, classroom_num)
    image_urls = []
    if os.path.exists(base_path):
        for filename in sorted(os.listdir(base_path)):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                image_urls.append(f'/uploads/img/{building_name}/{classroom_num}/{filename}')
    if image_urls:
        schedule['images'] = image_urls

    return jsonify(schedule)


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

    with db.cursor(dictionary=True) as cursor:
        cursor.execute("SELECT classroom_id, course_id FROM schedules WHERE schedule_id = %s", (schedule_id,))
        sched = cursor.fetchone()
        if not sched:
            return jsonify(success=False, message="Schedule not found")

        course_id = sched['course_id']

        cursor.execute("SELECT weekday, time_start, time_end FROM schedules WHERE schedule_id = %s", (schedule_id,))
        original = cursor.fetchone()
        time_changed = (
            original['weekday'] != weekday or
            str(original['time_start']) != time_start or
            str(original['time_end']) != time_end
        )

        # בדיקת זמינות מרצה
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

        # האם צריך להחריג את הכיתה הנוכחית?
        exclude_current_classroom = not time_changed

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

        if exclude_current_classroom:
            query += " AND c.classroom_id != %s"
            params.append(sched['classroom_id'])

        cursor.execute(query, tuple(params))
        available = cursor.fetchall()

        if not available:
            return jsonify(success=False, message="No available classrooms found")

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

            return jsonify(success=False, message="No available classroom matches the new constraints", available_classrooms=classroom_options)

        cursor.execute("SELECT classroom_id FROM classrooms WHERE classroom_num = %s", (selected_classroom_num,))
        classroom_row = cursor.fetchone()
        if not classroom_row:
            return jsonify(success=False, message="Selected classroom not found")

        new_classroom_id = classroom_row['classroom_id']

        # שמירת היסטוריית שינוי
        cursor.execute("""
            INSERT INTO schedule_history (
                schedule_id, course_id,
                old_classroom_id, new_classroom_id,
                old_weekday, new_weekday,
                old_time_start, new_time_start,
                old_time_end, new_time_end,
                updated_by_user_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            schedule_id,
            course_id,
            sched['classroom_id'], new_classroom_id,
            original['weekday'], weekday,
            original['time_start'], time_start,
            original['time_end'], time_end,
            session.get('user_id')
        ))

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



@app.route('/reports_statistics')
def reports_schedule():
    return render_template('reports_statistics.html')

@app.route('/delete_schedule', methods=['POST'])
def delete_schedule():
    data = request.get_json()
    schedule_id = data.get('schedule_id')
    course_id = data.get('course_id')

    try:
        with db.cursor() as cursor:
            # ✅ מחיקה גם מהיסטוריית שינויים
            cursor.execute("DELETE FROM schedule_history WHERE schedule_id = %s", (schedule_id,))

            # מחיקה מטבלת schedules
            cursor.execute("DELETE FROM schedules WHERE schedule_id = %s", (schedule_id,))
            # מחיקה מטבלת courses
            cursor.execute("DELETE FROM courses WHERE course_id = %s", (course_id,))
        db.commit()
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e))

@app.route('/api/classrooms')
def get_classrooms():
    cursor = db.cursor(dictionary=True)
    query = """
    SELECT c.*, b.building_name,
           (SELECT COUNT(*) FROM boards WHERE classroom_id = c.classroom_id) AS board_count
    FROM classrooms c
    JOIN buildings b ON c.building_id = b.building_id
    """
    cursor.execute(query)
    classrooms = cursor.fetchall()
    cursor.close()
    return jsonify(classrooms=classrooms)

@app.route('/api/update_classroom', methods=['POST'])
def update_classroom():
    data = request.get_json()
    classroom_id = data.get('classroom_id')
    floor_num = data.get('floor_num')
    capacity = data.get('capacity')
    is_remote_learning = data.get('is_remote_learning')
    is_sheltered = data.get('is_sheltered')
    board_count = data.get('board_count', 0)  # מספר לוחות חדש

    try:
        cursor = db.cursor()

        # עדכון נתוני הכיתה
        cursor.execute("""
            UPDATE classrooms
            SET floor_num = %s,
                capacity = %s,
                is_remote_learning = %s,
                is_sheltered = %s
            WHERE classroom_id = %s
        """, (floor_num, capacity, is_remote_learning, is_sheltered, classroom_id))

        # מחיקת כל הלוחות הקיימים עבור הכיתה
        cursor.execute("DELETE FROM boards WHERE classroom_id = %s", (classroom_id,))

        # הכנסת הלוחות החדשים עם גודל ברירת מחדל (נניח גודל 1)
        for _ in range(int(board_count)):
            cursor.execute("INSERT INTO boards (board_size, classroom_id) VALUES (%s, %s)", (1, classroom_id))

        db.commit()
        cursor.close()
        return jsonify(success=True)

    except Exception as e:
        return jsonify(success=False, message=str(e)), 500




@app.route('/uploads/img/<building>/<room>/<filename>')
def classroom_image(building, room, filename):
    folder_path = os.path.join('uploads', 'img', building, room)
    return send_from_directory(folder_path, filename)

@app.route('/api/add_classroom', methods=['POST'])
def add_classroom():
    data = request.get_json()
    classroom_num = data['classroom_num']
    floor_num = data['floor_num']
    capacity = data['capacity']
    is_remote_learning = data['is_remote_learning']
    is_sheltered = data['is_sheltered']
    board_count = int(data.get('board_count', 0))  # default 0 if missing
    building_choice = data['building_choice']
    building_name = data.get('building_name')
    building_id = data.get('building_id')

    try:
        cursor = db.cursor(dictionary=True)

        # Handle building
        if building_choice == 'new':
            num_floors = 1  # ערך ברירת מחדל כדי למנוע שגיאה
            cursor.execute("INSERT INTO buildings (building_name, num_floors) VALUES (%s, %s)", (building_name, num_floors))
            building_id = cursor.lastrowid

        elif not building_id:
            return jsonify(success=False, message="Missing building ID for existing building.")

        # Insert classroom
        cursor.execute("""
            INSERT INTO classrooms (classroom_num, floor_num, capacity, is_remote_learning, is_sheltered, building_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (classroom_num, floor_num, capacity, is_remote_learning, is_sheltered, building_id))

        classroom_id = cursor.lastrowid  # ID of the inserted classroom

        # Insert boards
        for _ in range(board_count):
            cursor.execute("INSERT INTO boards (classroom_id, board_size) VALUES (%s, %s)", (classroom_id, 1))

        db.commit()
        return jsonify(success=True)

    except Exception as e:
        return jsonify(success=False, message=str(e))

    finally:
        cursor.close()


@app.route('/api/delete_classroom/<int:classroom_id>', methods=['DELETE'])
def delete_classroom(classroom_id):
    try:
        cursor = db.cursor()

        # מחיקה מטבלת schedule_history
        cursor.execute("DELETE FROM schedule_history WHERE old_classroom_id = %s OR new_classroom_id = %s", (classroom_id, classroom_id))

        # מחיקה מטבלת schedules
        cursor.execute("DELETE FROM schedules WHERE classroom_id = %s", (classroom_id,))

        # מחיקה מטבלת boards
        cursor.execute("DELETE FROM boards WHERE classroom_id = %s", (classroom_id,))

        # מחיקה מטבלת classrooms
        cursor.execute("DELETE FROM classrooms WHERE classroom_id = %s", (classroom_id,))

        db.commit()
        cursor.close()
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500

@app.route('/api/schedules')
def api_schedules():
    try:
        db = get_connection() 
        with db.cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT 
                  s.schedule_id,
                  c.classroom_num,
                  b.building_name,
                  s.course_id,
                  cr.course_name,
                  cr.lecturer_name,
                  cr.students_num,
                  s.weekday,
                  s.time_start,
                  s.time_end,
                  c.is_remote_learning,
                  c.is_sheltered
                FROM schedules s
                JOIN classrooms c ON s.classroom_id = c.classroom_id
                JOIN buildings b ON c.building_id = b.building_id
                JOIN courses cr ON s.course_id = cr.course_id
            """)
            rows = cursor.fetchall()

        for row in rows:
            for key in row:
                val = row[key]
                if key in ["is_remote_learning", "is_sheltered"]:
                    row[key] = "yes" if val in (1, "1", "yes", True) else "no"
                elif isinstance(val, (datetime, date)):
                    row[key] = val.isoformat()
                elif isinstance(val, time):
                    row[key] = val.strftime("%H:%M")
                elif isinstance(val, timedelta):
                    row[key] = str(val)
                elif val is None:
                    row[key] = ""

        db.close()  
        return jsonify(schedules=rows)

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({"error": "Database error"}), 500

@app.route('/api/buildings')
def get_buildings():
    try:
        db = get_connection() 
        with db.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT building_id, building_name FROM buildings")
            buildings = cursor.fetchall()
        db.close()  
        return jsonify(buildings=buildings)

    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({"error": "Database error"}), 500



@app.route('/second_schedule')
def second_schedule():
    return render_template('second_schedule.html')

@app.route('/manage_classrooms')
def manage_classrooms():
    return render_template('manage_classrooms.html')

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)

