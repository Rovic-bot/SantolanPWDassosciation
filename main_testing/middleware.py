from django.conf import settings
from django.http import HttpResponseBadRequest


def environment(request):
    return {'main_testing_environment': True}


class EnvironmentMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, 'MAIN_TESTING', False):
            return HttpResponseBadRequest('Dedicated fictional settings required.')
        response = self.get_response(request)
        response['X-Santolan-Environment'] = 'MAIN-FICTIONAL-TESTING'
        return response
