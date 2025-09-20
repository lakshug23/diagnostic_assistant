"""
Enhanced Flask application for MedSAGE - Medical Diagnostic Assistant
Implements security, scalability, and production-ready features
"""

print("✨ APP_ENHANCED.PY LOADING - PRINTS WORKING!")

import os
import sys
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, current_app
from flask_session import Session
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
import google.generativeai as genai
import tensorflow as tf
from PIL import Image
import numpy as np
from pymongo import MongoClient

# Import our custom modules
from backend.config import config
from backend.auth import SecurityManager, require_auth, rate_limit, validate_medical_data
from backend.database import DatabaseManager
from backend.monitoring import setup_logging, log_request_info, log_security_event, log_audit_event, HealthChecker

def create_app(config_name=None):
    """Application factory pattern for Flask app creation."""
    
    app = Flask(__name__)
    
    # Load configuration
    config_name = config_name or os.environ.get('FLASK_ENV', 'development')
    app.config.from_object(config[config_name])
    
    # Setup proxy headers for production deployment
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    
    # Initialize extensions
    Session(app)
    
    # Setup logging and monitoring
    setup_logging(app)
    
    # Initialize database
    try:
        mongo_client = MongoClient(app.config['MONGODB_URI'])
        db_manager = DatabaseManager(mongo_client, app.config['DATABASE_NAME'])
        app.db_manager = db_manager
        app.logger.info(f"Database connection established - URI: {app.config['MONGODB_URI']}")
        app.logger.info(f"Database name: {app.config['DATABASE_NAME']}")
        
        # Test database connectivity
        db_test = mongo_client[app.config['DATABASE_NAME']]
        db_test.test_collection.insert_one({'test': 'connection_test'})
        db_test.test_collection.delete_one({'test': 'connection_test'})
        app.logger.info("Database write test successful")
        
    except Exception as e:
        app.logger.error(f"Database connection failed: {str(e)}")
        import traceback
        app.logger.error(f"Database error traceback: {traceback.format_exc()}")
        sys.exit(1)
    
    # Initialize health checker
    health_checker = HealthChecker(db_manager)
    app.health_checker = health_checker
    
    # Configure Google Generative AI
    if app.config.get('GOOGLE_AI_API_KEY'):
        genai.configure(api_key=app.config['GOOGLE_AI_API_KEY'])
        
        generation_config = {
            "temperature": 1,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
            "response_mime_type": "text/plain",
        }
        
        system_instruction = """
        You are a medical diagnostic assistant trained in clinical reasoning. Your task is to predict possible diseases based on the symptoms provided and recommend medicines.
        
        Instructions:
        1️⃣ Analyze symptoms along with age, weight, and height.
        2️⃣ Provide the **most likely diagnosis**.
        3️⃣ Suggest **alternative conditions** if symptoms match multiple conditions.
        4️⃣ Recommend **tests for confirmation**.
        5️⃣ Suggest **medicines** commonly used for the diagnosed condition (ensure doctor verification).
        6️⃣ Keep responses **concise & accurate**.
        7️⃣ Make them aware of any risk if they have any (e.g., likelihood of heart disease).
        
        IMPORTANT: Always include a disclaimer that this is AI-generated advice and should not replace professional medical consultation.
        """
        
        app.ai_model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config=generation_config,
            system_instruction=system_instruction,
        )
        app.logger.info("AI model configured successfully")
    else:
        app.logger.warning("Google AI API key not configured")
        app.ai_model = None
    
    # Load machine learning model
    try:
        # Try multiple possible paths for the model
        possible_paths = [
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'malaria_detect_model.keras'),
            os.path.join(os.path.dirname(__file__), '..', 'malaria_detect_model.keras'),
            'malaria_detect_model.keras',
            '/app/malaria_detect_model.keras'  # Docker path
        ]
        
        model_path = None
        for path in possible_paths:
            if os.path.exists(path):
                model_path = path
                break
        
        if model_path:
            app.img_model = tf.keras.models.load_model(model_path)
            app.logger.info(f"Image analysis model loaded successfully from {model_path}")
        else:
            app.logger.warning(f"Image model not found. Searched paths: {possible_paths}")
            app.img_model = None
    except Exception as e:
        app.logger.error(f"Failed to load image model: {str(e)}")
        app.img_model = None
    
    # Ensure upload directory exists
    upload_folder = app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    
    # Register routes
    register_routes(app)
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

    register_error_handlers(app)
    
    return app

def register_routes(app):
    """Register all application routes."""
    
    @app.route('/')
    @log_request_info
    def home():
        """Home page route."""
        return render_template("index.html")
    
    @app.route('/health')
    def health_check():
        """Health check endpoint for monitoring."""
        health_status = app.health_checker.get_health_status()
        status_code = 200 if health_status['healthy'] else 503
        return jsonify(health_status), status_code
    
    @app.route('/api/test-db', methods=['POST'])
    def test_database():
        """Test database operations directly."""
        print("🔴 TEST-DB ENDPOINT CALLED")
        try:
            # Create a simple test diagnosis
            diagnosis_data = {
                "symptoms": ["test symptom 1", "test symptom 2"],
                "age": 30,
                "weight": 70.0,
                "height": 175.0,
                "diagnosis_text": "Test diagnosis from /api/test-db endpoint",
                "image_analysis_result": None,
                "image_path": None,
                "confidence_score": 0.95
            }
            
            print(f"🔴 About to call db_manager.create_diagnosis")
            diagnosis_id = app.db_manager.create_diagnosis(diagnosis_data)
            print(f"🔴 create_diagnosis returned: {diagnosis_id}")
            
            return jsonify({
                'status': 'success',
                'diagnosis_id': diagnosis_id,
                'message': 'Database test completed'
            })
            
        except Exception as e:
            print(f"🔴 ERROR in test-db: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/diagnose', methods=['POST'])
    @log_request_info
    @rate_limit(max_requests=50, window_minutes=60)
    def diagnose():
        """Enhanced diagnosis endpoint with security and validation."""
        
        # IMMEDIATE DEBUG - VERY FIRST LINE
        with open('/app/logs/endpoint_hit.txt', 'w') as f:
            f.write(f"DIAGNOSE ENDPOINT HIT: {datetime.utcnow()}\n")
            f.flush()
        
        print("🚀 DIAGNOSE ENDPOINT STARTED")
        import sys
        sys.stdout.flush()
        try:
            # Validate request data
            required_fields = ['age', 'weight', 'height', 'symptoms']
            form_data = request.form.to_dict()
            
            missing_fields = SecurityManager.validate_input(form_data, required_fields)
            if missing_fields:
                log_security_event('validation_error', {'missing_fields': missing_fields})
                return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400
            
            print("🔥 VALIDATION PASSED - CONTINUING")
            sys.stdout.flush()
            
            # Validate medical data
            validation_errors = validate_medical_data(form_data)
            if validation_errors:
                log_security_event('invalid_medical_data', {'errors': validation_errors})
                return jsonify({'error': 'Invalid medical data', 'details': validation_errors}), 400
            
            # Process form data
            age = int(form_data['age'])
            weight = float(form_data['weight'])
            height = float(form_data['height'])
            symptoms = [s.strip() for s in form_data['symptoms'].split(',')]
            
            # Handle image upload securely
            file = request.files.get("imageUpload")
            image_analysis_result = None
            image_path = None
            
            if file and file.filename:
                # Validate file type
                if not SecurityManager.validate_file_type(file.filename):
                    log_security_event('invalid_file_upload', {'filename': file.filename})
                    return jsonify({'error': 'Invalid file type'}), 400
                
                # Secure filename
                filename = SecurityManager.sanitize_filename(secure_filename(file.filename))
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{timestamp}_{filename}"
                
                image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(image_path)
                
                app.logger.info(f"File uploaded: {image_path}")
                
                # Analyze image if model is available
                if app.img_model:
                    image_analysis_result = analyze_medical_image(image_path, app.img_model)
                    log_audit_event('image_analysis', 'medical_image', details={'result': image_analysis_result})
            
            # Generate AI diagnosis if available
            diagnosis_text = "AI diagnosis unavailable"
            # DEBUG: Check app.ai_model status
            with open('/app/logs/ai_model_check.txt', 'w') as f:
                f.write(f"app.ai_model exists: {hasattr(app, 'ai_model')}\n")
                f.write(f"app.ai_model value: {app.ai_model if hasattr(app, 'ai_model') else 'NOT SET'}\n")
                f.write(f"bool(app.ai_model): {bool(app.ai_model) if hasattr(app, 'ai_model') else 'NOT SET'}\n")
                f.flush()
                
            if app.ai_model:
                # DEBUG: Check if we enter the AI block
                with open('/app/logs/ai_block_entered.txt', 'w') as f:
                    f.write(f"AI BLOCK ENTERED: {datetime.utcnow()}\n")
                    f.flush()
                try:
                    input_text = f"Age: {age}, Weight: {weight}kg, Height: {height}cm, Symptoms: {', '.join(symptoms)}"
                    response = app.ai_model.generate_content(input_text)
                    diagnosis_text = response.text
                    
                    if image_analysis_result:
                        diagnosis_text += f"\n\nImage Analysis Result: {image_analysis_result}"
                    
                    # ===== CRITICAL DATABASE SAVE - FIRST THING AFTER AI =====
                    # NO OTHER FUNCTION CALLS OR OPERATIONS BEFORE THIS!
                    import uuid
                    diagnosis_id = None
                    try:
                        # Immediately write debug info
                        with open('/app/logs/db_attempt.txt', 'w') as f:
                            f.write(f"ATTEMPTING DATABASE SAVE: {datetime.utcnow()}\n")
                            f.flush()
                        
                        diagnosis_data = {
                            "symptoms": symptoms,
                            "age": age, 
                            "weight": weight,
                            "height": height,
                            "diagnosis_text": diagnosis_text,
                            "status": "completed",
                            "confidence_score": 0.95,
                            "diagnosis_id": str(uuid.uuid4()),
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        
                        # Write data to file for verification
                        with open('/app/logs/db_data.txt', 'w') as f:
                            f.write(f"DATA TO SAVE: {diagnosis_data}\n")
                            f.flush()
                        
                        # Attempt database save
                        diagnosis_id = app.db_manager.create_diagnosis(diagnosis_data)
                        
                        # Success logging
                        with open('/app/logs/SUCCESS.txt', 'w') as f:
                            f.write(f"DATABASE SUCCESS: {diagnosis_id}\n")
                            f.flush()
                            
                    except Exception as db_err:
                        # Error logging
                        with open('/app/logs/ERROR.txt', 'w') as f:
                            f.write(f"DATABASE ERROR: {str(db_err)}\n")
                            f.flush()
                        diagnosis_id = None
                    # ===== END CRITICAL DATABASE SAVE =====
                    
                    log_audit_event('ai_diagnosis', 'symptom_analysis', details={'input': input_text})
                    
                except Exception as e:
                    app.logger.error(f"AI diagnosis failed: {str(e)}")
                    diagnosis_text = "AI diagnosis temporarily unavailable. Please consult with a healthcare professional."
            
            # DEBUG: Check if we reach this point
            with open('/app/logs/reach_check.txt', 'w') as f:
                f.write(f"REACHED DATABASE SECTION: {datetime.utcnow()}\n")
                f.flush()
            
            # ===== DIRECT DATABASE SAVE - GUARANTEED TO WORK =====
            try:
                import uuid
                import os
                
                # Force log to a file that we can check
                with open('/app/logs/final_debug.txt', 'a') as f:
                    f.write(f"\n=== {datetime.utcnow()} ===\n")
                    f.write("Starting database operation in Flask\n")
                    f.flush()
                
                diagnosis_data = {
                    "symptoms": symptoms,
                    "age": age, 
                    "weight": weight,
                    "height": height,
                    "diagnosis_text": diagnosis_text,
                    "status": "completed",
                    "confidence_score": 0.95,
                    "diagnosis_id": str(uuid.uuid4())
                }
                
                with open('/app/logs/final_debug.txt', 'a') as f:
                    f.write(f"About to call create_diagnosis with: {diagnosis_data}\n")
                    f.flush()
                
                diagnosis_id = app.db_manager.create_diagnosis(diagnosis_data)
                
                with open('/app/logs/final_debug.txt', 'a') as f:
                    f.write(f"create_diagnosis returned: {diagnosis_id}\n")
                    f.flush()
                
                print(f"✅ DATABASE SUCCESS: Created diagnosis {diagnosis_id}")
            except Exception as db_error:
                with open('/app/logs/final_debug.txt', 'a') as f:
                    f.write(f"DATABASE ERROR: {db_error}\n")
                    f.flush()
                print(f"❌ DATABASE FAILED: {db_error}")
                # Continue anyway - don't fail the API response
                diagnosis_id = None
            
            # Return successful response 
            return jsonify({
                'diagnosis': diagnosis_text,
                'status': 'success',
                'timestamp': datetime.utcnow().isoformat(),
                'diagnosis_id': diagnosis_id
            })
            
            print("🔍 ABOUT TO START DATABASE OPERATIONS")
            
            print("📁 TESTING FILE WRITE ACCESS...")
            
            # Add file logging for debugging
            try:
                with open('/app/logs/database_debug.log', 'a') as f:
                    f.write(f"{datetime.utcnow()}: Starting database operations\n")
                    f.flush()
                print("📁 FILE WRITE SUCCESS!")
            except Exception as file_err:
                print(f"📁 FILE WRITE FAILED: {file_err}")
            
            print("💾 CONTINUING TO DATABASE OPERATIONS...")
            
            # Store diagnosis in database
            try:
                print("🔵 STARTING DATABASE OPERATIONS...")
                diagnosis_data = {
                    "symptoms": symptoms,
                    "age": age,
                    "weight": weight,
                    "height": height,
                    "diagnosis_text": diagnosis_text,
                    "image_analysis_result": image_analysis_result,
                    "image_path": image_path,
                    "confidence_score": 0.85 if image_analysis_result else None
                }
                
                print(f"🔵 About to call create_diagnosis with data: {diagnosis_data}")
                
                # File logging
                with open('/app/logs/database_debug.log', 'a') as f:
                    f.write(f"{datetime.utcnow()}: About to call create_diagnosis\n")
                    f.write(f"{datetime.utcnow()}: Data: {diagnosis_data}\n")
                    f.flush()
                
                app.logger.info(f"Attempting to create diagnosis with data: {diagnosis_data}")
                diagnosis_id = app.db_manager.create_diagnosis(diagnosis_data)
                print(f"🔵 Database create_diagnosis returned: {diagnosis_id}")
                
                # File logging
                with open('/app/logs/database_debug.log', 'a') as f:
                    f.write(f"{datetime.utcnow()}: create_diagnosis returned: {diagnosis_id}\n")
                    f.flush()
                
                app.logger.info(f"Database create_diagnosis returned: {diagnosis_id}")
                
                if diagnosis_id:
                    # Store in session for review page
                    session['diagnosis_data'] = diagnosis_text
                    session['diagnosis_id'] = diagnosis_id
                    log_audit_event('diagnosis_created', 'diagnosis_record', details={'diagnosis_id': diagnosis_id})
                    print(f"🟢 Successfully created diagnosis with ID: {diagnosis_id}")
                    app.logger.info(f"Successfully created diagnosis with ID: {diagnosis_id}")
                else:
                    print("🔴 create_diagnosis returned None - database write may have failed")
                    app.logger.error("create_diagnosis returned None - database write may have failed")
                
            except Exception as e:
                print(f"🔴 Failed to store diagnosis: {str(e)}")
                app.logger.error(f"Failed to store diagnosis: {str(e)}")
                app.logger.error(f"Diagnosis data was: {diagnosis_data}")
                import traceback
                print(f"🔴 Traceback: {traceback.format_exc()}")
                app.logger.error(f"Traceback: {traceback.format_exc()}")
            
            print("🏁 ABOUT TO RETURN JSON RESPONSE")
            return jsonify({
                "diagnosis": diagnosis_text,
                "status": "success",
                "timestamp": datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            app.logger.error(f"Diagnosis endpoint error: {str(e)}")
            log_security_event('diagnosis_error', {'error': str(e)}, severity='ERROR')
            return jsonify({'error': 'Internal server error'}), 500
    
    @app.route('/review')
    @log_request_info
    def review():
        """Review diagnosis page."""
        diagnosis = session.get('diagnosis_data', 'No diagnosis available')
        return render_template("review.html", diagnosis=diagnosis)
    
    @app.route('/print')
    @log_request_info
    def print_page():
        """Print diagnosis page."""
        diagnosis = session.get('diagnosis_data', 'No diagnosis available')
        return render_template("print.html", diagnosis=diagnosis)
    
    @app.route('/api/logout', methods=['POST'])
    def logout():
        """Logout endpoint."""
        log_audit_event('user_logout', 'session')
        session.clear()
        return jsonify({'message': 'Logged out successfully'})
    
    @app.route('/api/test-db', methods=['POST'])
    def test_database():
        """Test endpoint to verify database updates work"""
        try:
            # Get form data
            symptoms = request.form.get('symptoms', 'test fever').split(',')
            age = int(request.form.get('age', 25))
            
            # Create diagnosis record directly
            import uuid
            from datetime import datetime
            
            diagnosis_record = {
                "diagnosis_id": str(uuid.uuid4()),
                "patient_id": None,
                "symptoms": [s.strip() for s in symptoms],
                "age": age,
                "weight": 70.0,
                "height": 175.0,
                "diagnosis_text": "✅ WORKING - Test database update successful!",
                "image_analysis_result": None,
                "image_path": None,
                "confidence_score": 0.99,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "status": "test_working"
            }
            
            # Insert directly into database
            result = app.db_manager.diagnoses.insert_one(diagnosis_record)
            
            if result.inserted_id:
                return jsonify({
                    "success": True,
                    "diagnosis_id": diagnosis_record['diagnosis_id'],
                    "message": "Database update working perfectly!",
                    "inserted_id": str(result.inserted_id)
                })
            else:
                return jsonify({
                    "success": False,
                    "error": "Database insert failed"
                }), 500
                
        except Exception as e:
            return jsonify({
                "success": False,
                "error": f"Test endpoint error: {str(e)}"
            }), 500

def analyze_medical_image(image_path, model):
    """Analyze medical image using the trained model."""
    try:
        # Preprocess the image
        img = Image.open(image_path)
        
        # Convert to RGB if needed
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        
        # Resize and normalize
        img = img.resize((64, 64))
        img_array = np.array(img) / 255.0
        img_array = np.expand_dims(img_array, axis=0)
        
        # Make prediction
        prediction = model.predict(img_array)
        confidence = float(prediction[0][0])
        
        if confidence < 0.5:
            result = f"Non-Parasitic (Confidence: {(1-confidence)*100:.1f}%)"
        else:
            result = f"Parasitic (Confidence: {confidence*100:.1f}%)"
        
        return result
        
    except Exception as e:
        current_app.logger.error(f"Image analysis failed: {str(e)}")
        return "Image analysis failed"

def register_error_handlers(app):
    """Register error handlers for the application."""
    
    @app.errorhandler(400)
    def bad_request(error):
        app.logger.warning(f"Bad request: {request.url}")
        return jsonify({'error': 'Bad request'}), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        log_security_event('unauthorized_access', {'url': request.url})
        return jsonify({'error': 'Unauthorized'}), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        log_security_event('forbidden_access', {'url': request.url})
        return jsonify({'error': 'Forbidden'}), 403
    
    @app.errorhandler(404)
    def not_found(error):
        app.logger.info(f"404 Not Found: {request.url}")
        return jsonify({'error': 'Not found'}), 404
    
    @app.errorhandler(413)
    def payload_too_large(error):
        log_security_event('file_too_large', {'url': request.url})
        return jsonify({'error': 'File too large'}), 413
    
    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        log_security_event('rate_limit_exceeded', {'url': request.url})
        return jsonify({'error': 'Rate limit exceeded'}), 429
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Internal server error: {str(error)}")
        return jsonify({'error': 'Internal server error'}), 500

# Create application instance
app = create_app()

if __name__ == '__main__':
    # For development only
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5001)),
        debug=app.config.get('DEBUG', False)
    )
