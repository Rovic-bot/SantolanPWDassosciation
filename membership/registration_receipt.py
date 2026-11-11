"""Reference-only presentation for an owning session's registration receipt."""
from base64 import b64encode
from io import BytesIO

import qrcode

from core.reference_services import display_reference


def reference_confirmation(reference):
    """Encode the already issued reference locally, never applicant information."""
    if not reference:
        return {'reference': '', 'reference_display': '', 'reference_qr': ''}
    displayed = display_reference('association', reference)
    buffer = BytesIO()
    qrcode.make(displayed, box_size=8, border=4).save(buffer, format='PNG')
    return {'reference': reference, 'reference_display': displayed,
            'reference_qr': 'data:image/png;base64,' + b64encode(buffer.getvalue()).decode('ascii')}
