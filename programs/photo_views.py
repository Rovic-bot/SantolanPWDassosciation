from django.contrib import messages
from ewaf.access_invalidation import private_access_writer
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe
from accounts.decorators import dashboard_required
from core.permissions import require_workspace_permissions
from .forms import PhotoReviewForm, CorrectionForm
from .models import ProgramApplication, ApplicationPhoto
from .services import record_log
from .workflow import PHOTO_VIEW, CONFIGURED_EVIDENCE, review_photo, correct_application


@never_cache
@dashboard_required
@require_safe
def queue(request):
    require_workspace_permissions(request.user, *PHOTO_VIEW)
    items = ProgramApplication.objects.select_related('program', 'member', 'current_photo').filter(
        status__in=['PENDING_PHOTO_VERIFICATION', 'NEEDS_INFORMATION', 'PHOTO_VERIFIED', 'ELIGIBILITY_REVIEW']).exclude(
        current_photo__isnull=True, source_snapshot__has_key='evidence_policy',
        source_snapshot__evidence_policy=CONFIGURED_EVIDENCE)
    query = request.GET.get('q', '').strip()[:200]
    if query:
        from core.reference_services import filter_reference
        items = filter_reference(items, 'program', query,
            Q(public_reference__icontains=query) | Q(member__control_number__icontains=query))
    return render(request, 'programs/photo_queue.html', {'page_obj': Paginator(items, 20).get_page(request.GET.get('page')), 'query': query})


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def review(request, reference):
    require_workspace_permissions(request.user, *PHOTO_VIEW, 'programs.review_applicationphoto')
    application = get_object_or_404(ProgramApplication.objects.select_related('program', 'member', 'current_photo'), pk=reference)
    form = PhotoReviewForm(request.POST if request.method == 'POST' else None,
        initial={'version': application.version, 'photo_id': application.current_photo_id})
    if request.method == 'POST' and form.is_valid():
        try:
            review_photo(reference, user=request.user, data=request.POST, address=request.META.get('REMOTE_ADDR'))
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, 'Manual Photo Verification recorded. Eligibility and selection are separate reviews.')
            return redirect('programs:photo_review', reference=reference)
    return render(request, 'programs/photo_review.html', {'application': application, 'form': form,
        'reviews': application.current_photo.reviews.all() if application.current_photo_id else [], 'photos': application.photos.all().order_by('-uploaded_at')})


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def correction(request, reference):
    require_workspace_permissions(request.user, *PHOTO_VIEW, 'programs.resubmit_applicationphoto', 'programs.view_programdocument')
    application = get_object_or_404(ProgramApplication.objects.select_related('program', 'member', 'current_photo'), pk=reference)
    form = CorrectionForm(request.POST if request.method == 'POST' else None, request.FILES or None, application=application)
    if request.method == 'POST':
        if getattr(request, 'upload_limit_exceeded', False):
            form.add_error(None, 'The combined uploads exceed the upload limit.')
        elif form.is_valid():
            try:
                correct_application(reference, user=request.user, data=request.POST, files=request.FILES, address=request.META.get('REMOTE_ADDR'))
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, 'Help Desk correction saved. The reference and earlier evidence are retained; required reviews must be completed again.')
                if request.GET.get('return') == 'applicant':
                    from django.urls import reverse
                    return redirect(reverse('programs:application_detail', args=[application.program_id, reference]) + '#documents')
                return redirect('programs:photo_review', reference=reference) if request.user.has_perm('programs.review_applicationphoto') else redirect('programs:application_detail', pk=application.program_id, reference=reference)
    return render(request, 'programs/correction.html', {'application': application, 'form': form})


@never_cache
@dashboard_required
@require_safe
@private_access_writer('photo_viewed')
def photo(request, reference, photo_id):
    require_workspace_permissions(request.user, *PHOTO_VIEW)
    evidence = get_object_or_404(ApplicationPhoto.objects.select_related('application__program'), pk=photo_id, application_id=reference)
    try:
        source = evidence.file.open('rb')
    except OSError:
        raise Http404('Private photo unavailable.')
    try:
        record_log(evidence.application.program, 'photo_viewed', 'Authorized private calendar-photo access.', user=request.user,
            application=evidence.application, changes={'photo': {'before': None, 'after': str(evidence.pk)}}, address=request.META.get('REMOTE_ADDR'))
    except Exception:
        source.close()
        raise
    response = FileResponse(source, content_type='image/png', filename='calendar-photo.png')
    response['Content-Security-Policy'] = "sandbox; default-src 'none'"
    response['Referrer-Policy'] = 'no-referrer'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'no-store, private'
    return response
