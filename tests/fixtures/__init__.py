"""Shared fixtures/synthetic sample text for the test suite.

All text here is synthetic and contains no real PHI.
"""

CLEAN_NOTE = (
    "Patient denies chest pain, shortness of breath, or fever. "
    "No history of MI. BP 120/80, HR 76 bpm. "
    "Allergic to penicillin. Left knee pain, stable."
)

REDUNDANT_NOTE = (
    "Patient came in today. Patient came in today for a visit. "
    "Denies fever or chills. Denies fever or chills. "
    "BP 130/85. BP 130/85. "
    "As previously discussed, patient understands the plan. "
    "Follow up in two weeks. Follow up in two weeks."
)
