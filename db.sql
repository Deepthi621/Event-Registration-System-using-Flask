-- 1. Create the database
CREATE DATABASE IF NOT EXISTS EventRegistrationDB;
USE EventRegistrationDB;

-- 2. Create Users table (with ProfilePhotoFilename)
CREATE TABLE IF NOT EXISTS Users (
    UserID INT PRIMARY KEY AUTO_INCREMENT,
    Name VARCHAR(100) NOT NULL,
    Email VARCHAR(100) UNIQUE NOT NULL,
    Password VARCHAR(255) NOT NULL,
    Role ENUM('Organizer', 'Attendee') NOT NULL,
    ProfilePhotoFilename VARCHAR(255) DEFAULT NULL  -- Added this column
);

-- 3. Insert sample users
INSERT INTO Users (Name, Email, Password, Role)
VALUES 
('Ravi Kumar', 'ravi@events.com', 'ravi123', 'Organizer'),
('Anjali Rao', 'anjali@domain.com', 'anjali123', 'Attendee'),
('Meena Shah', 'meena@domain.com', 'meena123', 'Attendee');

-- 4. Create Events table (with StartTime and EndTime)
CREATE TABLE IF NOT EXISTS Events (
    EventID INT PRIMARY KEY AUTO_INCREMENT,
    EventName VARCHAR(100) NOT NULL,
    Venue VARCHAR(150),
    Date DATE NOT NULL,
    StartTime TIME,
    EndTime TIME,
    Capacity INT,
    Fee DECIMAL(10, 2),
    OrganizerID INT,
    FOREIGN KEY (OrganizerID) REFERENCES Users(UserID)
);

-- 5. Insert sample events
INSERT INTO Events (EventName, Venue, Date, StartTime, EndTime, Capacity, Fee, OrganizerID)
VALUES 
('Tech Talk 2025', 'Auditorium A', '2025-05-01', '09:00:00', '17:00:00', 100, 150.00, 1),
('Startup Meetup', 'Hall B', '2025-06-10', '13:30:00', '16:00:00', 80, 200.00, 1),
('AI Workshop', 'Lab 3', '2025-05-20', '10:00:00', '12:30:00', 50, 300.00, 1);

-- 6. Create Registrations table (with Status)
CREATE TABLE IF NOT EXISTS Registrations (
    RegistrationID INT PRIMARY KEY AUTO_INCREMENT,
    UserID INT,
    EventID INT,
    Status ENUM('Active', 'Cancelled') DEFAULT 'Active',
    CancellationReason TEXT,
    RegistrationDate TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (UserID) REFERENCES Users(UserID),
    FOREIGN KEY (EventID) REFERENCES Events(EventID),
    UNIQUE(UserID, EventID)  -- Prevent duplicate registrations
);

-- 7. Insert sample registrations
INSERT INTO Registrations (UserID, EventID)
VALUES 
(2, 1),
(3, 2);

-- 8. Create Payments table
CREATE TABLE IF NOT EXISTS Payments (
    PaymentID INT PRIMARY KEY AUTO_INCREMENT,
    RegistrationID INT,
    Amount DECIMAL(10, 2),
    Status ENUM('Pending', 'Completed', 'Failed', 'Cancelled') DEFAULT 'Pending',
    FOREIGN KEY (RegistrationID) REFERENCES Registrations(RegistrationID)
);

-- 9. Insert sample payments
INSERT INTO Payments (RegistrationID, Amount, Status)
VALUES
(1, 150.00, 'Completed'),
(2, 200.00, 'Failed');

-- 10. Create Feedback table
CREATE TABLE IF NOT EXISTS Feedback (
    FeedbackID INT PRIMARY KEY AUTO_INCREMENT,
    UserID INT NOT NULL,
    EventID INT NOT NULL,
    Rating INT NOT NULL CHECK (Rating BETWEEN 1 AND 5),
    Comment TEXT,
    FeedbackDate TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (UserID) REFERENCES Users(UserID),
    FOREIGN KEY (EventID) REFERENCES Events(EventID),
    UNIQUE(UserID, EventID)  -- Prevent multiple feedbacks per user-event
);

-- 11. Create Reports and ReportPhotos tables
CREATE TABLE IF NOT EXISTS Reports (
    ReportID INT AUTO_INCREMENT PRIMARY KEY,
    EventID INT NOT NULL,
    Content TEXT NOT NULL,
    CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (EventID) REFERENCES Events(EventID)
);

CREATE TABLE IF NOT EXISTS ReportPhotos (
    PhotoID INT AUTO_INCREMENT PRIMARY KEY,
    ReportID INT NOT NULL,
    filename VARCHAR(255) NOT NULL,
    FOREIGN KEY (ReportID) REFERENCES Reports(ReportID) ON DELETE CASCADE
);
