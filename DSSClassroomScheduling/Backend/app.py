from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
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
            print("המשתמש נמצא במסד הנתונים:", user)
            return redirect(url_for('home'))
        else:
            print("לא נמצא משתמש בשם:", username)
            flash('Invalid username or password!')
            return redirect(url_for('login'))

    return render_template('login.html')

# מסלול לדף הבית
@app.route('/home')
def home():
    return render_template('home.html')

# מסלול לקבצים סטטיים
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# הפעלת האפליקציה
if __name__ == '__main__':
    try:
        db.ping(reconnect=True)
        print("החיבור למסד הנתונים פעיל!")
    except mysql.connector.Error as err:
        print("שגיאה בחיבור למסד הנתונים:", err)
    app.run(debug=True)
