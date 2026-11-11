"""Explicit result publication for disposable assistance workflow fixtures."""
def publish_selection(program, user):
    from .models import Announcement
    from .results import prepare_results, publish_results
    item = Announcement.objects.filter(program=program).first()
    item = prepare_results(program.pk, user=user, version=item.version if item else 0,
        reason='SYNTHETIC selected-member publication before actual assistance.', recorded=True,
        selection_reason='Synthetic members meet the program requirements and recorded selection criteria.')
    return publish_results(item.pk, user=user, version=item.version)
