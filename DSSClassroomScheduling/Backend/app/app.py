from flask import Flask, jsonify

# Create the Flask app instance
app = Flask(__name__)

# Define a basic route
@app.route('/')
def home():
    """
    A simple route that returns a JSON response.
    Used to confirm the server is running.
    """
    return jsonify({'message': 'The server is running successfully!'})

# Run the app
if __name__ == '__main__':
    # Enable debug mode for easier development
    app.run(debug=True)
