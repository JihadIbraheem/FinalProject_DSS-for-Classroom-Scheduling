#!/bin/bash

echo "Starting Flask server..."
python3 backend/server.py &

echo "Starting React app..."
cd frontend
npm start
