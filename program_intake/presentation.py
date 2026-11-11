def update_review_context(context, application, case):
    from .sources import configured, uses_sources
    configuration = configured(application.program)
    context['automatic_sources'] = uses_sources(configuration)
    if context['automatic_sources'] and not configuration.policy['eligibility']:
        context.update(qualification_status='Not required', qualification_form=None,
                       additional_requirements_not_applicable=True)
        context['eligibility_checks'] = [row for row in context['eligibility_checks'] if row['key'] != 'qualification']
        context['eligibility_summary'] = [(label, status) for label, status in context['eligibility_summary']
                                         if label != 'Program fit and required consent']
        if case and case.eligibility_id == 'eligible' and all(status not in ('Needs review', 'Does not match', 'Not met')
                for label, status in context['eligibility_summary']):
            context.update(review_result=case.eligibility_label, review_code='eligible',
                review_explanation='Recorded eligible. EWAF source verification remains a separate required review.')
    return context
