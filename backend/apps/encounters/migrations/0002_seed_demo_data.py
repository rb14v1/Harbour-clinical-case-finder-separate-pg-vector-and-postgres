"""
Idempotent data migration that seeds a demo clinician + admin, a handful of
patients, and a coherent set of encounters spread across several specialties
(cardiology, pediatrics, oncology, general_medicine, dermatology) so the app
is immediately browsable/testable after `migrate`, with no manual setup
step. Most encounters have consent_for_research=True (eligible to surface in
other clinicians' similarity searches); a few are False, to exercise that
filter.

Embeddings are computed at seed time via the same apps.common.ai.get_embedding
function used everywhere else, and upserted into Qdrant via
apps.common.qdrant_store - NOT just into Postgres. This is the one place
besides apps/encounters/signals.py that writes to Qdrant, and it mirrors the
same "two separate databases" trade-off: if Qdrant is briefly unreachable at
migrate time, we catch and log a warning rather than fail the migration -
the Postgres side still seeds successfully, and `python manage.py
sync_vectors` can repair Qdrant afterwards.

Safe to run repeatedly: skips seeding if the demo clinician (or their
encounters) already exist.
"""
import logging

from django.db import migrations

logger = logging.getLogger(__name__)

CLINICIAN_EMAIL = "clinician@example.com"
ADMIN_EMAIL = "admin@example.com"
DEMO_PASSWORD = "demo12345"

PATIENTS = [
    ("Maria Alvarez", "1965-03-14", "MRN-10001"),
    ("James Whitfield", "1978-11-02", "MRN-10002"),
    ("Priya Natarajan", "2014-06-21", "MRN-10003"),
    ("Thomas O'Brien", "1952-09-09", "MRN-10004"),
]

# (patient_index, specialty, chief_complaint, notes, diagnosis, treatment, consent)
ENCOUNTERS = [
    (
        0, "cardiology",
        "Intermittent chest tightness on exertion",
        "Patient reports chest tightness climbing stairs, resolves with rest. "
        "No radiation to arm or jaw. Mild dyspnea. Risk factors: hypertension, "
        "former smoker.",
        "Stable angina, likely coronary artery disease",
        "Started on sublingual nitroglycerin PRN, referred for exercise stress "
        "test, started low-dose aspirin and atorvastatin.",
        True,
    ),
    (
        1, "cardiology",
        "Palpitations and lightheadedness",
        "Episodes of rapid, irregular heartbeat lasting several minutes, "
        "associated with lightheadedness but no syncope. No chest pain.",
        "Paroxysmal atrial fibrillation",
        "Started on a beta blocker and anticoagulation per CHA2DS2-VASc "
        "score, referred to electrophysiology for possible ablation.",
        True,
    ),
    (
        3, "cardiology",
        "Shortness of breath on exertion with leg swelling",
        "Progressive dyspnea over two weeks, orthopnea, bilateral ankle "
        "edema. History of prior myocardial infarction.",
        "Congestive heart failure exacerbation",
        "IV furosemide, fluid restriction, uptitrated ACE inhibitor, "
        "scheduled follow-up echocardiogram.",
        True,
    ),
    (
        1, "cardiology",
        "Chest discomfort with exertion, worse than before",
        "Similar chest tightness to a prior episode, now occurring with "
        "less exertion and lasting longer. Denies rest pain.",
        "Unstable angina",
        "Admitted for observation, serial troponins, started heparin "
        "infusion, urgent cardiology consult.",
        False,
    ),
    (
        2, "pediatrics",
        "Fever and ear pain for two days",
        "Child pulling at right ear, fussy, fever to 38.9C. Decreased "
        "appetite. No cough or rhinorrhea.",
        "Acute otitis media",
        "Started amoxicillin, advised ibuprofen for fever, follow-up in 2 "
        "weeks if symptoms persist.",
        True,
    ),
    (
        2, "pediatrics",
        "Wheeze and cough overnight",
        "Recurrent nighttime cough and audible wheeze, worse with upper "
        "respiratory infections. Family history of asthma.",
        "Reactive airway disease, likely early asthma",
        "Started albuterol inhaler with spacer, provided asthma action "
        "plan, follow-up in 4 weeks.",
        True,
    ),
    (
        2, "pediatrics",
        "Rash and itching after starting new food",
        "Widespread hives appeared within an hour of eating peanut butter "
        "for the first time, with lip swelling.",
        "Food allergy, likely peanut",
        "Treated with oral antihistamine, prescribed epinephrine "
        "auto-injector, referred to pediatric allergy/immunology.",
        True,
    ),
    (
        2, "pediatrics",
        "Persistent fever and ear pulling",
        "Three days of fever, irritability, and pulling at the ear, poor "
        "sleep. Similar episode treated two months ago.",
        "Recurrent acute otitis media",
        "Started amoxicillin-clavulanate given recent prior antibiotic "
        "course, referred to ENT for recurrent infections.",
        False,
    ),
    (
        0, "oncology",
        "Unintentional weight loss and fatigue",
        "Ten-pound weight loss over two months without dieting, persistent "
        "fatigue, occasional night sweats. No fever.",
        "Suspected lymphoma, pending biopsy",
        "Ordered CT chest/abdomen/pelvis, referred for excisional lymph "
        "node biopsy, baseline labs including LDH.",
        True,
    ),
    (
        3, "oncology",
        "New lump found on self-exam",
        "Patient noticed a firm, non-tender lump; no skin changes or "
        "nipple discharge. No family history reported previously.",
        "Breast mass, suspicious on imaging - biopsy pending",
        "Diagnostic mammogram and ultrasound ordered, core needle biopsy "
        "scheduled, referred to breast surgery.",
        True,
    ),
    (
        1, "oncology",
        "Persistent cough and blood-tinged sputum",
        "Six-week cough, recent hemoptysis, 15-pound weight loss. Long "
        "smoking history.",
        "Suspected bronchogenic carcinoma, pending tissue diagnosis",
        "Chest CT with contrast ordered, referred to pulmonology for "
        "bronchoscopy and biopsy, smoking cessation counseling.",
        True,
    ),
    (
        0, "oncology",
        "Fatigue and easy bruising",
        "Progressive fatigue, frequent bruising, and gum bleeding over the "
        "past month. No recent trauma.",
        "Pancytopenia, suspected acute leukemia - pending bone marrow biopsy",
        "Urgent CBC with differential and peripheral smear, same-day "
        "hematology referral, bone marrow biopsy scheduled.",
        False,
    ),
    (
        3, "general_medicine",
        "Routine follow-up for hypertension and diabetes",
        "Stable blood pressure readings at home, occasional missed "
        "metformin doses, no new symptoms.",
        "Hypertension and type 2 diabetes, both reasonably controlled",
        "Continued current antihypertensive and metformin, reinforced "
        "medication adherence, ordered HbA1c and lipid panel.",
        True,
    ),
    (
        1, "general_medicine",
        "Fatigue and cold intolerance",
        "Several months of fatigue, weight gain, feeling cold, dry skin, "
        "and constipation.",
        "Primary hypothyroidism",
        "Started levothyroxine, ordered baseline TSH and free T4, "
        "follow-up labs in 6 weeks.",
        True,
    ),
    (
        2, "general_medicine",
        "Sore throat and low-grade fever",
        "Three days of sore throat, mild fever, no cough. Rapid strep test "
        "performed in clinic.",
        "Streptococcal pharyngitis",
        "Started penicillin V, advised supportive care and return if "
        "symptoms worsen.",
        True,
    ),
    (
        0, "dermatology",
        "Changing mole on the back",
        "Patient's partner noticed a mole that has grown and darkened over "
        "six months, with irregular borders.",
        "Atypical nevus, suspicious for melanoma - pending excisional biopsy",
        "Dermoscopy performed, excisional biopsy with margins scheduled, "
        "patient counseled on sun protection.",
        True,
    ),
    (
        3, "dermatology",
        "Itchy, scaly patches on elbows and knees",
        "Recurrent well-demarcated red, scaly plaques on extensor surfaces, "
        "worse in winter. Family history of similar skin condition.",
        "Plaque psoriasis",
        "Started high-potency topical corticosteroid, emollients, referred "
        "to dermatology if inadequate response in 4 weeks.",
        True,
    ),
    (
        2, "dermatology",
        "Widespread itchy rash after new detergent",
        "Diffuse itchy, red, slightly raised rash on trunk and arms "
        "starting two days after switching laundry detergent.",
        "Contact dermatitis, allergic",
        "Advised discontinuing the new detergent, started oral "
        "antihistamine and topical corticosteroid.",
        False,
    ),
]


def seed_demo_data(apps, schema_editor):
    from django.contrib.auth.hashers import make_password
    from django.utils import timezone

    from apps.common import qdrant_store
    from apps.common.ai import get_embedding

    User = apps.get_model("accounts", "User")
    Patient = apps.get_model("patients", "Patient")
    Encounter = apps.get_model("encounters", "Encounter")

    clinician, _ = User.objects.get_or_create(
        email=CLINICIAN_EMAIL,
        defaults={
            "password": make_password(DEMO_PASSWORD),
            "full_name": "Dr. Dana Reyes",
            "role": "clinician",
            "specialty": "cardiology",
            "is_active": True,
        },
    )
    User.objects.get_or_create(
        email=ADMIN_EMAIL,
        defaults={
            "password": make_password(DEMO_PASSWORD),
            "full_name": "Alex Kim",
            "role": "admin",
            "is_active": True,
            "is_staff": True,
        },
    )

    if Encounter.objects.filter(clinician=clinician).exists():
        # Already seeded (e.g. migrate run a second time) - skip.
        return

    patients = []
    for full_name, dob, mrn in PATIENTS:
        patient, _ = Patient.objects.get_or_create(
            mrn=mrn,
            defaults={"full_name": full_name, "date_of_birth": dob},
        )
        patients.append(patient)

    now = timezone.now()
    created_encounters = []
    for patient_index, specialty, chief_complaint, notes, diagnosis, treatment, consent in ENCOUNTERS:
        encounter = Encounter.objects.create(
            patient=patients[patient_index],
            clinician=clinician,
            specialty=specialty,
            chief_complaint=chief_complaint,
            notes=notes,
            diagnosis=diagnosis,
            treatment=treatment,
            consent_for_research=consent,
            created_at=now,
        )
        created_encounters.append(encounter)

    # Seed Qdrant too, not just Postgres - guarded so a briefly unreachable
    # Qdrant (e.g. real-Postgres/no-Qdrant-yet deployments) doesn't fail the
    # whole migration. `python manage.py sync_vectors` repairs this later.
    try:
        qdrant_store.ensure_collection()
        for encounter in created_encounters:
            text = f"{encounter.chief_complaint} {encounter.notes} {encounter.diagnosis}"
            vector = get_embedding(text)
            qdrant_store.upsert_point(
                point_id=encounter.id,
                vector=vector,
                payload={
                    "specialty": encounter.specialty,
                    "consent_for_research": encounter.consent_for_research,
                    "clinician_id": encounter.clinician_id,
                },
            )
    except Exception:
        logger.warning(
            "Could not seed Qdrant during migration (Qdrant may be "
            "unreachable) - Postgres seed data was still created. Run "
            "`python manage.py sync_vectors` once Qdrant is available.",
            exc_info=True,
        )


def unseed_demo_data(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Encounter = apps.get_model("encounters", "Encounter")
    clinician = User.objects.filter(email=CLINICIAN_EMAIL).first()
    if clinician is not None:
        Encounter.objects.filter(clinician=clinician).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("patients", "0001_initial"),
        ("encounters", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_demo_data, unseed_demo_data),
    ]
