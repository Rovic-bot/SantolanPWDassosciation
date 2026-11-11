"""Owner-confirmed PDF checklist (2026-10-24), shared across guidance.

These owner-confirmed lists are presentation, not upload requirements or receipt
states. Existing configured evidence/snapshots and approval services are retained;
physical evidence handling and accepted-document provenance remain OQ-27.
"""

LEGACY_ASSOCIATION_REQUIREMENTS = (
    {'label': 'Membership Application Form'},
    {'label': 'One (1) 2×2 ID Picture'},
    {'label': 'Birth Certificate OR Marriage Certificate',
     'note': 'Bring either civil document; both are not required.'},
    {'label': "Voter's Certificate"},
    {'label': 'One (1) Long Envelope',
     'note': 'A physical item to bring onsite, not a required digital upload.'},
)

# The owner explicitly adopted the supplied PDF's quantities and PWD ID copies.
# Retain the older checklist for earlier field contracts and immutable receipts.
ASSOCIATION_REQUIREMENTS = (
    {'label': 'One (1) long brown envelope',
     'note': 'A physical item to bring onsite, not a required digital upload.'},
    {'label': 'Four (4) photocopies of PWD ID'},
    {'label': "Two (2) photocopies of Voter's Certificate"},
    {'label': 'Two (2) photocopies of Birth Certificate OR Marriage Certificate',
     'note': 'Bring copies of either civil document; both are not required.'},
    {'label': 'Four (4) 2×2 pictures with white background'},
)

PDAO_REQUIREMENTS = (
    {'label': 'PDAO PWD ID Application Form'},
    {'label': 'One (1) 1×1 ID Picture'},
    {'label': 'Proof of Life',
     'note': 'Whole-body photograph holding an updated calendar.'},
    {'label': 'Medical Certificate stating:',
     'details': ('Final diagnosis', 'Functional limitation', "Doctor's name",
                 "Doctor's license number")},
    {'label': 'Birth Certificate OR Marriage Certificate'},
    {'label': "Voter's ID OR Voter's Certificate OR National ID"},
)

REGISTRATION_STEPS = (
    'Prepare the required documents and physical item.',
    'Visit the Barangay Santolan PWD Association Help Desk IN PERSON.',
    'Submit the membership form and requirements in person.',
    'Authorized Association personnel review the submission and applicable verification.',
    'Membership is established only after the required administrative approval.',
)


def membership_guidance():
    return {
        'association_requirements': ASSOCIATION_REQUIREMENTS,
        'pdao_requirements': PDAO_REQUIREMENTS,
        'registration_steps': REGISTRATION_STEPS,
    }
