==============================================================================
PROJECT: PRISM (Patient Rapid Information System for Medicine)
==============================================================================

DESCRIPTION:
PRISM is a rapid-response medical information system designed to provide 
emergency responders with instant access to critical patient data 
(Blood Type, Allergies, Implants) using biometric fingerprint authentication.
It bridges the "Information Gap" in critical care, saving valuable time 
during the "Golden Hour" of trauma response.

------------------------------------------------------------------------------
THE PROBLEM:
In emergencies (accidents, strokes, shock), patients are often unconscious 
or uncommunicative. Doctors lose time waiting for diagnostics or risk 
adverse drug reactions due to a lack of medical history.

THE SOLUTION:
PRISM links a physical biometric ID (Fingerprint) to a digital medical record.
1. Scan Finger: Responder places patient's finger on the sensor.
2. Instant Match: System identifies the patient in < 2 seconds.
3. Critical Data: Dashboard displays Blood Group, Allergies, and Contacts.

------------------------------------------------------------------------------
TECHNICAL STACK:
- Frontend: HTML5, CSS (Glassmorphism), JavaScript (Fetch API, Streaming)
- Backend: Python (Flask Framework)
- Database: MySQL
- Hardware: Arduino Uno + R307 Optical Fingerprint Sensor
- Communication: Serial (USB) between Python & Arduino

------------------------------------------------------------------------------
FOLDER STRUCTURE:
/prism_project
  |-- app.py                # Python Flask Server (Backend Logic)
  |-- /uploads              # Stores patient profile photos
  |-- /templates            # Frontend HTML files
       |-- index.html       # Landing Page (Emergency Access)
       |-- prism-form.html  # Registration Page (Biometric Enrollment)
       |-- prism-dashboard.html # Critical Data View
  |-- /arduino_code
       |-- FINGER.ino       # C++ Code for Arduino + R307 Sensor

------------------------------------------------------------------------------
SETUP INSTRUCTIONS:

1. HARDWARE SETUP
   - Connect R307 Fingerprint Sensor to Arduino Uno.
   - Upload 'FINGER.ino' to the Arduino using Arduino IDE.
   - Note the COM Port (e.g., COM22).

2. DATABASE SETUP (MySQL)
   - Open MySQL Workbench/Command Line.
   - Run the following SQL commands:
     CREATE DATABASE prism;
     USE prism;
     CREATE TABLE patients (
         id INT AUTO_INCREMENT PRIMARY KEY,
         fingerprint_id INT UNIQUE,
         passkey VARCHAR(255),
         full_name VARCHAR(255),
         blood_group VARCHAR(10),
         allergies TEXT,
         medications TEXT,
         photo_path VARCHAR(255),
         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
     );

3. SOFTWARE SETUP
   - Install Python dependencies:
     pip install flask mysql-connector-python pyserial flask-cors

   - Configure 'app.py':
     Update 'ARDUINO_PORT' to your specific COM port.
     Update 'password' in the 'get_db_connection' function.

4. RUNNING THE PROJECT
   - Open terminal in project folder.
   - Run: python app.py
   - Open browser: http://localhost:3000

------------------------------------------------------------------------------
DISCLAIMER:
This is a prototype designed for educational and demonstration purposes.
In a real-world scenario, this system would require HIPAA/GDPR compliance 
and secure cloud infrastructure.
==============================================================================
