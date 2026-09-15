"""Authentication backend.

Users sign in with their email address. Django's default ``ModelBackend`` is not
used because this application has no ``PermissionsMixin``, no staff flag and no
Django admin site: authorisation is answered entirely by the role model in
:mod:`ztech_sales.core.permissions`.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import check_password

from ztech_sales.core.models import User


class EmailBackend(BaseBackend):
    def authenticate(
        self,
        request: Any = None,
        username: str | None = None,
        password: str | None = None,
        **kwargs: Any,
    ) -> User | None:
        email = (username or kwargs.get("email") or "").strip().lower()
        if not email or not password:
            return None
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Run the hasher anyway so that a missing account and a wrong
            # password take a comparable amount of time and the response cannot
            # be used to enumerate valid email addresses.
            User().set_password(password)
            return None

        if not user.check_password(password):
            return None
        if not user.is_active or user.is_locked:
            return None
        return user

    def get_user(self, user_id: Any) -> User | None:
        try:
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError, TypeError):
            return None
        # A deactivated account loses access on its very next request, without
        # waiting for the session to expire.
        return user if user.is_active else None

    def user_can_authenticate(self, user: User) -> bool:
        return bool(user.is_active and not user.is_locked)


def verify_password(raw_password: str, encoded: str) -> bool:
    return check_password(raw_password, encoded)
