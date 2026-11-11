from django import template

register = template.Library()


@register.inclusion_tag('admin/directory_pagination.html')
def directory_pagination(cl):
    page = cl.paginator.get_page(cl.page_num)
    return {'cl': cl, 'page': page,
        'previous_url': cl.get_query_string({'p': page.previous_page_number()}) if page.has_previous() else '',
        'next_url': cl.get_query_string({'p': page.next_page_number()}) if page.has_next() else '',
        'pages': [{'number': number, 'url': cl.get_query_string({'p': number})
            if number != cl.paginator.ELLIPSIS else ''}
            for number in cl.paginator.get_elided_page_range(page.number, on_each_side=1, on_ends=1)]}
