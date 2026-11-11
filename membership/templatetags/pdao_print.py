from django import template

from membership.pdao_printing import print_context

register = template.Library()


@register.inclusion_tag('membership/pdao/source_form.html')
def pdao_source_form(submitted):
    return print_context(submitted)
