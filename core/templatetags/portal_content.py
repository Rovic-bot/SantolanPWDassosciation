import re

from django import template
from django.urls import reverse
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def title_initials(value):
    return ''.join(word[0] for word in re.findall(r'[^\W_]+', str(value))[:2]).upper() or '?'


class PortalNode(template.Node):
    def __init__(self, field, body, kind):
        self.field, self.body, self.kind = field, body, kind

    def render(self, context):
        from core.portal_editor import state_for
        request = context.get('request')
        default = self.body.render(context)
        if not request:
            return default
        state = state_for(request)
        if not state['key']:
            return default
        from core.portal_fields import FIELDS
        name = self.field.resolve(context)
        definition = FIELDS[state['key']].get(name)
        if not definition:
            return default
        value = state['values'].get(name)
        if self.kind == 'picture':
            html = default
            if isinstance(value, dict) and value.get('token'):
                url = reverse('core:portal_image', args=[state['key'], name, value['token']])
                if state['preview']:
                    url += '?preview=1'
                if re.search(r'<img\b', html):
                    html = re.sub(r'<source\b[^>]*>', '', html)
                    html = re.sub(r'(<img\b[^>]*\bsrc=)["\'][^"\']*["\']', lambda m: m[1] + '"' + str(escape(url)) + '"', html, count=1)
                else:
                    html = str(format_html('<figure class="portal-custom-picture"><img src="{}" alt="{}" width="1080" height="720"></figure>', url, definition['label']))
            alt = state['values'].get(name + '_alt')
            if isinstance(alt, str):
                html = re.sub(r'\balt=["\'][^"\']*["\']', lambda m: 'alt="' + str(escape(alt)) + '"', html, count=1)
            if state['preview']:
                return format_html('<div class="portal-edit-picture" data-portal-picture="{}" data-portal-label="{}">{}<template data-portal-original>{}</template></div>', name, definition['label'], mark_safe(html), mark_safe(default))
            return mark_safe(html)
        html = escape(value) if isinstance(value, str) else default
        tag = 'div' if self.kind == 'block' else 'span'
        if state['preview']:
            return format_html('<{0} data-portal-field="{1}" data-portal-label="{2}" class="portal-edit-copy">{3}</{0}>', tag, name, definition['label'], mark_safe(html))
        if isinstance(value, str):
            return format_html('<{0} class="portal-saved-copy">{1}</{0}>', tag, value)
        return default


def parse_portal(parser, token, kind):
    bits = token.split_contents()
    if len(bits) != 2:
        raise template.TemplateSyntaxError('Portal fields need a field name.')
    body = parser.parse(('end' + bits[0],))
    parser.delete_first_token()
    return PortalNode(parser.compile_filter(bits[1]), body, kind)


@register.tag
def portal_text(parser, token):
    return parse_portal(parser, token, 'text')


@register.tag
def portal_block(parser, token):
    return parse_portal(parser, token, 'block')


@register.tag
def portal_picture(parser, token):
    return parse_portal(parser, token, 'picture')
