"""
This module is dedicated to validating and normalizing
data received from the client.
"""

from django.core.exceptions import ValidationError
from django.core.validators import validate_email


def validate_and_normalize_signup_form(data: dict) -> dict:
    """
    This is essentially doing client validation again. If invalid,
    400 response should be returned. Also, this includes removing
    trailing whitespaces and stuff.

    Input: request.data dict.
    Output: normalized dict.

    If invalid, throw ValidationError.
    """
    # 1: required keys check:
    try:
        username = data['username']
        email = data['email']
        password = data['password']
    except KeyError:
        raise ValidationError
    # 2: string length check:
    try:
        assert len(username) <= 20
        assert len(email) <= 20
        assert len(password) <= 20
    except AssertionError:
        raise ValidationError
    # 3: email validation:
    validate_email(email)

    return {
        'username': username,
        'email': email,
        'password': password,
    }


def validate_and_normalize_deck_stuff(deck_stuff: dict) -> dict:
    """
    Input: deck_stuff dict.
    Output: normalized dict.

    If invalid, throw ValidationError.
    """
    return deck_stuff
