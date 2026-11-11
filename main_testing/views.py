from django.shortcuts import render
from accounts.decorators import dashboard_required
from programs.models import Program
from members.models import Member
from programs.models import ProgramApplication
from assistance.models import AssistanceRelease
from announcements.models import Announcement


@dashboard_required
def explore(request):
    return render(request, 'main_testing/explore.html', {
        'labs': Program.objects.filter(name__startswith='EWAF Lab').order_by('name'),
        'counts': {'Members': Member.objects.count(), 'Programs': Program.objects.count(),
                   'Applications': ProgramApplication.objects.count(), 'Announcements': Announcement.objects.count(),
                   'Confirmed receipts': AssistanceRelease.objects.successful().count()},
    })
