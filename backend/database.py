"""
Database models and operations for MedSAGE application
"""
from datetime import datetime
from typing import Dict, List, Optional
import uuid

class DatabaseManager:
    """Handles database operations for the application."""
    
    def __init__(self, client, database_name):
        self.client = client
        self.db = client[database_name]
        self.patients = self.db.patients
        self.diagnoses = self.db.diagnoses
        self.users = self.db.users
        self.sessions = self.db.sessions
        
        # Create indexes for better performance
        self._create_indexes()
    
    def _create_indexes(self):
        """Create database indexes for better performance."""
        # Patient collection indexes
        self.patients.create_index("patient_id", unique=True)
        self.patients.create_index("email")
        self.patients.create_index("created_at")
        
        # Diagnosis collection indexes
        self.diagnoses.create_index("patient_id")
        self.diagnoses.create_index("diagnosis_id", unique=True)
        self.diagnoses.create_index("created_at")
        
        # User collection indexes
        self.users.create_index("email", unique=True)
        self.users.create_index("user_id", unique=True)
        
        # Session collection indexes
        self.sessions.create_index("session_id", unique=True)
        self.sessions.create_index("expires_at", expireAfterSeconds=0)
    
    def create_patient(self, patient_data: Dict) -> str:
        """Create a new patient record."""
        patient_id = str(uuid.uuid4())
        patient_record = {
            "patient_id": patient_id,
            "name": patient_data.get("name"),
            "email": patient_data.get("email"),
            "phone": patient_data.get("phone"),
            "date_of_birth": patient_data.get("date_of_birth"),
            "blood_group": patient_data.get("blood_group"),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "is_active": True
        }
        
        result = self.patients.insert_one(patient_record)
        return patient_id if result.inserted_id else None
    
    def create_diagnosis(self, diagnosis_data: Dict) -> str:
        """Create a new diagnosis record."""
        try:
            diagnosis_id = str(uuid.uuid4())
            diagnosis_record = {
                "diagnosis_id": diagnosis_id,
                "patient_id": diagnosis_data.get("patient_id"),
                "symptoms": diagnosis_data.get("symptoms", []),
                "age": diagnosis_data.get("age"),
                "weight": diagnosis_data.get("weight"),
                "height": diagnosis_data.get("height"),
                "diagnosis_text": diagnosis_data.get("diagnosis_text"),
                "image_analysis_result": diagnosis_data.get("image_analysis_result"),
                "image_path": diagnosis_data.get("image_path"),
                "confidence_score": diagnosis_data.get("confidence_score"),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "status": "draft"  # draft, reviewed, finalized
            }
            
            print(f"[DATABASE] Inserting diagnosis: {diagnosis_id}")
            result = self.diagnoses.insert_one(diagnosis_record)
            print(f"[DATABASE] Insert result: {result.inserted_id}")
            
            if result.inserted_id:
                # Verify the record was inserted
                verify = self.diagnoses.find_one({"diagnosis_id": diagnosis_id})
                if verify:
                    print(f"[DATABASE] Diagnosis {diagnosis_id} successfully verified in database")
                    return diagnosis_id
                else:
                    print(f"[DATABASE] ERROR: Diagnosis {diagnosis_id} not found after insert")
                    return None
            else:
                print(f"[DATABASE] ERROR: Insert operation failed")
                return None
                
        except Exception as e:
            print(f"[DATABASE] ERROR in create_diagnosis: {str(e)}")
            import traceback
            print(f"[DATABASE] Traceback: {traceback.format_exc()}")
            return None
    
    def get_patient_by_id(self, patient_id: str) -> Optional[Dict]:
        """Retrieve patient by ID."""
        return self.patients.find_one({"patient_id": patient_id, "is_active": True})
    
    def get_diagnosis_by_id(self, diagnosis_id: str) -> Optional[Dict]:
        """Retrieve diagnosis by ID."""
        return self.diagnoses.find_one({"diagnosis_id": diagnosis_id})
    
    def get_patient_diagnoses(self, patient_id: str) -> List[Dict]:
        """Get all diagnoses for a patient."""
        return list(self.diagnoses.find(
            {"patient_id": patient_id}
        ).sort("created_at", -1))
    
    def update_diagnosis(self, diagnosis_id: str, update_data: Dict) -> bool:
        """Update diagnosis record."""
        update_data["updated_at"] = datetime.utcnow()
        result = self.diagnoses.update_one(
            {"diagnosis_id": diagnosis_id},
            {"$set": update_data}
        )
        return result.modified_count > 0
    
    def create_user(self, user_data: Dict) -> str:
        """Create a new user (doctor/admin)."""
        user_id = str(uuid.uuid4())
        user_record = {
            "user_id": user_id,
            "email": user_data.get("email"),
            "password_hash": user_data.get("password_hash"),
            "name": user_data.get("name"),
            "role": user_data.get("role", "doctor"),  # doctor, admin
            "license_number": user_data.get("license_number"),
            "specialization": user_data.get("specialization"),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "is_active": True,
            "last_login": None
        }
        
        result = self.users.insert_one(user_record)
        return user_id if result.inserted_id else None
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email."""
        return self.users.find_one({"email": email, "is_active": True})
    
    def update_last_login(self, user_id: str):
        """Update user's last login timestamp."""
        self.users.update_one(
            {"user_id": user_id},
            {"$set": {"last_login": datetime.utcnow()}}
        )
    
    def create_session(self, session_data: Dict) -> str:
        """Create a new session record."""
        session_id = str(uuid.uuid4())
        session_record = {
            "session_id": session_id,
            "user_id": session_data.get("user_id"),
            "created_at": datetime.utcnow(),
            "expires_at": session_data.get("expires_at"),
            "ip_address": session_data.get("ip_address"),
            "user_agent": session_data.get("user_agent"),
            "is_active": True
        }
        
        result = self.sessions.insert_one(session_record)
        return session_id if result.inserted_id else None
    
    def get_active_session(self, session_id: str) -> Optional[Dict]:
        """Get active session by ID."""
        return self.sessions.find_one({
            "session_id": session_id,
            "is_active": True,
            "expires_at": {"$gt": datetime.utcnow()}
        })
    
    def invalidate_session(self, session_id: str):
        """Invalidate a session."""
        self.sessions.update_one(
            {"session_id": session_id},
            {"$set": {"is_active": False}}
        )

    def get_recent_diagnoses(self, limit: int = 50) -> List[Dict]:
        """Get recent diagnoses for dashboard."""
        return list(self.diagnoses.find().sort("created_at", -1).limit(limit))
    
    def get_diagnosis_stats(self) -> Dict:
        """Get diagnosis statistics."""
        pipeline = [
            {"$group": {
                "_id": None,
                "total_diagnoses": {"$sum": 1},
                "avg_confidence": {"$avg": "$confidence_score"}
            }}
        ]
        
        result = list(self.diagnoses.aggregate(pipeline))
        return result[0] if result else {"total_diagnoses": 0, "avg_confidence": 0}
