from django import template
from core.reference_services import display_reference

register = template.Library()


@register.filter
def short_reference(value, kind):
    return display_reference(kind, value)
