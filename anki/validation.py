"""
This module is dedicated to validating and normalizing
data received from the client.
"""

import re
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

# TODO: probably the better way is to use the "schema" library


def validate_and_normalize_signup_form(data: dict) -> dict:
    """
    This is essentially doing client validation again. If invalid,
    400 response should be returned. Also, this includes removing
    trailing whitespaces and stuff, i.e. normalizing.

    Input: request.data dict.
    Output: normalized dict.

    If invalid, throw ValidationError.
    """
    # 1: required keys check:
    if not ({'username', 'email', 'password'} <= data.keys()):
        raise ValidationError('schema')
    username = data['username']
    email = data['email']
    password = data['password']
    # 2: type check
    if type(username) != str or type(email) != str or type(password) != str:
        raise ValidationError('types')
    # 3: string length check:
    if 1 > len(username) > 30 or len(email) > 30 or len(password) > 30:
        raise ValidationError('length')
    # 4: username check:
    if not re.match("^[a-zA-Z0-9_.-]+$", username):
        raise ValidationError('username')
    # 5: email validation:
    try:
        validate_email(email)
    except ValidationError:
        raise ValidationError('email')
    # 6: password check:
    if not re.fullmatch(r'[A-Za-z0-9!@#$%^&*()\-_+=]{8,}', password):
        raise ValidationError('password')
    return {
        'username': username,
        'email': email,
        'password': password,
    }


def validate_and_normalize_deck_stuff(data: dict) -> dict:
    """
    Input: request.data dict.
    Output: normalized dict.

    If invalid, throw ValidationError.
    """
    # 1: required keys and type checks:
    # 0-depth:
    if not ({'deck', 'cards'} <= data.keys()):
        raise ValidationError('schema')
    deckinfo = data['deck']
    cards = data['cards']
    if type(deckinfo) != dict or type(cards) != list:
        raise ValidationError('types')
    # 1-depth:
    if not ({'id', 'name', 'color', 'public',
             'description'} <= deckinfo.keys()):
        raise ValidationError('deck schema')
    if (type(deckinfo['id']) != int or type(deckinfo['name']) != str or
        type(deckinfo['color']) != str or type(deckinfo['public']) != bool or
            type(deckinfo['description']) != str):
        raise ValidationError('deck types')
    for card in cards:
        if not ({'id', 'question', 'answer'} <= card.keys()):
            raise ValidationError('card schema')
        if (type(card['id']) != int or type(card['question']) != str or
                type(card['answer']) != str):
            raise ValidationError('card types')
    # 2: length limit checks (tmp)
    # deckinfo:
    if (1 > len(deckinfo['name']) > 16 or len(deckinfo['color']) != 7 or
            len(deckinfo['description']) > 2500):
        raise ValidationError('deck size')
    # cards:
    if len(cards) > 100:
        raise ValidationError('card number')
    for card in cards:
        if len(card['question']) > 200 or len(card['answer']) > 200:
            raise ValidationError('card size')

    return data
