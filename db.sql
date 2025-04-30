CREATE DATABASE EventRegistrationDB;
USE EventRegistrationDB;
CREATE TABLE Users (
    UserID INT PRIMARY KEY AUTO_INCREMENT,
    Name VARCHAR(100) NOT NULL,
    Email VARCHAR(100) UNIQUE NOT NULL,
    Password VARCHAR(255) NOT NULL,
    Role ENUM('Organizer', 'Attendee') NOT NULL
);
INSERT INTO Users (Name, Email, Password, Role)
VALUES 
('Ravi Kumar', 'ravi@events.com', 'ravi123', 'Organizer'),
('Anjali Rao', 'anjali@domain.com', 'anjali123', 'Attendee'),
('Meena Shah', 'meena@domain.com', 'meena123', 'Attendee');

CREATE TABLE Events (
    EventID INT PRIMARY KEY AUTO_INCREMENT,
    EventName VARCHAR(100) NOT NULL,
    Venue VARCHAR(150),
    Date DATE NOT NULL,
    Capacity INT,
    Fee DECIMAL(10, 2),
    OrganizerID INT,
    FOREIGN KEY (OrganizerID) REFERENCES Users(UserID)
);

INSERT INTO Events (EventName, Venue, Date, Capacity, Fee, OrganizerID)
VALUES 
('Tech Talk 2025', 'Auditorium A', '2025-05-01', 100, 150.00, 1),
('Startup Meetup', 'Hall B', '2025-06-10', 80, 200.00, 1),
('AI Workshop', 'Lab 3', '2025-05-20', 50, 300.00, 1);

CREATE TABLE Registrations (
    RegistrationID INT PRIMARY KEY AUTO_INCREMENT,
    UserID INT,
    EventID INT,
    RegistrationDate TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (UserID) REFERENCES Users(UserID),
    FOREIGN KEY (EventID) REFERENCES Events(EventID)
);

INSERT INTO Registrations (UserID, EventID)
VALUES 
(2, 1),
(3, 2);

CREATE TABLE Payments (
    PaymentID INT PRIMARY KEY AUTO_INCREMENT,
    RegistrationID INT,
    Amount DECIMAL(10, 2),
    Status ENUM('Pending', 'Completed', 'Failed') DEFAULT 'Pending',
    FOREIGN KEY (RegistrationID) REFERENCES Registrations(RegistrationID)
);

INSERT INTO Payments (RegistrationID, Amount, Status)
VALUES
(1, 150.00, 'Completed'),
(2, 200.00, 'Failed');

Select * from Users where Role = 'Attendee';
SELECT Events.EventName, Events.Venue, Events.Date
FROM Events
JOIN Users ON Events.OrganizerID = Users.UserID
WHERE Users.Name = 'Ravi Kumar';

SELECT U.Name AS OrganizerName, COUNT(E.EventID) AS EventCount
FROM Users U
JOIN Events E ON U.UserID = E.OrganizerID
WHERE U.Role = 'Organizer'
GROUP BY U.UserID;

SELECT E.EventName, COUNT(R.RegistrationID) AS TotalRegistrations
FROM Events E
LEFT JOIN Registrations R ON E.EventID = R.EventID
GROUP BY E.EventID;

SELECT U.Name AS AttendeeName, E.EventName
FROM Registrations R
JOIN Users U ON R.UserID = U.UserID
JOIN Events E ON R.EventID = E.EventID
WHERE U.Role = 'Attendee';

SELECT AVG(P.Amount) AS AvgFee
FROM Payments P
WHERE P.Status = 'Completed';

SELECT EventName, Fee
FROM Events
ORDER BY Fee ASC;

SELECT EventName, Fee
FROM Events
WHERE Fee = (SELECT MAX(Fee) FROM Events);

SELECT E.EventName, COUNT(R.RegistrationID) AS AttendeeCount
FROM Events E
JOIN Registrations R ON E.EventID = R.EventID
GROUP BY E.EventID
HAVING COUNT(R.RegistrationID) > 1;

SELECT E.EventName, SUM(P.Amount) AS TotalIncome
FROM Payments P
JOIN Registrations R ON P.RegistrationID = R.RegistrationID
JOIN Events E ON R.EventID = E.EventID
WHERE P.Status = 'Completed'
GROUP BY E.EventID;

ALTER TABLE Users ADD Salary DECIMAL(10, 2);

UPDATE Users
SET Salary = 70000
WHERE UserID = 1;  -- or whatever UserID Ravi Kumar has

SET SQL_SAFE_UPDATES = 0;
UPDATE Users SET Salary = 70000 WHERE Name = 'Ravi Kumar';
SET SQL_SAFE_UPDATES = 1;

-- Cusror Starts

DELIMITER $$

CREATE PROCEDURE ShowEventAttendees(IN givenEventID INT)
BEGIN
  DECLARE done INT DEFAULT 0;
  DECLARE attendeeName VARCHAR(100);
  DECLARE attendeeEmail VARCHAR(100);

DROP PROCEDURE IF EXISTS ShowEventAttendees;
DELIMITER $$

CREATE PROCEDURE ShowEventAttendees(IN givenEventID INT)
BEGIN
  DECLARE done INT DEFAULT 0;
  DECLARE attendeeName VARCHAR(100);
  DECLARE attendeeEmail VARCHAR(100);

  -- Cursor to get attendees for the given EventID
  DECLARE attendee_cursor CURSOR FOR
    SELECT U.Name, U.Email
    FROM Users U
    JOIN Registrations R ON U.UserID = R.UserID
    WHERE R.EventID = givenEventID AND U.Role = 'Attendee';

  -- Exit when no more rows
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;

  -- Open the cursor
  OPEN attendee_cursor;

  read_loop: LOOP
    FETCH attendee_cursor INTO attendeeName, attendeeEmail;
    IF done THEN
      LEAVE read_loop;
    END IF;

    -- Display result
    SELECT CONCAT('Attendee: ', attendeeName, ', Email: ', attendeeEmail) AS RegisteredAttendee;
  END LOOP;

  CLOSE attendee_cursor;
END$$

DELIMITER ;

CALL ShowEventAttendees(1);

-- Cursor Ends

-- Views Start
CREATE OR REPLACE VIEW UpcomingEvents AS
SELECT EventID, EventName, Venue, Date, Capacity, Fee
FROM Events
WHERE Date >= CURDATE();

SELECT * FROM UpcomingEvents;

CREATE OR REPLACE VIEW EventRegistrationCount AS
SELECT 
    E.EventID,
    E.EventName,
    COUNT(R.RegistrationID) AS TotalRegistrations
FROM Events E
LEFT JOIN Registrations R ON E.EventID = R.EventID
GROUP BY E.EventID, E.EventName;

SELECT * FROM EventRegistrationCount;

CREATE OR REPLACE VIEW OrganizerEvents AS
SELECT 
    U.UserID AS OrganizerID,
    U.Name AS OrganizerName,
    E.EventID,
    E.EventName,
    E.Date
FROM Users U
JOIN Events E ON U.UserID = E.OrganizerID
WHERE U.Role = 'Organizer';

SELECT * FROM OrganizerEvents;

CREATE OR REPLACE VIEW EventAttendees AS
SELECT 
    R.EventID,
    E.EventName,
    U.UserID AS AttendeeID,
    U.Name AS AttendeeName,
    U.Email
FROM Registrations R
JOIN Users U ON R.UserID = U.UserID
JOIN Events E ON R.EventID = E.EventID
WHERE U.Role = 'Attendee';

SELECT * FROM EventAttendees WHERE EventID = 1;

-- Views End

-- Transaction starts

START TRANSACTION;

-- Step 1: Insert registration
INSERT INTO Registrations (UserID, EventID)
VALUES (3, 1);  -- Change to actual UserID and EventID

-- Step 2: Decrease capacity
UPDATE Events
SET Capacity = Capacity - 1
WHERE EventID = 1 AND Capacity > 0;

-- Check that both worked (optional)
SELECT * FROM Events WHERE EventID = 1;

-- Commit if everything's fine
COMMIT;

ROLLBACK;

ALTER TABLE Users
MODIFY Email VARCHAR(100) NOT NULL UNIQUE;

ALTER TABLE Users
ADD CONSTRAINT chk_role CHECK (Role IN ('Organizer', 'Attendee'));

ALTER TABLE Events
MODIFY Fee DECIMAL(10, 2) NOT NULL DEFAULT 0.00;

ALTER TABLE Events
ADD CONSTRAINT chk_capacity CHECK (Capacity >= 0);

-- Transaction complete

SELECT * FROM eventregistrationdb.users;
use eventregistrationdb;
INSERT INTO Users (Name, Email, Password, Role)
VALUES ('Test User', 'test@example.com', 'password123', 'Attendee');


SELECT UserID, EventID, COUNT(*) 
FROM Registrations 
GROUP BY UserID, EventID 
HAVING COUNT(*) > 1;

DELETE r1 FROM Registrations r1
INNER JOIN Registrations r2 
WHERE 
    r1.RegistrationID < r2.RegistrationID AND 
    r1.UserID = r2.UserID AND 
    r1.EventID = r2.EventID;

ALTER TABLE Registrations 
ADD CONSTRAINT unique_registration 
UNIQUE (UserID, EventID);

Use EventRegistrationDB;
-- Backfill missing payment amounts
UPDATE Payments P
JOIN Registrations R ON P.RegistrationID = R.RegistrationID
JOIN Events E ON R.EventID = E.EventID
SET P.Amount = E.Fee
WHERE P.Amount IS NULL;

-- Set default values for future records
ALTER TABLE Payments 
MODIFY COLUMN Amount DECIMAL(10,2) NOT NULL DEFAULT 0;

UPDATE Payments SET Amount = 0 WHERE Amount IS NULL;
ALTER TABLE Payments MODIFY COLUMN Amount DECIMAL(10,2) NOT NULL DEFAULT 0;

-- Add status to registrations
ALTER TABLE Registrations 
ADD COLUMN Status ENUM('Active', 'Cancelled') NOT NULL DEFAULT 'Active';

-- Update existing registrations
UPDATE Registrations SET Status = 'Active';

-- Add cancellation reason (optional)
ALTER TABLE Registrations 
ADD COLUMN CancellationReason TEXT;

ALTER TABLE Payments 
MODIFY COLUMN Status ENUM('Pending', 'Completed', 'Failed', 'Cancelled') DEFAULT 'Pending';

-- Check user details to confirm identity
SELECT * FROM Users WHERE Name = 'Neha';
DELETE Payments 
FROM Payments
JOIN Registrations ON Payments.RegistrationID = Registrations.RegistrationID
JOIN Users ON Registrations.UserID = Users.UserID
WHERE Users.Name = 'Neha';

-- Step 0: Make sure you're using the correct DB
USE EventRegistrationDB;

-- Step 1: Delete Payments linked to Neha's registrations
DELETE Payments 
FROM Payments
JOIN Registrations ON Payments.RegistrationID = Registrations.RegistrationID
JOIN Users ON Registrations.UserID = Users.UserID
WHERE Users.Name = 'Neha';

-- Step 2: Delete Neha's Registrations
DELETE FROM Registrations 
WHERE UserID IN (SELECT UserID FROM Users WHERE Name = 'Neha');

-- Step 3: If Neha is an Organizer, delete her Events (and any registrations/payments related to those events must already be deleted)
DELETE FROM Events 
WHERE OrganizerID IN (SELECT UserID FROM Users WHERE Name = 'Neha');

-- Step 4: Finally, delete Neha from the Users table
DELETE FROM Users 
WHERE Name = 'Neha';

-- Add these to your database setup
ALTER TABLE Registrations 
MODIFY COLUMN Status ENUM('Active', 'Cancelled') NOT NULL DEFAULT 'Active';

ALTER TABLE Payments 
MODIFY COLUMN Status ENUM('Pending', 'Completed', 'Failed', 'Cancelled') DEFAULT 'Pending';

UPDATE Registrations SET Status = 'Active' WHERE Status IS NULL;

Use eventregistrationdb;
CREATE TABLE Feedback (
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
USE EventRegistrationDB;

-- Add StartTime and EndTime columns
ALTER TABLE Events 
ADD COLUMN StartTime TIME AFTER Date,
ADD COLUMN EndTime TIME AFTER StartTime;

-- First remove existing time columns
ALTER TABLE Events DROP COLUMN StartTime;
ALTER TABLE Events DROP COLUMN EndTime;

-- Add new columns with proper TIME type
ALTER TABLE Events 
ADD COLUMN StartTime TIME AFTER Date,
ADD COLUMN EndTime TIME AFTER StartTime;

-- Update existing events with sample times
UPDATE Events SET 
    StartTime = '09:00:00',
    EndTime = '17:00:00'
WHERE EventID = 1;

UPDATE Events SET 
    StartTime = '13:30:00',
    EndTime = '16:00:00'
WHERE EventID = 2;

UPDATE Events SET 
    StartTime = '10:00:00',
    EndTime = '12:30:00'
WHERE EventID = 3;

use eventregistrationdb;
CREATE TABLE Reports (
    ReportID INT AUTO_INCREMENT PRIMARY KEY,
    EventID INT NOT NULL,
    Content TEXT NOT NULL,
    CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (EventID) REFERENCES Events(EventID)
);

CREATE TABLE ReportPhotos (
    PhotoID INT AUTO_INCREMENT PRIMARY KEY,
    ReportID INT NOT NULL,
    filename VARCHAR(255) NOT NULL,
    FOREIGN KEY (ReportID) REFERENCES Reports(ReportID) ON DELETE CASCADE
);
DELETE FROM Reports
WHERE ReportID = 6;

Select * from Reports;
Drop table Certificates;
USE EventRegistrationDB;

DELETE Payments 
FROM Payments
JOIN Registrations ON Payments.RegistrationID = Registrations.RegistrationID
WHERE Registrations.UserID = 16;

DELETE FROM Registrations
WHERE UserID = 16;

DELETE FROM Events
WHERE OrganizerID = 16;

DELETE FROM Users
WHERE UserID = 16;
