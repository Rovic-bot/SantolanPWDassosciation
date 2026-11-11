"""Deadline presentation after the public application-readiness checks."""
from datetime import timedelta


CLOSING_SOON_WINDOW = timedelta(hours=1)


def prepare_registration_notice(program, *, at):
    program.registration_notice_starts_at = None
    program.registration_closing_soon = False
    program.registration_notice_at = at
    closes_at = program.registration_closes_at
    if program.public_application_status != 'open' or not closes_at or closes_at <= at:
        return
    program.registration_notice_starts_at = closes_at - CLOSING_SOON_WINDOW
    program.registration_closing_soon = program.registration_notice_starts_at <= at
