from django.core.exceptions import ValidationError


def masked_name(full_name):
    """Historical mask only; current publication uses results.mask_identity."""
    parts = full_name.split()
    # With only an unstructured full_name, extra tokens cannot reliably distinguish
    # middle names from compound given names/surnames. Never guess that boundary.
    if (len(parts) != 2 or len(parts[0]) < 3 or len(parts[1]) < 2
            or not all(part.isalpha() for part in parts)
            or parts[1].casefold() in {'jr', 'sr', 'ii', 'iii', 'iv', 'v'}):
        raise ValidationError('Name masking needs review: multi-part names, suffixes, compound surnames or very short names are unresolved.')
    first, surname = parts
    return first[0] + '*' * (len(first) - 2) + first[-1] + ' ' + surname[0] + '.'
