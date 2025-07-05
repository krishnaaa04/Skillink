import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
import random
import time
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from urllib.parse import quote
import logging
import re

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)  
app.secret_key = "your_secret_key"

# Email Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')

mail = Mail(app)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Log email configuration for debugging
app.logger.debug(f"Email configuration: {app.config['MAIL_USERNAME']}")

# Database connection function
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Root@12345",
        database="skillink_db"
    )

# List of quotes
quotes = [
    "Success is not final, failure is not fatal: It is the courage to continue that counts.",
    "The only way to do great work is to love what you do.",
    "Your limitation—it's only your imagination.",
    "Do what you can, with what you have, where you are.",
    "Dream big and dare to fail.",
    "Opportunities don't happen. You create them.",
    "Believe you can, and you're halfway there. — Theodore Roosevelt"
]

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login')
def login_page():
    return render_template('login.html')


@app.route('/contact', methods=['POST'])
def contact():
    name = request.form.get('name')
    email = request.form.get('email')
    message = request.form.get('message')
    
    # Log the received data
    app.logger.debug(f"Received contact form data: Name={name}, Email={email}, Message={message}")
    
    # Basic validation
    if not all([name, email, message]):
        flash('Please fill in all fields', 'error')
        return redirect(url_for('home'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Save to database
        cursor.execute("""
            INSERT INTO contacts (name, email, message, created_at)
            VALUES (%s, %s, %s, NOW())
        """, (name, email, message))
        conn.commit()
        
        # Log before sending email
        app.logger.debug("Sending email...")
        
        # Send email to Skillink team
        msg = Message(
            subject=f"New Contact Form Submission from {name}",
            recipients=['skillink.team@gmail.com'],
            body=f"""
            Name: {name}
            Email: {email}
            Message: {message}
            """,
            html=f"""
            <h3>New Contact Form Submission</h3>
            <p><strong>Name:</strong> {name}</p>
            <p><strong>Email:</strong> {email}</p>
            <p><strong>Message:</strong> {message}</p>
            """
        )
        mail.send(msg)
        
        # Log after sending email
        app.logger.debug("Email sent successfully.")
        
        flash('Your message has been sent! We\'ll contact you soon.', 'success')
        return redirect(url_for('home'))
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        app.logger.error(f"An error occurred while sending your message: {str(e)}")
        flash('An error occurred while sending your message: ' + str(e), 'error')
        return redirect(url_for('home'))
        
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

# Signup route
@app.route('/signup', methods=['POST'])
def signup():
    full_name = request.form['full_name']
    email = request.form['email']
    user_type = request.form['user_type']
    password = request.form['password']
    experience = request.form.get('experience', "")
    skills = request.form.get('skills', "")

    # Validate skills - only letters, spaces, commas, and hyphens allowed
    if skills and not re.match(r'^[a-zA-Z\s,-]+$', skills):
        flash('Skills should only contain letters, spaces, commas, or hyphens.', 'error')
        return redirect(url_for('login_page'))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Check if email already exists
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        existing_user = cursor.fetchone()
        if existing_user:
            flash('Email already exists. Please use a different email.', 'error')
            return redirect(url_for('login_page'))

        sql = """
        INSERT INTO users (full_name, email, user_type, password_hash, experience, skills) 
        VALUES (%s, %s, %s, SHA2(%s, 256), %s, %s)
        """
        values = (full_name, email, user_type, password, experience, skills)
        cursor.execute(sql, values)
        conn.commit()
        flash('Account created successfully! Please log in.', 'success')
    except mysql.connector.Error as err:
        flash(f'Error creating account: {err}', 'error')
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('login_page'))

# Login route
@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    sql = "SELECT id, full_name, user_type, experience, skills FROM users WHERE email = %s AND password_hash = SHA2(%s, 256)"

    try:
        cursor.execute(sql, (email, password))
        user = cursor.fetchone()
        
        if user:
            session['user_id'] = user['id']
            session['full_name'] = user['full_name']
            session['user_type'] = user['user_type']

            if user['user_type'] == 'employee':
                # Check if profile exists
                cursor.execute("SELECT user_id FROM eprofile WHERE user_id = %s", (user['id'],))
                profile_exists = cursor.fetchone()

                if not profile_exists:
                    cursor.execute(""" 
                        INSERT INTO eprofile (user_id, experience, skills) 
                        VALUES (%s, %s, %s)
                    """, (user['id'], user['experience'], user['skills']))
                    conn.commit()

                return redirect(url_for('employee_dashboard'))
            else:
                return redirect(url_for('employer_dashboard'))
        else:
            flash('Invalid credentials. Please try again.', 'error')
            return redirect(url_for('login'))
    except Exception as e:
        flash(f'Login error: {str(e)}', 'error')
        return redirect(url_for('login'))
    finally:
        cursor.close()
        conn.close()

# Employee Dashboard
@app.route('/employee/dashboard')
def employee_dashboard():
    if 'user_id' not in session or session['user_type'] != 'employee':
        return redirect(url_for('login'))
    
    quote_of_the_day = random.choice(quotes)
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT title, DATE_FORMAT(start_date, '%Y-%m-%d') AS date, 
                   TIME_FORMAT(start_date, '%H:%i') AS start_time, 
                   TIME_FORMAT(end_date, '%H:%i') AS end_time 
            FROM bookings 
            WHERE user_id = %s AND start_date >= NOW() 
            ORDER BY start_date ASC 
            LIMIT 5
        """, (session['user_id'],))
        upcoming_events = cursor.fetchall()
    
    except Exception as e:
        flash(f'Error loading upcoming events: {str(e)}', 'error')
        upcoming_events = []
    
    finally:
        cursor.close()
        conn.close()
    
    return render_template('employee_dashboard.html', 
                           user=session['full_name'], 
                           quote=quote_of_the_day,
                           upcoming_events=upcoming_events)

# Employee Calendar
@app.route('/employee/calendar')
def employee_calendar():
    if 'user_id' not in session or session['user_type'] != 'employee':
        return redirect(url_for('login'))
    
    return render_template('employee_calendar.html', user=session['full_name'])

# Get events for specific date
@app.route('/employee/calendar/date_events', methods=['GET'])
def get_date_events():
    if 'user_id' not in session or session['user_type'] != 'employee':
        return jsonify({'error': 'Unauthorized'}), 401
    
    date = request.args.get('date')
    if not date:
        return jsonify({'error': 'Date parameter required'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT id, title, start_date, end_date 
            FROM bookings 
            WHERE user_id = %s AND DATE(start_date) = %s
            ORDER BY start_date
        """, (session['user_id'], date))
        events = cursor.fetchall()
        
        # Format dates for display
        for event in events:
            event['start_time'] = event['start_date'].strftime('%H:%M')
            if event['end_date']:
                event['end_time'] = event['end_date'].strftime('%H:%M')
            else:
                event['end_time'] = None
            # Remove the original date fields
            del event['start_date']
            del event['end_date']
        
        return jsonify(events)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# Add new calendar event
@app.route('/employee/calendar/add', methods=['POST'])
def add_calendar_event():
    if 'user_id' not in session or session['user_type'] != 'employee':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    if not data or 'title' not in data or 'start' not in data:
        return jsonify({'error': 'Missing required fields'}), 400
    
    title = data['title']
    start_date = data['start']
    end_date = data.get('end', start_date)  # Use start date if end date not provided
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO bookings (user_id, title, start_date, end_date)
            VALUES (%s, %s, %s, %s)
        """, (session['user_id'], title, start_date, end_date))
        conn.commit()
        
        # Get the ID of the newly created event
        event_id = cursor.lastrowid
        
        return jsonify({
            'id': event_id,
            'title': title,
            'start': start_date,
            'end': end_date
        }), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# Update calendar event
@app.route('/employee/calendar/update/<int:event_id>', methods=['PUT'])
def update_calendar_event(event_id):
    if 'user_id' not in session or session['user_type'] != 'employee':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # First verify the event belongs to the current user
        cursor.execute("SELECT user_id FROM bookings WHERE id = %s", (event_id,))
        event = cursor.fetchone()
        
        if not event or event['user_id'] != session['user_id']:
            return jsonify({'error': 'Event not found or unauthorized'}), 404
        
        # Build update query based on provided fields
        update_fields = []
        values = []
        
        if 'title' in data:
            update_fields.append("title = %s")
            values.append(data['title'])
        
        if 'start' in data:
            update_fields.append("start_date = %s")
            values.append(data['start'])
        
        if 'end' in data:
            update_fields.append("end_date = %s")
            values.append(data['end'])
        
        if not update_fields:
            return jsonify({'error': 'No valid fields to update'}), 400
        
        values.append(event_id)
        update_query = "UPDATE bookings SET " + ", ".join(update_fields) + " WHERE id = %s"
        
        cursor.execute(update_query, values)
        conn.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# Delete calendar event
@app.route('/employee/calendar/delete/<int:event_id>', methods=['DELETE'])
def delete_calendar_event(event_id):
    if 'user_id' not in session or session['user_type'] != 'employee':
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # First verify the event belongs to the current user
        cursor.execute("SELECT user_id FROM bookings WHERE id = %s", (event_id,))
        event = cursor.fetchone()
        
        if not event or event['user_id'] != session['user_id']:
            return jsonify({'error': 'Event not found or unauthorized'}), 404
        
        cursor.execute("DELETE FROM bookings WHERE id = %s", (event_id,))
        conn.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/employee/profile', methods=['GET', 'POST'])
def employee_profile():
    if 'user_id' not in session or session['user_type'] != 'employee':
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        try:
            # Handle file upload
            profile_photo = None
            if 'profile_photo' in request.files:
                file = request.files['profile_photo']
                if file and file.filename != '':
                    # Secure the filename
                    filename = secure_filename(file.filename)
                    # Generate unique filename
                    unique_filename = f"{user_id}_{int(time.time())}_{filename}"
                    filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
                    file.save(filepath)
                    profile_photo = unique_filename

            # Get form data
            bio = request.form.get('bio', '')
            experience = request.form.get('experience', '')
            skills = request.form.get('skills', '')
            contact_info = request.form.get('contact_info', '')
            location = request.form.get('location', '')

            # VALIDATION CHECKS
            errors = []
            
            # Experience validation (0-50)
            if experience:
                try:
                    exp_num = int(experience)
                    if exp_num < 0 or exp_num > 50:
                        errors.append('Experience must be between 0 and 50 years')
                except ValueError:
                    errors.append('Experience must be a valid number')
            
            # Skills validation (no numbers)
            if skills and any(char.isdigit() for char in skills):
                errors.append('Skills should not contain numbers')
            
            # Location validation (no numbers)
            if location and any(char.isdigit() for char in location):
                errors.append('Location should not contain numbers')
            
            # If there are validation errors, return them
            if errors:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'error': ', '.join(errors)}), 400
                else:
                    for error in errors:
                        flash(error, 'error')
                    return redirect(url_for('employee_profile'))

            # Check if profile exists
            cursor.execute("SELECT user_id FROM eprofile WHERE user_id = %s", (user_id,))
            profile_exists = cursor.fetchone()

            if profile_exists:
                # Update existing profile
                if profile_photo:
                    # Delete old photo if exists
                    cursor.execute("SELECT profile_photo FROM eprofile WHERE user_id = %s", (user_id,))
                    old_photo = cursor.fetchone()
                    if old_photo and old_photo['profile_photo']:
                        old_path = os.path.join(UPLOAD_FOLDER, old_photo['profile_photo'])
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    
                    update_sql = """
                        UPDATE eprofile 
                        SET bio = %s, experience = %s, skills = %s, 
                            contact_info = %s, location = %s, profile_photo = %s
                        WHERE user_id = %s
                    """
                    cursor.execute(update_sql, 
                                (bio, experience, skills, contact_info, location, profile_photo, user_id))
                else:
                    update_sql = """
                        UPDATE eprofile 
                        SET bio = %s, experience = %s, skills = %s, 
                            contact_info = %s, location = %s
                        WHERE user_id = %s
                    """
                    cursor.execute(update_sql, 
                                (bio, experience, skills, contact_info, location, user_id))
            else:
                # Create new profile
                insert_sql = """
                    INSERT INTO eprofile 
                    (user_id, bio, experience, skills, contact_info, location, profile_photo)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(insert_sql, 
                             (user_id, bio, experience, skills, contact_info, location, profile_photo))

            conn.commit()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True})
            else:
                flash('Profile updated successfully!', 'success')
                return redirect(url_for('employee_profile'))

        except Exception as e:
            conn.rollback()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': str(e)}), 500
            else:
                flash(f'Error updating profile: {str(e)}', 'error')
                return redirect(url_for('employee_profile'))
        finally:
            cursor.close()
            conn.close()

    else:  # GET request
        try:
            # Fetch user details
            cursor.execute("SELECT full_name FROM users WHERE id = %s", (user_id,))
            user_details = cursor.fetchone()
            full_name = user_details['full_name'] if user_details else "Unknown"

            # Fetch profile data
            cursor.execute("""
                SELECT bio, experience, skills, contact_info, location, profile_photo 
                FROM eprofile 
                WHERE user_id = %s
            """, (user_id,))
            profile_data = cursor.fetchone()

            # Fetch reviews
            cursor.execute("""
                SELECT r.id, r.rating, r.review_text, r.created_at, 
                       u.full_name as employer_name, u.id as employer_id
                FROM reviews r
                JOIN users u ON r.employer_id = u.id
                WHERE r.employee_id = %s
                ORDER BY r.created_at DESC
            """, (user_id,))
            reviews = cursor.fetchall()

            # Calculate average rating
            avg_rating = 0
            if reviews:
                total = sum(int(review['rating']) for review in reviews if review['rating'])
                avg_rating = total / len(reviews) if reviews else 0

            profile_data_dict = {
                "bio": profile_data['bio'] if profile_data else "",
                "experience": profile_data['experience'] if profile_data else "",
                "skills": profile_data['skills'] if profile_data else "",
                "contact_info": profile_data['contact_info'] if profile_data else "",
                "location": profile_data['location'] if profile_data else "",
                "profile_photo": profile_data['profile_photo'] if profile_data else None
            }

            return render_template('employee_profile.html', 
                                 user=full_name, 
                                 profile=profile_data_dict,
                                 reviews=reviews,
                                 avg_rating=round(avg_rating, 1))
        except Exception as e:
            flash(f'Error loading profile: {str(e)}', 'error')
            return redirect(url_for('employee_dashboard'))
        finally:
            cursor.close()
            conn.close()

 # Configure upload folder
UPLOAD_FOLDER = 'static/uploads/profile_photos'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)           

# Employee Certificates
@app.route('/employee/certificates', methods=['GET', 'POST'])
def employee_certificates():
    if 'user_id' not in session or session['user_type'] != 'employee':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        try:
            title = request.form['title']
            issuing_organization = request.form['issuing_organization']
            issue_date = request.form['issue_date']
            description = request.form.get('description', '')
            certificate_url = request.form['certificate_url']
            
            cursor.execute("""
                INSERT INTO ecertificates 
                (user_id, title, issuing_organization, issue_date, description, certificate_url)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (session['user_id'], title, issuing_organization, issue_date, description, certificate_url))
            
            conn.commit()
            flash('Certificate added successfully!', 'certificate')
        except Exception as e:
            conn.rollback()
            flash(f'Error adding certificate: {str(e)}', 'certificate')
        finally:
            return redirect(url_for('employee_certificates'))
    
    # GET request handling
    try:
        cursor.execute("""
            SELECT id, title, issuing_organization, issue_date, description, certificate_url
            FROM ecertificates
            WHERE user_id = %s
            ORDER BY issue_date DESC
        """, (session['user_id'],))
        certificates = cursor.fetchall()
        
        return render_template('employee_certificates.html', 
                            user=session['full_name'],
                            certificates=certificates)
    except Exception as e:
        flash(f'Error loading certificates: {str(e)}', 'certificate')
        return redirect(url_for('employee_dashboard'))
    finally:
        cursor.close()
        conn.close()

# Delete Certificate
@app.route('/delete_certificate/<int:cert_id>', methods=['POST'])
def delete_certificate(cert_id):
    if 'user_id' not in session or session['user_type'] != 'employee':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # First verify the certificate belongs to the current user
        cursor.execute("SELECT user_id FROM ecertificates WHERE id = %s", (cert_id,))
        cert = cursor.fetchone()
        
        if cert and cert[0] == session['user_id']:
            cursor.execute("DELETE FROM ecertificates WHERE id = %s", (cert_id,))
            conn.commit()
            flash('Certificate deleted successfully!', 'certificate')
        else:
            flash('Certificate not found or you do not have permission to delete it', 'certificate')
    except Exception as e:
        conn.rollback()
        flash(f'Error deleting certificate: {str(e)}', 'certificate')
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('employee_certificates'))

# Employer Dashboard
@app.route('/employer/dashboard')
def employer_dashboard():
    if 'user_id' not in session or session['user_type'] != 'employer':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Fetch distinct locations
        cursor.execute("SELECT DISTINCT location FROM eprofile WHERE location IS NOT NULL AND location != ''")
        locations = [row['location'] for row in cursor.fetchall()]

        # Fetch distinct experience levels
        cursor.execute("SELECT DISTINCT experience FROM users WHERE experience IS NOT NULL AND experience != ''")
        experiences = [row['experience'] for row in cursor.fetchall()]

        return render_template('employer_dashboard.html', 
                               user=session['full_name'], 
                               locations=locations, 
                               experiences=experiences)

    except Exception as e:
        flash(f'Error loading employer dashboard: {str(e)}', 'error')
        return redirect(url_for('login'))
    
    finally:
        cursor.close()
        conn.close()

# Employer Search Route
@app.route('/employer/search', methods=['GET'])
def employer_search():
    if 'user_id' not in session or session['user_type'] != 'employer':
        return jsonify({'error': 'Unauthorized'}), 401

    search_query = request.args.get('query', '').strip()
    skills = request.args.get('skills', '').strip()
    location = request.args.get('location', '').strip()
    min_exp = request.args.get('min_exp', '').strip()
    max_exp = request.args.get('max_exp', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Base query
        sql = """
            SELECT users.id, users.full_name, users.experience, users.skills, 
                   eprofile.bio, eprofile.profile_photo, eprofile.location, eprofile.contact_info
            FROM users
            LEFT JOIN eprofile ON users.id = eprofile.user_id
            WHERE users.user_type = 'employee'
        """
        values = []

        # Search filters
        if search_query:
            sql += " AND (users.full_name LIKE %s OR users.skills LIKE %s OR eprofile.bio LIKE %s)"
            values.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])

        if skills:
            sql += " AND users.skills LIKE %s"
            values.append(f"%{skills}%")

        if location:
            sql += " AND eprofile.location LIKE %s"
            values.append(f"%{location}%")

        # Experience filter
        if min_exp.isdigit():
            sql += " AND users.experience >= %s"
            values.append(int(min_exp))

        if max_exp.isdigit():
            sql += " AND users.experience <= %s"
            values.append(int(max_exp))
        elif max_exp == "20+":  # Handle "20+" case
            sql += " AND users.experience >= 20"

        cursor.execute(sql, values)
        employees = cursor.fetchall()

        return jsonify(employees)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    finally:
        cursor.close()
        conn.close()


# Employer View Employee Profile
@app.route('/employer/profile/<int:employee_id>')
def employer_view_profile(employee_id):
    if 'user_id' not in session or session['user_type'] != 'employer':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Fetch employee details
        cursor.execute("""
            SELECT users.id, users.full_name, users.experience, users.skills, 
                   eprofile.bio, eprofile.profile_photo, eprofile.location, eprofile.contact_info
            FROM users
            LEFT JOIN eprofile ON users.id = eprofile.user_id
            WHERE users.id = %s
        """, (employee_id,))
        profile = cursor.fetchone()

        if not profile:
            flash('Employee profile not found.', 'error')
            return redirect(url_for('employer_dashboard'))

        # Fetch employee's certificates
        cursor.execute("""
            SELECT id, title, issuing_organization, issue_date, description, certificate_url
            FROM ecertificates
            WHERE user_id = %s
            ORDER BY issue_date DESC
        """, (employee_id,))
        certificates = cursor.fetchall()

        # Fetch reviews for this employee
        cursor.execute("""
            SELECT r.id, r.rating, r.review_text, r.created_at, 
                   u.full_name as employer_name, u.id as employer_id
            FROM reviews r
            JOIN users u ON r.employer_id = u.id
            WHERE r.employee_id = %s
            ORDER BY r.created_at DESC
        """, (employee_id,))
        reviews = cursor.fetchall()

        # Calculate average rating - FIXED VERSION
        avg_rating = 0
        if reviews:
            total = 0
            count = 0
            for review in reviews:
                # Ensure rating is treated as a number
                rating = int(review['rating']) if review['rating'] else 0
                total += rating
                count += 1
            avg_rating = total / count if count > 0 else 0

        return render_template('employer_profile.html', 
                             profile=profile,
                             employee_id=employee_id,
                             certificates=certificates,
                             reviews=reviews,
                             avg_rating=round(avg_rating, 1),
                             current_user_id=session['user_id'])
    
    except Exception as e:
        flash(f'Error loading profile: {str(e)}', 'error')
        return redirect(url_for('employer_dashboard'))
    
    finally:
        cursor.close()
        conn.close()

# API endpoint to get employee's calendar events
@app.route('/employer/calendar_events/<int:employee_id>')
def get_employee_calendar_events(employee_id):
    if 'user_id' not in session or session['user_type'] != 'employer':
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT id, title, start_date as start, end_date as end 
            FROM bookings 
            WHERE user_id = %s
            ORDER BY start_date
        """, (employee_id,))
        events = cursor.fetchall()
        
        # Convert datetime objects to strings
        for event in events:
            event['start'] = event['start'].isoformat() if event['start'] else None
            event['end'] = event['end'].isoformat() if event['end'] else None
        
        return jsonify(events)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# Route to Submit a Review
@app.route('/submit_review', methods=['POST'])
def submit_review():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 403

    # Get data from form
    employee_id = request.form.get('employee_id')
    rating = request.form.get('rating')
    review_text = request.form.get('review_text', '')
    employer_id = session['user_id']

    # Validate required fields
    if not all([employee_id, rating]):
        return jsonify({"error": "Missing required fields"}), 400

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Insert review
        cursor.execute("""
            INSERT INTO reviews (employee_id, employer_id, rating, review_text)
            VALUES (%s, %s, %s, %s)
        """, (employee_id, employer_id, rating, review_text))
        
        # Get the newly created review with employer info
        cursor.execute("""
            SELECT r.id, r.rating, r.review_text, r.created_at, 
                   u.full_name as employer_name
            FROM reviews r
            JOIN users u ON r.employer_id = u.id
            WHERE r.id = LAST_INSERT_ID()
        """)
        new_review = cursor.fetchone()
        
        # Calculate new average rating
        cursor.execute("""
            SELECT AVG(rating) as avg_rating, COUNT(*) as review_count
            FROM reviews 
            WHERE employee_id = %s
        """, (employee_id,))
        rating_data = cursor.fetchone()
        
        avg_rating = round(float(rating_data['avg_rating']), 1) if rating_data['avg_rating'] else 0
        review_count = rating_data['review_count']
        
        conn.commit()
        
        return jsonify({
            "success": True,
            "review": new_review,
            "avg_rating": avg_rating,
            "review_count": review_count
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/employer/contact/<int:employee_id>')
def employer_contact(employee_id):
    if 'user_id' not in session or session['user_type'] != 'employer':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get employee's email and name
        cursor.execute("SELECT email, full_name FROM users WHERE id = %s", (employee_id,))
        employee = cursor.fetchone()
        
        if not employee:
            flash('Employee not found', 'error')
            return redirect(url_for('employer_dashboard'))
        
        employer_name = session['full_name']
        subject = f"Job Opportunity from {employer_name}"
        body = f"Dear {employee['full_name']},\n\nI came across your profile on Skillink and would like to discuss a potential opportunity with you.\n\nBest regards,\n{employer_name}"
        
        # Create Gmail URL
        gmail_url = (
            f"https://mail.google.com/mail/?view=cm&fs=1"
            f"&to={quote(employee['email'])}"
            f"&su={quote(subject)}"
            f"&body={quote(body)}"
        )
        
        return redirect(gmail_url)
    
    except Exception as e:
        flash(f'Error contacting employee: {str(e)}', 'error')
        return redirect(url_for('employer_dashboard'))
    
    finally:
        cursor.close()
        conn.close()

# Logout Route
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)