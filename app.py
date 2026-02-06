import os
import time
import json
import serial
import mysql.connector
from flask import Flask, request, jsonify, render_template, send_from_directory, Response, stream_with_context
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- Configuration ---
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ARDUINO CONFIG
ARDUINO_PORT = 'COM22'  # <--- MAKE SURE THIS MATCHES YOUR PC
BAUD_RATE = 9600

# --- Database Connection ---
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='praveen@sql', # <--- UPDATED PASSWORD
            database='prism'
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to DB: {err}")
        return None

# --- Arduino Helper Function ---
# (Used by scan_search. scan_enroll has its own streaming logic)
def send_arduino_command(command, operation_type):
    """
    Opens connection, sends command ('1' or '2'), 
    waits for specific success/fail response.
    """
    ser = None
    try:
        ser = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=1)
        time.sleep(2) # Wait for Arduino reset
        
        # Clear any old data
        ser.reset_input_buffer()
        
        # Send Command
        ser.write(command.encode())
        print(f"Sent command '{command}' to Arduino...")

        start_time = time.time()
        timeout = 60 # 60 seconds timeout for scanning

        while (time.time() - start_time) < timeout:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                print(f"[Arduino]: {line}") # Debug print
                
                # --- LOGIC FOR ENROLLMENT (Cmd '1') ---
                if operation_type == 'enroll':
                    if "SUCCESS_ENROLL" in line:
                        finger_id = int(line.split(":")[1])
                        return {'success': True, 'id': finger_id}
                    elif "FAIL" in line:
                        return {'success': False, 'message': f"Sensor Error: {line}"}
                
                # --- LOGIC FOR SEARCH (Cmd '2') ---
                elif operation_type == 'search':
                    if "FOUND_ID" in line:
                        finger_id = int(line.split(":")[1])
                        return {'success': True, 'id': finger_id}
                    elif "NOT_FOUND" in line:
                        return {'success': False, 'message': "Fingerprint not matched."}
                    elif "FAIL" in line:
                        return {'success': False, 'message': "Sensor Error."}

        return {'success': False, 'message': "Timeout: No finger detected."}

    except serial.SerialException as e:
        print(f"Serial Error: {e}")
        return {'success': False, 'message': "Could not connect to Fingerprint Sensor."}
    finally:
        if ser and ser.is_open:
            ser.close()

# --- Helper ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def to_int_or_none(value):
    if not value or value == "undefined" or value == "null": return None
    try: return int(value)
    except ValueError: return None


# ====== PAGE ROUTES ======
@app.route('/')
def index(): return render_template('index.html')

@app.route('/prism-form.html')
def form_page(): return render_template('prism-form.html')

@app.route('/prism-dashboard.html')
def dashboard_page(): return render_template('prism-dashboard.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ====== FINGERPRINT API ROUTES ======

@app.route('/api/scan-enroll', methods=['GET', 'POST'])
def scan_enroll():
    def generate():
        ser = None
        try:
            # 1. Connect to Arduino
            ser = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=1)
            time.sleep(2) # Wait for reset
            ser.reset_input_buffer()
            
            # 2. Send Enroll Command
            ser.write(b'1')
            yield json.dumps({"status": "starting", "message": "Sensor Initializing..."}) + "\n"

            start_time = time.time()
            
            # 3. Listen Loop
            while (time.time() - start_time) < 60: # 60s timeout
                if ser.in_waiting > 0:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    
                    # --- Map Arduino Messages to User Friendly Text ---
                    if "READY_TO_ENROLL" in line:
                        yield json.dumps({"status": "step", "message": "Place your finger on the sensor..."}) + "\n"
                    
                    elif "REMOVE_FINGER" in line:
                        yield json.dumps({"status": "step", "message": "Great! Now remove your finger."}) + "\n"
                    
                    elif "PLACE_SAME_FINGER" in line:
                        yield json.dumps({"status": "step", "message": "Place the SAME finger again..."}) + "\n"
                    
                    elif "SUCCESS_ENROLL" in line:
                        finger_id = int(line.split(":")[1])
                        # Final Success Message
                        yield json.dumps({"status": "done", "success": True, "id": finger_id, "message": "Success!"}) + "\n"
                        return # End the stream
                    
                    elif "FAIL" in line:
                        yield json.dumps({"status": "done", "success": False, "message": "Scan Failed. Try again."}) + "\n"
                        return
                    
            yield json.dumps({"status": "done", "success": False, "message": "Timeout: No finger detected."}) + "\n"

        except Exception as e:
            yield json.dumps({"status": "done", "success": False, "message": f"Server Error: {str(e)}"}) + "\n"
        finally:
            if ser and ser.is_open:
                ser.close()

    # Return a Stream Response
    return Response(stream_with_context(generate()), mimetype='application/json')


@app.route('/api/scan-search', methods=['POST'])
def scan_search():
    """Trigger Arduino to Search for finger"""
    result = send_arduino_command('2', 'search')
    
    if result['success']:
        # If fingerprint found, immediately fetch patient data
        finger_id = result['id']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM patients WHERE fingerprint_id = %s", (finger_id,))
        patient = cursor.fetchone()
        cursor.close()
        conn.close()

        if patient:
            # Fix Date serialization
            if patient.get('dob'): patient['dob'] = str(patient['dob'])
            return jsonify({'success': True, 'patientData': patient})
        else:
            return jsonify({'success': False, 'message': f"Fingerprint ID {finger_id} found on device, but not in Database!"})
    
    return jsonify(result)


# ====== REGISTRATION & FETCH ROUTES ======

@app.route('/api/register', methods=['POST'])
def register_patient():
    conn = get_db_connection()
    if not conn: return jsonify({'success': False, 'message': 'Database connection failed'})
    
    cursor = conn.cursor()
    try:
        # 1. File Upload
        photo_filename = None
        if 'photoUpload' in request.files:
            file = request.files['photoUpload']
            if file and file.filename != '':
                ext = file.filename.rsplit('.', 1)[1].lower()
                photo_filename = f"{int(time.time()*1000)}.{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))

        # 2. Medications
        med_names = request.form.getlist('med_name[]')
        med_doses = request.form.getlist('med_dose[]')
        valid_meds = [f"{n} ({d or 'N/A'})" for n, d in zip(med_names, med_doses) if n.strip()]
        med_string = "; ".join(valid_meds) if valid_meds else "None reported"

        # 3. Insert Data
        sql = """
            INSERT INTO patients (
                passkey, fingerprint_id, full_name, dob, age, blood_group, photo_path,
                emergency_contact_name, emergency_contact_phone, doctor_name, doctor_phone,
                allergies, chronic_diseases, implants, medications,
                vitals_bp, vitals_hr, vitals_sugar, vitals_cholesterol,
                smoking_status, diet_type, exercise_level,
                organ_donor, religious_restrictions, other_notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        values = (
            request.form.get('passkey'),
            to_int_or_none(request.form.get('fingerprint_id')), # New Field
            request.form.get('fullName'),
            request.form.get('dob') or None,
            to_int_or_none(request.form.get('age')),
            request.form.get('bloodGroup'),
            photo_filename,
            request.form.get('emergencyName'),
            request.form.get('emergencyPhone'),
            request.form.get('doctorName'),
            request.form.get('doctorPhone'),
            request.form.get('allergies'),
            request.form.get('chronic'),
            request.form.get('implants'),
            med_string,
            request.form.get('bp'),
            to_int_or_none(request.form.get('heartrate')),
            to_int_or_none(request.form.get('bloodsugar')),
            to_int_or_none(request.form.get('cholesterol')),
            request.form.get('smokingStatus'),
            request.form.get('dietType'),
            request.form.get('exerciseLevel'),
            request.form.get('organDonor', 'no'),
            request.form.get('religiousRestrictions', 'no'),
            request.form.get('otherNotes')
        )

        cursor.execute(sql, values)
        conn.commit()
        return jsonify({'success': True, 'message': 'Registration successful!'})

    except mysql.connector.Error as err:
        print(f"DB Error: {err}")
        if err.errno == 1062:
            return jsonify({'success': False, 'message': 'Passkey or Fingerprint ID already exists.'})
        return jsonify({'success': False, 'message': str(err)})
    finally:
        cursor.close()
        conn.close()

# --- Manual Passkey Fetch ---
@app.route('/api/emergency-fetch', methods=['POST'])
def emergency_fetch():
    data = request.get_json()
    passkey = data.get('passkey')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM patients WHERE passkey = %s", (passkey,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if result:
        if result.get('dob'): result['dob'] = str(result['dob'])
        return jsonify({'success': True, 'patientData': result})
    else:
        return jsonify({'success': False, 'message': 'Invalid Passkey.'})

if __name__ == '__main__':
    app.run(port=3000, debug=True)