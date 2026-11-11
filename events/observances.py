"""Annual calendar references; publishing uses the audited observance service."""
from calendar import month_name, monthrange
from dataclasses import InitVar, dataclass
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


SOURCE_HOSTS = frozenset({
    'ncda.gov.ph', 'ldr.senate.gov.ph', 'issuances-library.senate.gov.ph',
    'www.un.org', 'accessibility.day',
})
CATEGORIES = {'disability': 'Disability observance', 'health': 'Health related — not PWD-specific'}
RECURRENCE_KINDS = frozenset({'whole_month', 'fixed_day', 'fixed_range', 'last_monday', 'third_week', 'third_thursday'})


def validate_source_url(value):
    """Validate links without requesting URLs or trusting a gov.ph substring."""
    URLValidator(schemes=['https'])(value)
    try:
        parts = urlsplit(value)
        invalid = (parts.hostname not in SOURCE_HOSTS or parts.username is not None
                   or parts.password is not None or parts.port is not None
                   or parts.query or parts.fragment or not parts.path.startswith('/')
                   or '\\' in value or any(char.isspace() or ord(char) < 32 for char in value))
    except ValueError:
        invalid = True
    if invalid:
        raise ValidationError('Use a direct HTTPS link from a reviewed official source, without credentials, ports or tracking parameters.')


@dataclass(frozen=True)
class ObservanceReference:
    month: int
    title: str
    recurrence_kind: str
    legal_basis: str
    source_url: str
    description: str
    category: str = 'disability'
    day_start: int | None = None
    day_end: int | None = None
    require_source: InitVar[bool] = True

    def __post_init__(self, require_source):
        if type(self.month) is not int or not 1 <= self.month <= 12:
            raise ValidationError('Choose a month from January to December.')
        if self.recurrence_kind not in RECURRENCE_KINDS or self.category not in CATEGORIES:
            raise ValidationError('Choose a supported recurrence and category.')
        for value, limit in ((self.title, 200), (self.description, 2000)):
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise ValidationError('Provide nonempty reference text within its field limit.')
        for value, limit in ((self.legal_basis, 250), (self.source_url, 1000)):
            if not isinstance(value, str) or len(value) > limit or (require_source and not value.strip()):
                raise ValidationError('Provide nonempty reference text within its field limit.')
        if self.source_url:
            validate_source_url(self.source_url)
        if self.recurrence_kind in ('fixed_day', 'fixed_range'):
            # A leap year validates possible month/day pairs, without deriving a year.
            limit = monthrange(2000, self.month)[1]
            if type(self.day_start) is not int or not 1 <= self.day_start <= limit:
                raise ValidationError('Choose a valid day in this month.')
            if self.recurrence_kind == 'fixed_range':
                if type(self.day_end) is not int or not self.day_start < self.day_end <= limit:
                    raise ValidationError('Choose an end day after the start, in the same month.')
            elif self.day_end is not None:
                raise ValidationError('A fixed day has no end-day field.')
        elif self.day_start is not None or self.day_end is not None:
            raise ValidationError('Descriptive recurrences must not invent exact dates.')

    @property
    def recurrence_rule(self):
        month = month_name[self.month]
        if self.recurrence_kind == 'whole_month':
            return f'Whole month of {month}'
        if self.recurrence_kind == 'third_week':
            return f'Third week of {month}'
        if self.recurrence_kind == 'last_monday':
            return f'Last Monday of {month}'
        if self.recurrence_kind == 'third_thursday':
            return f'Third Thursday of {month}'
        if self.recurrence_kind == 'fixed_range':
            return f'{month} {self.day_start}–{self.day_end}'
        return f'{month} {self.day_start}'


REFERENCE_CATALOGUE = (
    ObservanceReference(1, 'National Autism Consciousness Week', 'third_week',
        'Proclamation No. 711, s. 1996',
        'https://ncda.gov.ph/disability-laws/proclamations/proclamation-no-711/',
        'An annual observance supporting autism awareness and inclusion. The third-week rule is kept descriptive; exact dates depend on the officially confirmed convention.'),
    ObservanceReference(2, 'National Down Syndrome Consciousness Month', 'whole_month',
        'Proclamation No. 157, s. 2002',
        'https://issuances-library.senate.gov.ph/executive-issuance/proclamation-no-157-s-2002',
        'A month-long national observance raising awareness of Down syndrome.'),
    ObservanceReference(3, 'Women with Disabilities Day', 'last_monday',
        'Proclamation No. 744, s. 2004',
        'https://ncda.gov.ph/disability-laws/proclamations/proclamation-no-744/',
        'An annual observance promoting the rights and participation of women with disabilities.'),
    ObservanceReference(4, 'World Autism Awareness Day', 'fixed_day',
        'United Nations General Assembly Resolution 62/139',
        'https://www.un.org/en/observances/autism-day/',
        'A United Nations observance supporting awareness, acceptance and inclusion of autistic people.', day_start=2),
    ObservanceReference(5, 'Global Accessibility Awareness Day', 'third_thursday',
        'Global Accessibility Awareness Day (GAAD) official annual observance',
        'https://accessibility.day/spread-awareness/',
        'An international observance promoting digital accessibility and inclusion for people with disabilities.'),
    ObservanceReference(6, 'National Kidney Month', 'whole_month',
        'Proclamation No. 184, s. 1993',
        'https://ldr.senate.gov.ph/executive-issuance/proclamation-no-184',
        'A health-related observance for kidney health awareness. It is not a PWD-specific observance.', category='health'),
    ObservanceReference(7, 'National Disability Rights Week', 'fixed_range',
        'Proclamation No. 597, s. 2024',
        'https://ncda.gov.ph/declaring-the-period-of-17-to-23-july-of-every-year-as-national-disability-rights-week-proclamation-no-597/',
        'An annual observance promoting the rights and inclusion of persons with disabilities.', day_start=17, day_end=23),
    ObservanceReference(8, 'White Cane Safety Day', 'fixed_day',
        'Republic Act No. 6759',
        'https://ncda.gov.ph/disability-laws/republic-acts/republic-act-6759/',
        'An annual observance promoting recognition of the white cane and respect for blind people.', day_start=1),
    ObservanceReference(9, 'Cerebral Palsy Awareness and Protection Week', 'fixed_range',
        'Proclamation No. 588, s. 2004',
        'https://ncda.gov.ph/disability-laws/proclamations/proclamation-no-588/',
        'An annual observance supporting awareness, rights and participation of people with cerebral palsy.', day_start=16, day_end=22),
    ObservanceReference(10, 'National ADHD Awareness Week', 'third_week',
        'Proclamation No. 472, s. 2003',
        'https://ncda.gov.ph/disability-laws/proclamations/proclamation-no-472/',
        'An annual observance raising awareness of attention deficit/hyperactivity disorder. The third-week rule does not establish exact dates for a particular year.'),
    ObservanceReference(11, 'Deaf Awareness Week', 'fixed_range',
        'Proclamation No. 829, s. 1991',
        'https://ncda.gov.ph/disability-laws/proclamations/proclamation-829/',
        'An annual observance supporting Deaf awareness and inclusion. NCDA uses this current title; the proclamation uses “Deafness Awareness Week”.', day_start=10, day_end=16),
    ObservanceReference(12, 'International Day of Persons with Disabilities in the Philippines', 'fixed_day',
        'Proclamation No. 1157, s. 2006',
        'https://ncda.gov.ph/disability-laws/proclamations/proclamation-no-1157/',
        'An annual observance promoting the rights and participation of persons with disabilities. The proclamation text specifies December 3.', day_start=3),
)


def calendar_months(references=()):
    """Presentation only. Callers must establish visibility before projecting rows."""
    months = [{'number': number, 'name': month_name[number], 'observances': []}
              for number in range(1, 13)]
    for item in references:
        months[item.month - 1]['observances'].append({
            'title': item.title, 'recurrence_rule': item.recurrence_rule,
            'category_label': CATEGORIES[item.category], 'legal_basis': item.legal_basis,
            'source_url': item.source_url, 'description': item.description,
        })
    return months
