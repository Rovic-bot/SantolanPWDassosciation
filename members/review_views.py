from uuid import UUID, uuid4

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods
from accounts.decorators import dashboard_required
from .models import Member
from .review_models import InformationReview
from . import review_services as services


@never_cache
@dashboard_required
@sensitive_post_parameters()
@require_http_methods(['GET', 'HEAD', 'POST'])
def reviews(request, pk):
    actor = services.actor_for(request.user)
    member = get_object_or_404(Member, pk=pk)
    application = None
    if request.GET.get('application'):
        services.actor_for(request.user, application=True)
        try:
            application_id = UUID(request.GET['application'])
        except (ValueError, TypeError):
            raise Http404('The record is unavailable.') from None
        application = get_object_or_404(member.program_applications, pk=application_id)
    form = services.IntakeForm(request.POST if request.method == 'POST' else None,
        initial={'request_key': uuid4(), 'kind': 'evaluation' if application else 'information',
                 'trigger': 'clarification' if application else 'reported_change', 'declaration': 'not_collected'})
    if request.method == 'POST':
        services.actor_for(request.user, write=True, application=application)
        if form.is_valid():
            try:
                record = services.open_review(member.pk, user=request.user, data=request.POST,
                    application_id=application.pk if application else None)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, 'Private concern recorded. Accepted information and program outcomes are unchanged.')
                return redirect('members:review_detail', pk=record.pk)
    records = member.information_reviews.all()
    if not actor.has_perms(['programs.view_program', 'programs.view_programapplication']):
        records = records.filter(application__isnull=True)
    return render(request, 'members/reviews/list.html', {'member': member, 'application': application,
        'form': form, 'page_obj': Paginator(records, 20).get_page(request.GET.get('page'))})


@never_cache
@dashboard_required
@sensitive_post_parameters()
@require_http_methods(['GET', 'HEAD', 'POST'])
def review_detail(request, pk):
    services.actor_for(request.user)
    record = get_object_or_404(InformationReview.objects.select_related('member', 'application'), pk=pk)
    services.actor_for(request.user, application=record.application_id)
    form = services.FindingForm(request.POST if request.method == 'POST' else None,
        initial={'version': record.version, 'state': 'under_review'})
    if request.method == 'POST':
        services.actor_for(request.user, write=True, application=record.application_id)
        if form.is_valid():
            try:
                services.record_findings(record.pk, user=request.user, data=request.POST)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, 'Review history retained. Source corrections still require the authorized workflow.')
                return redirect('members:review_detail', pk=record.pk)
    return render(request, 'members/reviews/detail.html', {'record': record, 'form': form,
        'page_obj': Paginator(record.actions.all(), 20).get_page(request.GET.get('page'))})
