"""The stub's seed data: item bank, accounts and sample admin data.

The topics, concepts and glossary are the real content of backend/content/ (app/content.py), and
the primitives come from the library's catalogue. The rest is sample data for building the
frontend (docs/frontend.md §8): the accounts exist only in the stub and are reset whenever the
server restarts.
"""

from app.content import content

# Topics, concepts and glossary come from backend/content/, shared with `npm run db:seed`.
TOPIC_AREAS = content().taxonomy.topic_areas
CONCEPTS = content().taxonomy.concepts
GLOSSARY = [(g.id, g.concept_id, g.term, g.definition) for g in content().glossary]


# The item bank (check questions with verified answers) also comes from backend/content/.
ITEMS = content().items

# The onboarding diagnostic: one item per topic area, at most five (UC 4.2). The third is the
# question of the wireframe (Fig. 4.1).
DIAGNOSTIC_ITEMS = [8, 16, 5, 10, 12]


STUB_PASSWORD = "password123"

# (email, name, role); every account's password is STUB_PASSWORD.
ACCOUNTS = [
    ("student@fourierlearn.test", "Test Student", "student"),
    ("new@fourierlearn.test", "New Student", "student"),
    ("admin@fourierlearn.test", "Admin", "admin"),
]

# Extra students for the admin pages: (name, days since joining, lessons, disabled).
SAMPLE_STUDENTS = [
    ("Ayesha Khan", 40, 6, False),
    ("Bilal Ahmed", 35, 3, False),
    ("Fatima Noor", 30, 9, False),
    ("Hamza Ali", 28, 1, False),
    ("Zainab Raza", 21, 4, False),
    ("Usman Tariq", 14, 0, True),
    ("Maryam Iqbal", 10, 2, False),
    ("Ali Hassan", 7, 5, False),
    ("Hira Shah", 3, 1, False),
    ("Omar Farooq", 1, 0, False),
]

# Scores of the seeded student, per topic area, as in the progress wireframe (Fig. 4.6).
SEEDED_AREA_SCORES = {
    "Functions and graphs": 0.85,
    "Coordinate geometry": 0.70,
    "Travel graphs": 0.55,
    "Differentiation": 0.40,
    "Integration": 0.25,
}

DEFAULT_PRIOR = 0.3
"""Every concept's score before any evidence (the stub's P(L0))."""

RENDER_ERRORS = [
    "LayoutViolation: label 'B' overlaps 'line' after step 3 of beat 1",
    "InvalidParameters: beat 0 (FunctionGraph): domain: x range must contain the marked points",
    "TTSError: kokoro failed: input text is empty",
]
