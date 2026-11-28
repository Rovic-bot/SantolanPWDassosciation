from django.db import IntegrityError
from django.test import SimpleTestCase

from core.database_errors import is_unique_violation


class DuplicateDatabaseErrorTests(SimpleTestCase):
    def test_mysql_duplicate_key_is_recognized(self):
        self.assertTrue(is_unique_violation(IntegrityError(1062, 'Synthetic duplicate')))

    def test_postgresql_duplicate_key_is_recognized_from_driver_code(self):
        for attribute in ('sqlstate', 'pgcode'):
            with self.subTest(driver_attribute=attribute):
                cause = Exception('Synthetic duplicate')
                setattr(cause, attribute, '23505')
                error = IntegrityError('Synthetic duplicate')
                error.__cause__ = cause
                self.assertTrue(is_unique_violation(error))

    def test_foreign_key_and_other_integrity_failures_are_not_duplicates(self):
        for state in ('23503', '23502', '23514', None):
            with self.subTest(sqlstate=state):
                cause = Exception('Synthetic integrity failure')
                cause.sqlstate = state
                error = IntegrityError('Synthetic integrity failure')
                error.__cause__ = cause
                self.assertFalse(is_unique_violation(error))
        self.assertFalse(is_unique_violation(IntegrityError(1452, 'Synthetic foreign key')))
        self.assertFalse(is_unique_violation(IntegrityError()))
        self.assertFalse(is_unique_violation(ValueError(1062)))
