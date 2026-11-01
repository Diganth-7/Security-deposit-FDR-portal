from datetime import date, timedelta, datetime
from sqlalchemy.orm import Session
from app.database import engine, Base, SessionLocal
from app.models.user import User, UserRole
from app.models.institution import Institution
from app.models.deposit import Deposit, DepositStatus
from app.auth.security import get_password_hash

def seed_database():
    """Initializes tables and seeds initial test data for Phase 1 demonstration idempotently."""
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    
    try:
        # 1. Institutions
        def get_or_create_inst(aicte_id, name, state, city, address, institute_type, email, phone):
            inst = db.query(Institution).filter(Institution.aicte_id == aicte_id).first()
            if not inst:
                inst = Institution(
                    aicte_id=aicte_id,
                    name=name,
                    state=state,
                    city=city,
                    address=address,
                    institute_type=institute_type,
                    contact_email=email,
                    contact_phone=phone
                )
                db.add(inst)
                db.commit()
                db.refresh(inst)
            return inst

        inst1 = get_or_create_inst(
            "1-3329182741",
            "Delhi Technological University (DTU)",
            "Delhi",
            "New Delhi",
            "Shahbad Daulatpur, Main Bawana Road, Delhi 110042",
            "Government State University",
            "registrar@dtu.ac.in",
            "+91-11-27871018"
        )
        inst2 = get_or_create_inst(
            "1-4581290332",
            "College of Engineering, Pune (COEP Tech)",
            "Maharashtra",
            "Pune",
            "Wellesley Rd, Shivajinagar, Pune 411005",
            "Unitary Public University",
            "accounts@coep.ac.in",
            "+91-20-25507000"
        )
        inst3 = get_or_create_inst(
            "1-9872145561",
            "BMS College of Engineering",
            "Karnataka",
            "Bengaluru",
            "Bull Temple Rd, Basavanagudi, Bengaluru 560019",
            "Autonomous Private Aided",
            "finance@bmsce.ac.in",
            "+91-80-26622130"
        )

        # 2. Users
        def get_or_create_user(email, full_name, password, role, institution_id=None):
            user = db.query(User).filter(User.email == email.lower()).first()
            if not user:
                user = User(
                    email=email.lower(),
                    full_name=full_name,
                    hashed_password=get_password_hash(password),
                    role=role,
                    institution_id=institution_id,
                    is_active=True
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            return user

        admin_user = get_or_create_user(
            "admin@aicte.gov.in",
            "Dr. Alok Verma (Director Approval)",
            "Admin@AICTE2026",
            UserRole.ADMIN
        )
        officer_user = get_or_create_user(
            "officer.sharma@aicte.gov.in",
            "Rajesh Sharma (Regional Scrutiny Officer)",
            "Officer@AICTE2026",
            UserRole.OFFICER
        )
        inst_user1 = get_or_create_user(
            "registrar@dtu.ac.in",
            "Prof. S. K. Garg (DTU Registrar)",
            "Dtu@2026Pass",
            UserRole.INSTITUTION,
            institution_id=inst1.id
        )
        inst_user2 = get_or_create_user(
            "finance@coep.ac.in",
            "Dr. V. N. Pande (Finance Officer COEP)",
            "Coep@2026Pass",
            UserRole.INSTITUTION,
            institution_id=inst2.id
        )

        # 3. Deposits
        def get_or_create_deposit(fdr_number, amount, bank_name, branch_name, ifsc_code, issue_date, maturity_date, status, inst_id, submitted_by_id, verified_by_id=None, remarks=None):
            dep = db.query(Deposit).filter(Deposit.fdr_number == fdr_number).first()
            if not dep:
                dep = Deposit(
                    fdr_number=fdr_number,
                    amount=amount,
                    bank_name=bank_name,
                    branch_name=branch_name,
                    ifsc_code=ifsc_code,
                    issue_date=issue_date,
                    maturity_date=maturity_date,
                    status=status,
                    institution_id=inst_id,
                    submitted_by_id=submitted_by_id,
                    verified_by_id=verified_by_id,
                    verification_remarks=remarks,
                    verified_at=datetime.utcnow() - timedelta(days=100) if verified_by_id else None
                )
                db.add(dep)
                db.commit()
                db.refresh(dep)
            return dep

        today = date.today()
        get_or_create_deposit(
            "FDR-SBI-2025-99410",
            3500000.0,
            "State Bank of India",
            "Delhi University Branch",
            "SBIN0001067",
            today - timedelta(days=180),
            today + timedelta(days=365 * 3),
            DepositStatus.ACTIVE,
            inst1.id,
            inst_user1.id,
            officer_user.id,
            "Bank confirmation verified via branch email and letterhead certificate."
        )

        get_or_create_deposit(
            "FDR-PNB-2026-10482",
            1500000.0,
            "Punjab National Bank",
            "Connaught Place New Delhi",
            "PUNB0000100",
            today - timedelta(days=14),
            today + timedelta(days=365 * 5),
            DepositStatus.PENDING_VERIFICATION,
            inst1.id,
            inst_user1.id
        )

        get_or_create_deposit(
            "FDR-BOB-2025-78219",
            5000000.0,
            "Bank of Baroda",
            "Shivajinagar Pune",
            "BARB0SHIVAJ",
            today - timedelta(days=400),
            today + timedelta(days=365 * 4),
            DepositStatus.VERIFIED,
            inst2.id,
            inst_user2.id,
            officer_user.id,
            "Verified against joint lien FDR clause under AICTE Regulations."
        )

        get_or_create_deposit(
            "FDR-CAN-2024-33120",
            2000000.0,
            "Canara Bank",
            "Basavanagudi Bengaluru",
            "CNRB0000542",
            today - timedelta(days=800),
            today - timedelta(days=70),
            DepositStatus.MATURED_ACTION_REQUIRED,
            inst3.id,
            admin_user.id,
            officer_user.id,
            "Maturity reached. Action required from institution."
        )

        # FDR maturing in 30 days
        get_or_create_deposit(
            "FDR-HDFC-2025-30DAYS",
            4000000.0,
            "HDFC Bank",
            "Kashmere Gate Delhi",
            "HDFC0000030",
            today - timedelta(days=335),
            today + timedelta(days=30),
            DepositStatus.ACTIVE,
            inst1.id,
            inst_user1.id,
            officer_user.id,
            "Active AICTE security deposit."
        )

        # FDR maturing in 7 days
        get_or_create_deposit(
            "FDR-AXIS-2025-07DAYS",
            2500000.0,
            "Axis Bank",
            "FC Road Pune",
            "UTIB0000077",
            today - timedelta(days=358),
            today + timedelta(days=7),
            DepositStatus.ACTIVE,
            inst2.id,
            inst_user2.id,
            officer_user.id,
            "Approaching maturity. 7 days remaining."
        )

        # FDR maturing tomorrow (1 day)
        get_or_create_deposit(
            "FDR-ICICI-2025-01DAY",
            3000000.0,
            "ICICI Bank",
            "MG Road Bengaluru",
            "ICIC0000101",
            today - timedelta(days=364),
            today + timedelta(days=1),
            DepositStatus.ACTIVE,
            inst3.id,
            admin_user.id,
            officer_user.id,
            "Matures tomorrow."
        )

        print("Database idempotent seeding completed successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
