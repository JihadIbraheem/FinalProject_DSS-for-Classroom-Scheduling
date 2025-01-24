from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy

# Import the database URI from config
from config.config import DATABASE_URI

# Create the Flask app instance
app = Flask(__name__)

# Configure the database URI
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Define a simple database model
class Classroom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_number = db.Column(db.String(10), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)

# Create the database tables (if not already created)
with app.app_context():
    db.create_all()

# Define a route to add a classroom
@app.route('/api/add_classroom', methods=['POST'])
def add_classroom():
    data = request.get_json()
    room_number = data.get('room_number')
    capacity = data.get('capacity')

    # Create a new classroom record
    new_classroom = Classroom(room_number=room_number, capacity=capacity)
    db.session.add(new_classroom)
    db.session.commit()

    return jsonify({'message': 'Classroom added successfully!'})

# Define a route to fetch all classrooms
@app.route('/api/get_classrooms', methods=['GET'])
def get_classrooms():
    classrooms = Classroom.query.all()
    results = [
        {'id': classroom.id, 'room_number': classroom.room_number, 'capacity': classroom.capacity}
        for classroom in classrooms
    ]
    return jsonify(results)

# Run the app
if __name__ == '__main__':
    app.run(debug=True)
