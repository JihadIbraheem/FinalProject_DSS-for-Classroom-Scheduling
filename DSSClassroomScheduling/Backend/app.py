from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask import jsonify, Response, send_from_directory
##########################
from flask import send_file
import io
from io import BytesIO
from flask import Blueprint
from io import BytesIO
from sqlalchemy import text
from openpyxl import Workbook
###########################
import os
import pandas as pd
import mysql.connector
from datetime import time
from datetime import datetime
import re
from datetime import date,  timedelta
import re 
import json
from flask import session
import traceback





app = Flask(__name__)

app.template_folder = '../Frontend/src/pages'
app.static_folder = '../Frontend/src'

app.secret_key = 'your_secret_key'

db = mysql.connector.connect(
    host="34.165.87.21",
    user="admin",
    password="Admin2025!", 
    database="classroom_scheduler"
)


###########################

def get_connection():
    return mysql.connector.connect(
        host="34.165.87.21",
        user="admin",
        password="Admin2025!",
        database="classroom_scheduler"
    )

reports_bp = Blueprint('reports', __name__)

@app.route('/api/classrooms_by_building')
def get_classrooms_by_building():
    building_name = request.args.get('building_name')
    if not building_name:
        return jsonify([])

    try:
        cursor = db.cursor(dictionary=True)
        query = """
            SELECT c.classroom_id, c.classroom_num, c.building_id
            FROM classrooms c
            JOIN buildings b ON c.building_id = b.building_id
            WHERE b.building_name = %s
        """
        cursor.execute(query, (building_name,))
        classrooms = cursor.fetchall()
        return jsonify(classrooms)
    except Exception as e:
        print("Error:", e)
        return jsonify([]), 500

@app.route('/api/average_students_by_shelter_status')
def average_students_by_shelter_status():
    try:
        day = request.args.get('day')

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                c.is_sheltered,
                AVG(co.students_num) AS avg_students,
                SUM(co.students_num) AS total_students
            FROM schedules s
            JOIN classrooms c ON s.classroom_id = c.classroom_id
            JOIN courses co ON s.course_id = co.course_id
            WHERE s.weekday = %s AND co.students_num IS NOT NULL
            GROUP BY c.is_sheltered
        """, (day,))
        results = cursor.fetchall()
        conn.close()

        sheltered_avg = 0
        not_sheltered_avg = 0
        sheltered_total = 0
        not_sheltered_total = 0

        for row in results:
            if int(row['is_sheltered']) == 1:
                sheltered_avg = row['avg_students']
                sheltered_total = row['total_students']
            else:
                not_sheltered_avg = row['avg_students']
                not_sheltered_total = row['total_students']

        return jsonify({
            'sheltered_avg': round(sheltered_avg or 0, 1),
            'not_sheltered_avg': round(not_sheltered_avg or 0, 1),
            'sheltered_total': sheltered_total or 0,
            'not_sheltered_total': not_sheltered_total or 0
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/students_per_day')
def students_per_day():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT s.weekday, SUM(co.students_num) AS total_students
            FROM schedules s
            JOIN courses co ON s.course_id = co.course_id
            WHERE co.students_num IS NOT NULL
            GROUP BY s.weekday
        """)
        results = cursor.fetchall()
        conn.close()

        # סדר ימי השבוע לפי סדר עברי רגיל
        days_order = ["א'", "ב'", "ג'", "ד'", "ה'", "ו'"]
        day_names = {d: 0 for d in days_order}

        for row in results:
            day = row['weekday']
            if day in day_names:
                day_names[day] = int(row['total_students'])

        return jsonify(day_names)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/course_distribution')
def course_distribution():
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT course_id FROM courses")
    rows = cursor.fetchall()

    cs = sum(1 for row in rows if str(row['course_id']).startswith('203'))
    is_ = sum(1 for row in rows if str(row['course_id']).startswith('214'))
    other = len(rows) - cs - is_

    return jsonify({
        "Computer Science": cs,
        "Information Systems": is_,
        "Other": other
    })

@app.route('/api/hourly_students_by_day')
def hourly_students_by_day():
    try:
        day = request.args.get('day')
        if not day:
            return jsonify({'error': 'Missing day parameter'}), 400

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # שימוש ב-HOUR() במקום TIME_FORMAT כדי להימנע מבעיות עם %
        query = """
            SELECT
                HOUR(s.time_start) AS start_hour,
                HOUR(s.time_end) AS end_hour,
                co.students_num
            FROM schedules s
            JOIN courses co ON s.course_id = co.course_id
            WHERE s.weekday = %s
              AND co.students_num IS NOT NULL
        """

        cursor.execute(query, (day,))
        rows = cursor.fetchall()
        conn.close()

        # מילון של שעות עם ערך התחלתי 0
        hourly_counts = {str(h).zfill(2): 0 for h in range(8, 21)}

        # חישוב העומס לפי כל שעה בה השיעור פעיל
        for row in rows:
            start_hour = row['start_hour']
            end_hour = row['end_hour']
            students = row['students_num']

            for h in range(start_hour, end_hour):
                h_str = str(h).zfill(2)
                if h_str in hourly_counts:
                    hourly_counts[h_str] += students

        return jsonify(hourly_counts)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# API to fetch buildings list for frontend dropdown
@app.route('/api/buildings', methods=['GET'])
def fetch_buildings_for_dropdown():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT building_id, building_name FROM buildings")
    buildings = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(buildings)

# Reports route to render the frontend
@app.route('/reports_statistics', methods=['GET'])
def reports_statistics():
    return render_template('reports_statistics.html')

# Main Report Generation Handler
@app.route('/generate_report', methods=['POST'])
def generate_report():
    report_type = request.form.get('report_type')
    building_id = request.form.get('building_id')
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    output = io.BytesIO()

    if report_type == 'utilization':
        building_filter = ''
        filter_value = ()
        if building_id and building_id != 'all':
            building_filter = 'WHERE c.building_id = %s'
            filter_value = (building_id,)

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM classrooms c
            JOIN buildings b ON c.building_id = b.building_id
            {}""".format(building_filter), filter_value)
        total = cursor.fetchone()['total']

        cursor.execute("""
            SELECT COUNT(DISTINCT c.classroom_id) AS used
            FROM schedules s
            JOIN classrooms c ON s.classroom_id = c.classroom_id
            JOIN buildings b ON c.building_id = b.building_id
            {}""".format(building_filter), filter_value)
        used = cursor.fetchone()['used']

        cursor.execute("""
            SELECT AVG(cnt) as avg_daily FROM (
                SELECT COUNT(*) as cnt
                FROM schedules s
                JOIN classrooms c ON s.classroom_id = c.classroom_id
                JOIN buildings b ON c.building_id = b.building_id
                {}
                GROUP BY s.weekday
            ) sub
        """.format(building_filter), filter_value)
        row = cursor.fetchone()
        avg_daily = round(row['avg_daily'], 2) if row and row['avg_daily'] is not None else 0


        cursor.execute("""
            SELECT HOUR(s.time_start) AS hour, COUNT(*) AS cnt
            FROM schedules s
            JOIN classrooms c ON s.classroom_id = c.classroom_id
            JOIN buildings b ON c.building_id = b.building_id
            {}
            GROUP BY hour
            ORDER BY cnt DESC LIMIT 1
        """.format(building_filter), filter_value)
        row = cursor.fetchone()
        peak_hour = f"{row['hour']}:00" if row and row['hour'] is not None else 'N/A'


        cursor.execute("""
            SELECT COUNT(*) AS underutilized
            FROM classrooms c
            LEFT JOIN schedules s ON s.classroom_id = c.classroom_id
            JOIN buildings b ON c.building_id = b.building_id
            WHERE s.classroom_id IS NULL {}
        """.format(f"AND c.building_id = %s" if building_id != 'all' else ''), filter_value)
        underutilized = cursor.fetchone()['underutilized']

        total_available_hours = total * 10 * 6
        total_used_hours = used * avg_daily
        overall_utilization_rate = (total_used_hours / total_available_hours) * 100 if total_available_hours else 0

        summary_df = pd.DataFrame([{
            "Total Classrooms": total,
            "Utilized Classrooms": used,
            "Average Daily Usage Rate": avg_daily,
            "Peak Usage Hour": peak_hour,
            "Underutilized Classrooms": underutilized,
            "Overall Utilization Rate (%)": round(overall_utilization_rate, 2)
        }])

        building_query = """
            SELECT 
                b.building_name,
                COUNT(DISTINCT c.classroom_id) AS `# Classrooms`,
                ROUND(SUM(CASE WHEN s.schedule_id IS NOT NULL THEN 1 ELSE 0 END)/6, 2) AS `Avg. Utilization`,
                (
                    SELECT s2.weekday
                    FROM schedules s2
                    JOIN classrooms c2 ON s2.classroom_id = c2.classroom_id
                    WHERE c2.building_id = b.building_id
                    GROUP BY s2.weekday
                    ORDER BY COUNT(*) DESC
                    LIMIT 1
                ) AS `Peak Day`,
                GROUP_CONCAT(DISTINCT IF(s.schedule_id IS NULL, c.classroom_num, NULL)) AS `Underutilized Room`
            FROM buildings b
            JOIN classrooms c ON c.building_id = b.building_id
            LEFT JOIN schedules s ON s.classroom_id = c.classroom_id
        """

        if building_id != 'all':
            building_query += " WHERE b.building_id = %s"
            building_query += " GROUP BY b.building_id"
            building_df = pd.read_sql(building_query, conn, params=(building_id,))
        else:
            building_query += " GROUP BY b.building_id"
            building_df = pd.read_sql(building_query, conn)

        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            summary_df.to_excel(writer, sheet_name='Campus Summary', index=False)
            building_df.to_excel(writer, sheet_name='Utilization by Building', index=False)

            workbook = writer.book
            summary_sheet = writer.sheets['Campus Summary']
            red_format = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})
            green_format = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'})

            summary_sheet.conditional_format('F2', {
                'type': 'cell', 'criteria': '<', 'value': 30, 'format': red_format
            })
            summary_sheet.conditional_format('F2', {
                'type': 'cell', 'criteria': '>=', 'value': 70, 'format': green_format
            })

    elif report_type == 'estimated_students':
        df = pd.read_sql("""
            SELECT 
                b.building_name AS `Building Name`,
                SUM(c2.students_num) AS `Estimated Students`,
                ROUND(AVG(c2.students_num), 2) AS `Average per Room`,
                pd.peak_day AS `Peak Day`
            FROM buildings b
            JOIN classrooms c ON c.building_id = b.building_id
            JOIN schedules s ON s.classroom_id = c.classroom_id
            JOIN courses c2 ON s.course_id = c2.course_id
            LEFT JOIN (
                SELECT building_id, weekday AS peak_day
                FROM (
                    SELECT c.building_id, s.weekday,
                           ROW_NUMBER() OVER (PARTITION BY c.building_id ORDER BY COUNT(*) DESC) as rn
                    FROM classrooms c
                    JOIN schedules s ON s.classroom_id = c.classroom_id
                    GROUP BY c.building_id, s.weekday
                ) sub
                WHERE rn = 1
            ) pd ON pd.building_id = b.building_id
            GROUP BY b.building_id, pd.peak_day
        """, conn)

        day_map = {
    'א': 'Sunday', 'ב': 'Monday', 'ג': 'Tuesday',
    'ד': 'Wednesday', 'ה': 'Thursday', 'ו': 'Friday', 'ש': 'Saturday',
    '0': 'Sunday', '1': 'Monday', '2': 'Tuesday',
    '3': 'Wednesday', '4': 'Thursday', '5': 'Friday', '6': 'Saturday'
    }
        df['Peak Day'] = df['Peak Day'].astype(str).str.strip().map(day_map).fillna(df['Peak Day'])


        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Estimated Students Summary', index=False)

            workbook = writer.book
            worksheet = writer.sheets['Estimated Students Summary']

            red = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})
            yellow = workbook.add_format({'bg_color': '#FFEB9C', 'font_color': '#9C6500'})
            green = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'})

            worksheet.conditional_format('B2:B100', {'type': 'cell', 'criteria': '<', 'value': 300, 'format': red})
            worksheet.conditional_format('B2:B100', {'type': 'cell', 'criteria': 'between', 'minimum': 300, 'maximum': 1000, 'format': yellow})
            worksheet.conditional_format('B2:B100', {'type': 'cell', 'criteria': '>', 'value': 1000, 'format': green})

            chart = workbook.add_chart({'type': 'column'})
            chart.add_series({
                'name': 'Estimated Students',
                'categories': ['Estimated Students Summary', 1, 0, len(df), 0],
                'values':     ['Estimated Students Summary', 1, 1, len(df), 1],
            })
            chart.set_title({'name': 'Estimated Students per Building'})
            chart.set_x_axis({'name': 'Building'})
            chart.set_y_axis({'name': 'Students'})
            worksheet.insert_chart('F2', chart)

    elif report_type == 'history':
        if building_id and building_id != 'all':
            df = pd.read_sql("""
                SELECT 
                    sh.course_id,
                    CONCAT(RIGHT(co_old.classroom_num, 3), ' - ', b_old.building_name) AS old_classroom,
                    CONCAT(RIGHT(co_new.classroom_num, 3), ' - ', b_new.building_name) AS new_classroom,
                    sh.old_weekday,
                    sh.new_weekday,
                    TIME_FORMAT(sh.old_time_start, '%H:%i') AS old_time_start,
                    TIME_FORMAT(sh.old_time_end, '%H:%i') AS old_time_end,
                    TIME_FORMAT(sh.new_time_start, '%H:%i') AS new_time_start,
                    TIME_FORMAT(sh.new_time_end, '%H:%i') AS new_time_end,
                    u.first_name AS updated_by
                FROM schedule_history sh
                LEFT JOIN classrooms co_old ON sh.old_classroom_id = co_old.classroom_id
                LEFT JOIN buildings b_old ON co_old.building_id = b_old.building_id
                LEFT JOIN classrooms co_new ON sh.new_classroom_id = co_new.classroom_id
                LEFT JOIN buildings b_new ON co_new.building_id = b_new.building_id
                LEFT JOIN users u ON sh.updated_by_user_id = u.user_id
                WHERE b_old.building_id = %s OR b_new.building_id = %s
            """, conn, params=(building_id, building_id))
        else:
            df = pd.read_sql("""
                SELECT 
                    sh.course_id,
                    CONCAT(RIGHT(co_old.classroom_num, 3), ' - ', b_old.building_name) AS old_classroom,
                    CONCAT(RIGHT(co_new.classroom_num, 3), ' - ', b_new.building_name) AS new_classroom,
                    sh.old_weekday,
                    sh.new_weekday,
                    TIME_FORMAT(sh.old_time_start, '%H:%i') AS old_time_start,
                    TIME_FORMAT(sh.old_time_end, '%H:%i') AS old_time_end,
                    TIME_FORMAT(sh.new_time_start, '%H:%i') AS new_time_start,
                    TIME_FORMAT(sh.new_time_end, '%H:%i') AS new_time_end,
                    u.first_name AS updated_by
                FROM schedule_history sh
                LEFT JOIN classrooms co_old ON sh.old_classroom_id = co_old.classroom_id
                LEFT JOIN buildings b_old ON co_old.building_id = b_old.building_id
                LEFT JOIN classrooms co_new ON sh.new_classroom_id = co_new.classroom_id
                LEFT JOIN buildings b_new ON co_new.building_id = b_new.building_id
                LEFT JOIN users u ON sh.updated_by_user_id = u.user_id
            """, conn)

        df.to_excel(output, index=False, sheet_name="Changes & Rescheduling History")

    elif report_type == 'students_by_hour':
        query = """
            SELECT 
                b.building_name,
                c.classroom_num,
                c.capacity,
                s.weekday,
                s.time_start,
                s.time_end,
                co.students_num AS enrolled_students
            FROM schedules s
            JOIN classrooms c ON s.classroom_id = c.classroom_id
            JOIN buildings b ON c.building_id = b.building_id
            JOIN courses co ON s.course_id = co.course_id
        """
        params = ()

        if building_id and building_id.lower() != 'all':
            query += " WHERE b.building_id = %s"
            params = (building_id,)

        df = pd.read_sql(query, conn, params=params)

        if df.empty:
            return "No data found for this building", 404

        df['start_hour'] = df['time_start'].dt.components['hours']
        df['end_hour'] = df['time_end'].dt.components['hours']
        df['hour_range'] = df.apply(lambda row: list(range(row['start_hour'], row['end_hour'])), axis=1)

        expanded_rows = []
        for _, row in df.iterrows():
            for h in row['hour_range']:
                expanded_rows.append({
                    'Classroom': row['classroom_num'],
                    'Building': row['building_name'],
                    'Capacity': row['capacity'],
                    'Weekday': row['weekday'],
                    'Hour': f"{h:02d}:00",
                    'Students': row['enrolled_students']
                })

        result_df = pd.DataFrame(expanded_rows)

        grouped = result_df.groupby(
            ['Classroom', 'Building', 'Capacity', 'Weekday', 'Hour']
        )['Students'].sum().reset_index()

        grouped['Students'] = grouped.apply(
            lambda row: min(row['Students'], row['Capacity']),
            axis=1
        )

        # יצירת Pivot לפי שעות
        pivot = grouped.pivot_table(
            index=['Classroom', 'Building', 'Capacity', 'Weekday'],
            columns='Hour',
            values='Students',
            aggfunc='sum',
            fill_value=0
        )
        pivot.reset_index(inplace=True)

        # חישוב ממוצע ניצול ואחוזים
        pivot['Avg. Hourly Utilization (%)'] = pivot.apply(
            lambda row: round(
                sum([v for k, v in row.items() if isinstance(k, str) and ':' in k]) / (row['Capacity'] * len([k for k in row.keys() if isinstance(k, str) and ':' in k])) * 100
                if row['Capacity'] > 0 else 0, 2
            ),
            axis=1
        )

        # חישוב שעת שיא (Peak Hour)
        def get_peak_hour(row):
            hourly = {k: v for k, v in row.items() if isinstance(k, str) and ':' in k}
            return max(hourly, key=hourly.get) if hourly else 'N/A'

        pivot['Peak Hour'] = pivot.apply(get_peak_hour, axis=1)

        # גיליון summary
        summary_df = pd.DataFrame([{
            'Most Utilized Hour (Campus)': grouped.groupby('Hour')['Students'].sum().idxmax(),
            'Avg. Utilization Across Campus (%)': round(
                grouped['Students'].sum() / grouped['Capacity'].sum() * 100, 2
            ) if grouped['Capacity'].sum() > 0 else 0,
            'Most Utilized Classroom': grouped.groupby('Classroom')['Students'].sum().idxmax()
        }])

        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            pivot.to_excel(writer, index=False, sheet_name='Students by Hour')
            summary_df.to_excel(writer, index=False, sheet_name='Summary')

            workbook = writer.book
            sheet = writer.sheets['Students by Hour']

            # עיצוב מותנה לפי אחוז ניצול
            green = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'})
            yellow = workbook.add_format({'bg_color': '#FFEB9C', 'font_color': '#9C6500'})
            red = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})

            sheet.conditional_format('Z2:Z1000', {
                'type': 'cell', 'criteria': '>=', 'value': 70, 'format': green
            })
            sheet.conditional_format('Z2:Z1000', {
                'type': 'cell', 'criteria': 'between', 'minimum': 30, 'maximum': 69, 'format': yellow
            })
            sheet.conditional_format('Z2:Z1000', {
                'type': 'cell', 'criteria': '<', 'value': 30, 'format': red
            })

    elif report_type == 'lecturer_utilization':
        df = pd.read_sql("""
            SELECT 
                co.lecturer_name AS `Lecturer`,
                COUNT(*) AS `Number of Lessons`,
                COUNT(DISTINCT s.weekday) AS `Days Teaching`,
                COUNT(DISTINCT s.time_start) AS `Unique Start Times`
            FROM schedules s
            JOIN courses co ON s.course_id = co.course_id
            GROUP BY co.lecturer_name
            ORDER BY `Number of Lessons` DESC
        """, conn)

        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Lecturer Utilization')

            workbook = writer.book
            worksheet = writer.sheets['Lecturer Utilization']

            # הגרף - Top 10 עם תוויות
            chart = workbook.add_chart({'type': 'column'})

            chart.add_series({
                'name': 'Number of Lessons',
                'categories': ['Lecturer Utilization', 1, 0, 10, 0],  # שמות המרצים
                'values':     ['Lecturer Utilization', 1, 1, 10, 1],  # מספר שיעורים
                'data_labels': {'value': True},  # תוויות ערכים
            })

            chart.set_title({'name': 'מספר שיעורים – 10 מרצים ראשונים'})
            chart.set_x_axis({
                'name': 'מרצה',
                'label_position': 'low',
                'num_font': {'rotation': -45},  # סיבוב הטקסט בעברית
            })
            chart.set_y_axis({'name': 'כמות שיעורים'})

            chart.set_legend({'position': 'bottom'})
            chart.set_style(10)

            worksheet.insert_chart('F2', chart)

    else:
        return "Invalid report type", 400

    output.seek(0)
    cursor.close()
    conn.close()
    return send_file(output, download_name=f"{report_type}_report.xlsx", as_attachment=True)

###########################


@app.route('/api/classroom_shelter_status')
def classroom_shelter_status():
    building_id = request.args.get('building_id')
    if not building_id:
        return jsonify([])

    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT classroom_num AS Classroom,
               is_sheltered AS Sheltered
        FROM classrooms
        WHERE building_id = %s
    """, (building_id,))
    
    data = cursor.fetchall()
    return jsonify(data)


@app.route('/')
def default_home():
    return redirect(url_for('login'))

@app.route('/manual_schedule', methods=['POST'])
def manual_schedule():
    if is_data_existing():
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

        remote_raw = remote_flags[i].strip().lower()
        sheltered_raw = sheltered_flags[i].strip().lower()

        is_remote_any = remote_raw == 'any'
        is_sheltered_any = sheltered_raw == 'any'

        is_remote = 1 if remote_raw in ['1', 'true', 'yes', 'on'] else 0
        is_sheltered = 1 if sheltered_raw in ['1', 'true', 'yes', 'on'] else 0

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

        # יצירת שאילתת חיפוש כיתות לפי אילוצים
        query = "SELECT classroom_id, capacity, is_remote_learning, is_sheltered FROM classrooms WHERE capacity >= %s"
        params = [students_num]

        if not is_remote_any:
            query += " AND is_remote_learning = %s"
            params.append(is_remote)

        if not is_sheltered_any:
            query += " AND is_sheltered = %s"
            params.append(is_sheltered)

        query += " ORDER BY capacity ASC"

        cursor.execute(query, tuple(params))
        classrooms = cursor.fetchall()
        scheduled, classroom_used = try_schedule_with_classrooms([(c[0],) for c in classrooms])

        if not scheduled:
            # ניסיון רפוי מגבלות
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
                        if not is_remote_any and str(c[2]) != str(is_remote):
                            mismatches.append("remote learning mismatch")
                        if not is_sheltered_any and str(c[3]) != str(is_sheltered):
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


def split_multiple_courses(cell_text):
    parts = cell_text.split('}')
    courses = []
    for i in range(len(parts)):
        if i == 0:
            courses.append(parts[i] + '}')  # הראשון כולל הסוגר
        elif i < len(parts) and parts[i].strip():
            courses.append(parts[i].strip() + '}')
    return courses

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
    
@app.route('/resolve_conflicts', methods=['GET', 'POST'])
def resolve_conflicts():
    conflicts = session.get('pending_conflicts', [])

    if not conflicts:
        flash('No pending conflicts to resolve.')
        return redirect(url_for('upload'))

    if request.method == 'POST':
        selected_classroom_id = request.form.get('selected_classroom')
        course_data = json.loads(request.form.get('course_data'))
        weekday = request.form.get('weekday')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')

        if not selected_classroom_id or not selected_classroom_id.strip().isdigit():
            flash("נבחר ערך לא תקין לכיתה. אנא בחר/י כיתה תקינה.")
            return redirect(url_for('resolve_conflicts'))
        
        selected_classroom_id = int(selected_classroom_id)

        # 🟢 הכנס קודם לקורסים (אם לא קיים)
        with db.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM courses WHERE course_id = %s", (course_data['course_id'],))
            exists = cursor.fetchone()[0]
            if not exists:
                cursor.execute("""
                    INSERT INTO courses (course_id, course_name, students_num)
                    VALUES (%s, %s, %s)
                """, (
                    course_data['course_id'],
                    course_data['course_name'],
                    course_data['students_num']
                ))
                db.commit()

        # ✅ רק עכשיו הכנס לשיבוצים
        with db.cursor() as cursor:
            cursor.execute("""
                INSERT INTO schedules (classroom_id, course_id, weekday, time_start, time_end)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                selected_classroom_id,
                course_data['course_id'],
                weekday,
                start_time,
                end_time
            ))
            db.commit()

        # הסרת הקונפליקט מהתור
        session['pending_conflicts'] = conflicts[1:]
        session.modified = True

        if session['pending_conflicts']:
            return redirect(url_for('resolve_conflicts'))
        else:
            flash("All conflicts resolved successfully.")
            return redirect(url_for('upload'))

    # GET – הצגת הקונפליקט הנוכחי
    current_conflict = conflicts[0]
    course_data = current_conflict['course_data']
    suggested_classroom = current_conflict.get('suggested_classroom')
    weekday = current_conflict['weekday']
    start_time = current_conflict['start_time']
    end_time = current_conflict['end_time']

    return render_template('resolve_conflict.html',
                           conflict=current_conflict,
                           course_data=course_data,
                           suggested_classroom=suggested_classroom,
                           weekday=weekday,
                           start_time=start_time,
                           end_time=end_time)

def find_available_classrooms(conflict, all_matches=False):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    weekday = conflict['weekday']
    start_time = conflict['start_time']
    end_time = conflict['end_time']
    students_num = int(conflict.get('students_num', 0))

    if isinstance(start_time, str):
        if len(start_time) == 5:
            start_time += ":00"
        start_time = datetime.strptime(start_time, "%H:%M:%S").time()

    if isinstance(end_time, str):
        if len(end_time) == 5:
            end_time += ":00"
        end_time = datetime.strptime(end_time, "%H:%M:%S").time()

    query_base = """
        SELECT c.*, b.building_name
        FROM classrooms c
        JOIN buildings b ON c.building_id = b.building_id
        WHERE {capacity_clause}
          AND c.classroom_id NOT IN (
              SELECT classroom_id
              FROM schedules
              WHERE weekday = %s
                AND NOT (time_end <= %s OR time_start >= %s)
          )
        ORDER BY c.capacity {order}
        {limit}
    """

    if all_matches:
        query = query_base.format(capacity_clause="c.capacity >= %s", order="ASC", limit="")
        cursor.execute(query, (students_num, weekday, start_time, end_time))
        results = cursor.fetchall()
        conn.close()

        for r in results:
            r['reason'] = 'strict'
            r['is_remote_learning'] = bool(int(r.get('is_remote_learning') or 0))
            r['is_sheltered'] = bool(int(r.get('is_sheltered') or 0))

        return results

    query = query_base.format(capacity_clause="c.capacity >= %s", order="ASC", limit="LIMIT 1")
    cursor.execute(query, (students_num, weekday, start_time, end_time))
    result = cursor.fetchone()

    if result:
        conn.close()
        result['reason'] = 'strict'
        result['is_remote_learning'] = bool(int(result.get('is_remote_learning') or 0))
        result['is_sheltered'] = bool(int(result.get('is_sheltered') or 0))
        return [result]

    fallback_query = query_base.format(capacity_clause="1", order="DESC", limit="LIMIT 1")
    cursor.execute(fallback_query, (weekday, start_time, end_time))
    fallback = cursor.fetchone()
    conn.close()

    if fallback:
        fallback['reason'] = 'fallback'
        fallback['is_remote_learning'] = bool(int(fallback.get('is_remote_learning') or 0))
        fallback['is_sheltered'] = bool(int(fallback.get('is_sheltered') or 0))
        return [fallback]

    return []


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

@app.route('/resolve_conflict_direct', methods=['POST'])
def resolve_conflict_direct():
    try:
        selected_classroom_id = request.form.get('selected_classroom')
        course_data = json.loads(request.form.get('course_data'))
        weekday = request.form.get('weekday')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')

        if not selected_classroom_id or not selected_classroom_id.strip().isdigit():
            flash("נבחר ערך לא תקין לכיתה. אנא בחר/י כיתה תקינה.")
            return redirect(url_for('upload'))

        selected_classroom_id = int(selected_classroom_id)

        # הכנס קורס אם לא קיים
        with db.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM courses WHERE course_id = %s", (course_data['course_id'],))
            exists = cursor.fetchone()[0]
            if not exists:
                cursor.execute("""
                    INSERT INTO courses (course_id, course_name, students_num)
                    VALUES (%s, %s, %s)
                """, (
                    course_data['course_id'],
                    course_data['course_name'],
                    course_data['students_num']
                ))
                db.commit()

        # הכנס לשיבוץ
        with db.cursor() as cursor:
            cursor.execute("""
                INSERT INTO schedules (classroom_id, course_id, weekday, time_start, time_end)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                selected_classroom_id,
                course_data['course_id'],
                weekday,
                start_time,
                end_time
            ))
            db.commit()

        # הסר את הקונפליקט המתאים בלבד
        pending_conflicts = session.get('pending_conflicts', [])
        updated_conflicts = []

        for conflict in pending_conflicts:
            if not (
                conflict['course_data']['course_id'] == course_data['course_id'] and
                conflict['weekday'] == weekday and
                conflict['start_time'] == start_time and
                conflict['end_time'] == end_time
            ):
                updated_conflicts.append(conflict)

        session['pending_conflicts'] = updated_conflicts

        flash("Scheduling confirmed successfully ✅")
        return redirect(url_for('upload'))

    except Exception as e:
        flash(f"Error during scheduling: {e}")
        return redirect(url_for('upload'))

def insert_conflict_to_db(classroom_id, course_data, weekday, start_time, end_time):
    with db.cursor() as cursor:
        # הכנס לקורסים
        cursor.execute("""
            INSERT INTO courses (course_id, course_name, lecturer_name, students_num)
            VALUES (%s, %s, %s, %s)
        """, (course_data['course_id'], course_data['course_name'],
              course_data['lecturer_name'], course_data['students_num']))
        course_db_id = cursor.lastrowid

        # הכנס לשיבוץ
        cursor.execute("""
            INSERT INTO schedules (course_id, classroom_id, weekday, start_time, end_time, status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (course_db_id, classroom_id, weekday, start_time, end_time, 'Confirmed'))

        db.commit()

def process_file(file, return_raw_df=False):
    import pandas as pd
    from flask import session

    df = pd.read_excel(file)
    df.columns = df.columns.map(lambda x: str(x).strip())

    required_columns = {'יום', 'חדר', 'בניין', 'קיבולת'}
    if not required_columns.issubset(set(df.columns)):
        raise ValueError(f"Missing required columns. Found columns: {list(df.columns)}. Required: {list(required_columns)}")

    for col in ['יום', 'חדר', 'בניין']:
        if df[col].isnull().any() or (df[col].astype(str).str.strip() == "").any():
            raise ValueError(f"Empty values found in required column: '{col}'")

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
    pending_conflicts = []

    for i, row in df.iterrows():
        weekday = row['יום']
        classroom_id = str(row['חדר']).strip()

        for slot in time_slots:
            cell_text = row[slot]
            if pd.notna(cell_text):
                cell_text = str(cell_text).strip()
                if cell_text == '' or cell_text == slot:
                    continue

                try:
                    start_time, end_time = slot.split('-')
                    start_time = start_time.strip()
                    end_time = end_time.strip()
                except ValueError:
                    continue

                if cell_text.count('}') >= 2:
                    all_parts = split_multiple_courses(cell_text)

                    for idx, part in enumerate(all_parts):
                        course_data = extract_course_details(part)
                        if not course_data:
                            continue

                        required_fields = ['course_id', 'students_num', 'course_name']
                        if any(field not in course_data or str(course_data[field]).strip() == '' for field in required_fields):
                            raise ValueError(f"Missing required field in part {idx+1} at row {i+2}, column '{slot}': '{part}'")

                        if idx == 0:
                            schedule_rows.append({
                                'classroom_id': classroom_id,
                                'course_id': course_data['course_id'],
                                'weekday': weekday,
                                'status': 'Confirmed',
                                'time_start': start_time + ':00',
                                'time_end': end_time + ':00'
                            })
                            course_rows.append(course_data)
                        else:
                            available = find_available_classrooms({
                                'weekday': weekday,
                                'start_time': start_time + ':00',
                                'end_time': end_time + ':00',
                                'students_num': course_data['students_num']
                            })

                            if not available:
                                fallback = find_available_classrooms({
                                    'weekday': weekday,
                                    'start_time': start_time + ':00',
                                    'end_time': end_time + ':00',
                                    'students_num': 0
                                })

                                if fallback:
                                    fallback.sort(key=lambda x: x['capacity'], reverse=True)
                                    available = [fallback[0]]
                                else:
                                    available = []

                            pending_conflicts.append({
                                'original_classroom_id': classroom_id,
                                'weekday': weekday,
                                'start_time': start_time + ':00',
                                'end_time': end_time + ':00',
                                'course_data': course_data,
                                'suggested_classroom': available[0] if available else None
                            })

                    continue

                course_data = extract_course_details(cell_text)
                if not course_data:
                    raise ValueError(f"Invalid course format at row {i+2}, column '{slot}': '{cell_text}'")

                required_fields = ['course_id', 'students_num', 'course_name']
                for field in required_fields:
                    if field not in course_data or str(course_data[field]).strip() == '':
                        raise ValueError(f"Missing required field '{field}' at row {i+2}, column '{slot}': '{cell_text}'")

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

    # שמור את הקונפליקטים ב-session
    session['pending_conflicts'] = merge_conflicts(pending_conflicts)

    if return_raw_df:
        return schedule_df, courses_df, df

    return schedule_df, courses_df, pending_conflicts


def merge_conflicts(conflicts):
    merged = []
    conflicts.sort(key=lambda x: (x['course_data']['course_id'], x['weekday'], x['start_time']))

    for conflict in conflicts:
        if not merged:
            merged.append(conflict)
            continue

        last = merged[-1]

        same_course = conflict['course_data']['course_id'] == last['course_data']['course_id']
        same_day = conflict['weekday'] == last['weekday']

        last_end = datetime.strptime(last['end_time'], "%H:%M:%S")
        current_start = datetime.strptime(conflict['start_time'], "%H:%M:%S")

        if same_course and same_day and last_end == current_start:
            # עדכון הזמן של ה־end_time
            merged[-1]['end_time'] = conflict['end_time']
        else:
            merged.append(conflict)

    return merged

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    from flask import session
    upload_status = None

    if request.method == 'POST':
        if request.form.get('action') == 'view_classrooms':
            try:
                conflict_index = int(request.form.get('conflict_index'))
                weekday = request.form.get('weekday')
                start_time_str = request.form.get('start_time', '').strip()
                end_time_str = request.form.get('end_time', '').strip()
                course_data = json.loads(request.form.get('course_data'))

                if not start_time_str or not end_time_str:
                    raise ValueError("Missing start_time or end_time")

                # הבטחת פורמט אחיד HH:MM:SS
                if len(start_time_str) == 5:
                    start_time_str += ":00"
                if len(end_time_str) == 5:
                    end_time_str += ":00"

                # חיפוש כל הכיתות האפשריות
                available_classrooms = find_available_classrooms({
                    'weekday': weekday,
                    'start_time': start_time_str,
                    'end_time': end_time_str,
                    'students_num': course_data.get('students_num', 0)
                }, all_matches=True)

                pending_conflicts = session.get('pending_conflicts', [])
                if 0 <= conflict_index < len(pending_conflicts):
                    pending_conflicts[conflict_index]['available_options'] = available_classrooms
                    session['pending_conflicts'] = pending_conflicts

                upload_status = 'conflict'
                return render_template('upload.html',
                                       data_exists=is_data_existing(),
                                       upload_status=upload_status,
                                       conflicts=pending_conflicts)
            except Exception as e:
                flash(f'Error while fetching available classrooms: {e}')
                return redirect(url_for('upload'))

        # העלאה רגילה
        if is_data_existing():
            return redirect(url_for('upload'))

        file = request.files['file']
        if not file:
            flash('No file selected!')
            return redirect(url_for('upload'))

        try:
            schedule_data, course_data, _ = process_file(file)
            insert_courses_to_db(course_data)
            insert_data_to_db(schedule_data)

            conflicts = session.get('pending_conflicts', [])
            if conflicts:
                upload_status = 'conflict'
                return render_template('upload.html',
                                       data_exists=is_data_existing(),
                                       upload_status=upload_status,
                                       conflicts=conflicts)

            upload_status = 'success'
            flash('File uploaded and data inserted successfully!')
        except Exception as e:
            upload_status = 'error'
            flash(f'An error occurred: {e}')

    data_exists = is_data_existing()
    conflicts = session.get('pending_conflicts', [])
    return render_template('upload.html',
                           data_exists=data_exists,
                           upload_status=upload_status,
                           conflicts=conflicts)

@app.route('/reject_conflict_direct', methods=['POST'])
def reject_conflict_direct():
    try:
        course_data = json.loads(request.form.get('course_data'))
        weekday = request.form.get('weekday')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')

        pending_conflicts = session.get('pending_conflicts', [])

        # סנן החוצה את הקונפליקט שנדחה
        updated_conflicts = [
            c for c in pending_conflicts
            if not (
                c['course_data']['course_id'] == course_data['course_id'] and
                c['weekday'] == weekday and
                c['start_time'] == start_time and
                c['end_time'] == end_time
            )
        ]

        session['pending_conflicts'] = updated_conflicts

        if updated_conflicts:
            flash("Conflict rejected successfully ❌")
            return redirect(url_for('upload'))
        else:
            flash("All conflicts resolved or dismissed ✅")
            return redirect(url_for('upload'))

    except Exception as e:
        flash(f"Error rejecting conflict: {e}")
        return redirect(url_for('upload'))



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
        schedule_end_date = data.get('schedule_end_date')

        # פענוח הערכים של Remote Learning ו-Sheltered
        is_remote_raw = str(data['is_remote_learning']).strip().lower()
        is_sheltered_raw = str(data['is_sheltered']).strip().lower()

        # המרה לערכים לוגיים או None אם 'any'
        is_remote = None
        if is_remote_raw == 'yes':
            is_remote = 1
        elif is_remote_raw == 'no':
            is_remote = 0

        is_sheltered = None
        if is_sheltered_raw == 'yes':
            is_sheltered = 1
        elif is_sheltered_raw == 'no':
            is_sheltered = 0

        duration_minutes = int(duration_hours * 60)

        with db.cursor(buffered=True) as cursor:
            # בניית שאילתה דינאמית
            query = "SELECT classroom_id FROM classrooms WHERE capacity >= %s"
            params = [students_num]

            if is_remote is not None:
                query += " AND is_remote_learning = %s"
                params.append(is_remote)

            if is_sheltered is not None:
                query += " AND is_sheltered = %s"
                params.append(is_sheltered)

            query += " ORDER BY capacity ASC"
            cursor.execute(query, tuple(params))
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

            # הכנסת קורס למסד הנתונים
            cursor.execute("""
                INSERT INTO courses (course_id, course_name, students_num, lecturer_name)
                VALUES (%s, %s, %s, %s)
            """, (course_id, course_name, students_num, lecturer_name))

            # הכנסת שיבוץ למסד הנתונים
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

    # נקה את הקונפליקטים המזוהים (אם קיימים)
    session.pop('pending_conflicts', None)

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

@app.route('/api/classroom/<int:classroom_id>')
def get_classroom_info(classroom_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM classrooms WHERE classroom_id = %s", (classroom_id,))
    classroom = cursor.fetchone()
    cursor.close()
    conn.close()
    if classroom:
        return jsonify(classroom)
    else:
        return jsonify({"error": "Classroom not found"}), 404

@app.route('/api/save_schedule_update', methods=['POST'])
def save_schedule_update():
    data = request.get_json()
    if 'schedule_id' not in data:
        return jsonify(success=False, message="Missing schedule_id in request"), 400

    schedule_id = data['schedule_id']
    weekday = data['weekday']
    time_start = data['time_start']
    time_end = data['time_end']
    capacity = int(data['capacity'])

    def convert_to_bool(value):
        value = value.strip().lower() if value else ""
        if value == 'yes':
            return 1
        if value == 'no':
            return 0
        return None

    is_remote = convert_to_bool(data.get('is_remote_learning'))
    is_sheltered = convert_to_bool(data.get('is_sheltered'))

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

        exclude_current_classroom = not time_changed

        query = """
            SELECT * FROM classrooms c
            WHERE capacity >= %s
        """
        params = [capacity]

        if is_remote is not None:
            query += " AND is_remote_learning = %s"
            params.append(is_remote)

        if is_sheltered is not None:
            query += " AND is_sheltered = %s"
            params.append(is_sheltered)

        query += """
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
    

@app.route('/api/search_alternative_slots', methods=['POST'])
def search_alternative_slots():
    data = request.get_json()
    hebrew_weekday = data['weekday']
    time_start = data['time_start']
    time_end = data['time_end']
    capacity = data['capacity']
    boards = int(data.get('board_count') or 0)
    allow_flexible_time = data.get('allow_flexible_time', False)

    weekday_map = {
        'א': 'Sunday',
        'ב': 'Monday',
        'ג': 'Tuesday',
        'ד': 'Wednesday',
        'ה': 'Thursday',
        'ו': 'Friday'
    }

    hebrew_weekday_clean = hebrew_weekday.replace("'", "").strip()
    weekday = weekday_map.get(hebrew_weekday_clean)

    if weekday is None:
        return jsonify(success=False, message="Invalid Hebrew weekday provided"), 400

    start_hour = int(time_start.split(":")[0])
    end_hour = int(time_end.split(":")[0])
    duration = end_hour - start_hour

    # רשימת ימים באנגלית (כוללת גם Friday)
    weekdays = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    weekday_index = weekdays.index(weekday)
    search_days = weekdays[:weekday_index] + weekdays[weekday_index+1:]

    with db.cursor(dictionary=True) as cursor:

        def find_available(weekday_val, start_hour_val):
            new_time_start = f"{start_hour_val:02}:00"
            new_time_end = f"{start_hour_val + duration:02}:00"

            # שלב 1 – קונפליקטים
            cursor.execute("""
                SELECT classroom_id FROM schedules
                WHERE weekday = %s
                AND (
                    (time_start <= %s AND time_end > %s) OR
                    (time_start < %s AND time_end >= %s) OR
                    (time_start >= %s AND time_end <= %s)
                )
            """, (weekday_val, new_time_start, new_time_start, new_time_end, new_time_end, new_time_start, new_time_end))
            conflicts = set(row['classroom_id'] for row in cursor.fetchall())

            # שלב 2 – כיתות מתאימות
            cursor.execute("""
                SELECT c.classroom_id, c.classroom_num,
                       bld.building_name,
                       c.capacity, c.is_remote_learning, c.is_sheltered,
                       COUNT(br.board_id) AS board_count
                FROM classrooms c
                LEFT JOIN buildings bld ON c.building_id = bld.building_id
                LEFT JOIN boards br ON c.classroom_id = br.classroom_id
                GROUP BY c.classroom_id
                HAVING c.capacity >= %s AND board_count >= %s
            """, (capacity, boards))

            candidates = cursor.fetchall()
            available = [c for c in candidates if c['classroom_id'] not in conflicts]

            return available, new_time_start, new_time_end, weekday_val

        if allow_flexible_time:
            # נסרוק שעות שונות באותו יום
            for hour in range(8, 18 - duration + 1):
                available, t_start, t_end, wd = find_available(weekday, hour)
                if available:
                    return jsonify(success=True, available_classrooms=available,
                                   time_start=t_start, time_end=t_end, weekday=wd)

            # נסרוק ימים אחרים
            for day in search_days:
                for hour in range(8, 18 - duration + 1):
                    available, t_start, t_end, wd = find_available(day, hour)
                    if available:
                        return jsonify(success=True, available_classrooms=available,
                                       time_start=t_start, time_end=t_end, weekday=wd)

        return jsonify(success=False, message="No available classrooms found on different days or hours.")


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
    capacity = int(data.get('capacity'))
    is_remote_learning = data.get('is_remote_learning')
    is_sheltered = data.get('is_sheltered')
    board_count = int(data.get('board_count', 0))

    try:
        cursor = db.cursor(dictionary=True)

        # עדכון פרטי הכיתה
        cursor.execute("""
            UPDATE classrooms
            SET floor_num = %s,
                capacity = %s,
                is_remote_learning = %s,
                is_sheltered = %s
            WHERE classroom_id = %s
        """, (floor_num, capacity, is_remote_learning, is_sheltered, classroom_id))

        # מחיקת הלוחות הקיימים
        cursor.execute("DELETE FROM boards WHERE classroom_id = %s", (classroom_id,))

        # הוספת לוחות חדשים
        for _ in range(board_count):
            cursor.execute("INSERT INTO boards (board_size, classroom_id) VALUES (%s, %s)", (1, classroom_id))

        # חיפוש שיבוצים שהקיבולת שלהם חורגת מהחדשה
        cursor.execute("""
            SELECT s.schedule_id, s.course_id, s.classroom_id, c.classroom_num, co.course_name, co.students_num
            FROM schedules s
            JOIN courses co ON s.course_id = co.course_id
            JOIN classrooms c ON s.classroom_id = c.classroom_id
            WHERE s.classroom_id = %s AND co.students_num > %s
        """, (classroom_id, capacity))

        problematic_schedules = cursor.fetchall()

        db.commit()
        cursor.close()

        return jsonify(success=True, problematic_schedules=problematic_schedules)

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


@app.route('/api/schedule_history')
def get_schedule_history():
    try:
        with db.cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT sh.*, 
                       c.course_name,
                       u.first_name AS username,
                       cr_old.classroom_num AS old_classroom_num,
                       b_old.building_name AS old_building,
                       cr_new.classroom_num AS new_classroom_num,
                       b_new.building_name AS new_building
                FROM schedule_history sh
                JOIN courses c ON sh.course_id = c.course_id
                JOIN users u ON sh.updated_by_user_id = u.user_id
                JOIN classrooms cr_old ON sh.old_classroom_id = cr_old.classroom_id
                JOIN buildings b_old ON cr_old.building_id = b_old.building_id
                JOIN classrooms cr_new ON sh.new_classroom_id = cr_new.classroom_id
                JOIN buildings b_new ON cr_new.building_id = b_new.building_id
                ORDER BY sh.update_timestamp DESC
            """)
            history = cursor.fetchall()

            for row in history:
                if isinstance(row.get("update_timestamp"), (datetime, timedelta)):
                    row["update_timestamp"] = str(row["update_timestamp"])
                if isinstance(row.get("old_time_start"), (datetime, timedelta)):
                    row["old_time_start"] = str(row["old_time_start"])
                if isinstance(row.get("old_time_end"), (datetime, timedelta)):
                    row["old_time_end"] = str(row["old_time_end"])
                if isinstance(row.get("new_time_start"), (datetime, timedelta)):
                    row["new_time_start"] = str(row["new_time_start"])
                if isinstance(row.get("new_time_end"), (datetime, timedelta)):
                    row["new_time_end"] = str(row["new_time_end"])

        return jsonify(history=history)

    except Exception as e:
        print("Error fetching schedule history:", e)
        return jsonify(error="Internal server error"), 500
    
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
                  c.is_sheltered,
                  c.capacity AS classroom_capacity
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

            # חישוב אם מספר הסטודנטים חורג מהקיבולת
            try:
                students = int(row.get("students_num") or 0)
                capacity = int(row.get("classroom_capacity") or 0)
                row["exceeds_capacity"] = students > capacity
            except:
                row["exceeds_capacity"] = False

        db.close()  
        return jsonify(schedules=rows)

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

