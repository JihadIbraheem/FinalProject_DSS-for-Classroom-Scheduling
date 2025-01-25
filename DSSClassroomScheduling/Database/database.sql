CREATE DATABASE classroom_scheduling;
USE classroom_scheduling;

-- טבלת בניינים
CREATE TABLE Buildings (
    building_id INT AUTO_INCREMENT PRIMARY KEY,
    building_name VARCHAR(50) NOT NULL,
    rooms_num INT NOT NULL,
    capacity INT NOT NULL,
    remote_learning BOOLEAN DEFAULT FALSE
);

-- טבלת כיתות
CREATE TABLE Classrooms (
    classroom_id INT AUTO_INCREMENT PRIMARY KEY,
    classroom_num INT NOT NULL,
    floor_num INT NOT NULL,
    capacity INT NOT NULL,
    is_remote_learning BOOLEAN DEFAULT FALSE,
    is_sheltered BOOLEAN DEFAULT FALSE,
    building_id INT,
    FOREIGN KEY (building_id) REFERENCES Buildings(building_id)
);

-- טבלת לוחות
CREATE TABLE Boards (
    board_id INT AUTO_INCREMENT PRIMARY KEY,
    board_size VARCHAR(20) NOT NULL,
    classroom_id INT,
    FOREIGN KEY (classroom_id) REFERENCES Classrooms(classroom_id)
);

-- טבלת קורסים
CREATE TABLE Courses (
    course_id INT AUTO_INCREMENT PRIMARY KEY,
    course_name VARCHAR(100) NOT NULL,
    students_num INT NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    course_type VARCHAR(50)
);

-- טבלת מרצים
CREATE TABLE Lecturers (
    lecturer_id INT AUTO_INCREMENT PRIMARY KEY,
    lecturer_name VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL
);

-- טבלת שיבוצים
CREATE TABLE Schedules (
    schedule_id INT AUTO_INCREMENT PRIMARY KEY,
    classroom_id INT NOT NULL,
    course_id INT NOT NULL,
    schedule_datetime DATETIME NOT NULL,
    status ENUM('Pending', 'Confirmed', 'Conflict') NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    time_start TIME NOT NULL,
    time_end TIME NOT NULL,
    FOREIGN KEY (classroom_id) REFERENCES Classrooms(classroom_id),
    FOREIGN KEY (course_id) REFERENCES Courses(course_id)
);

-- טבלת משתמשים
CREATE TABLE Users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(100) NOT NULL,
    role ENUM('Admin', 'Manager') NOT NULL,
    permissions TEXT
);

-- טבלת אילוצים
CREATE TABLE Constraints (
    constraint_id INT AUTO_INCREMENT PRIMARY KEY,
    course_id INT,
    classroom_id INT,
    constraint_type VARCHAR(50) NOT NULL,
    constraint_detail TEXT,
    FOREIGN KEY (course_id) REFERENCES Courses(course_id),
    FOREIGN KEY (classroom_id) REFERENCES Classrooms(classroom_id)
);
