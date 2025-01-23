CREATE TABLE Users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(100) NOT NULL,
    password VARCHAR(100) NOT NULL,
    role ENUM('Admin', 'Manager') NOT NULL
);

CREATE TABLE Schedules (
    schedule_id INT AUTO_INCREMENT PRIMARY KEY,
    classroom_id INT NOT NULL,
    course_id INT NOT NULL,
    schedule_datetime DATETIME NOT NULL,
    status ENUM('Pending', 'Confirmed', 'Conflict') NOT NULL
);
