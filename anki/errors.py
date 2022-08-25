"""
This module contains the error codes and messages for the views.

TODO: change this into a dict of responses instead, or functions
      returning responses (do that in "Code optimization" PR).
"""


messages = {
    # Default message. It means that whatever is being done, is done:
    'OKAY': 'All good.',
    # Universal messages:
    'AUTH_REQUIRED': 'You should be signed in to access resource.',
    'VERIFICATION_REQUIRED': 'You should be a verified user to '
                             'access resource.',
    'ACCESS_DENIED': 'You do not have access to resource.',
    'VALIDATION': 'Validation error. '
                  'The request data does not follow the schema '
                  'shared between client and server. '
                  'Error reported.',
    'USER_NOT_FOUND': 'User with such username is not found.',
    'DECK_NOT_FOUND': 'Deck with such name is not found.',
    # Sign up and account verification messages:
    'QUEUE': 'Cannot create account. '
             'The queue of accounts pending verification is full. '
             'Try again later.',
    'EMAIL_CONFLICT': 'Cannot create account. '
                      'An account with such email already exists.',
    'UNAME_CONFLICT': 'Cannot create account. '
                      'An account with such username already exists.',
    'MAIL_NOT_SENT': 'Account created, '
                     'but failed to send verification email. '
                     'Try requesting to re-send.',
    'VERIFIED': 'Account verified successfully.',
    'VERIFIED_ALREADY': 'Account is already verified.',
    'AV_CODE_NOT_VALID': 'Account verification code is not valid '
                         'for any account.',
    # Messages for when getting the current user (get-me):
    'NOT_SIGNED_IN': 'You are not signed in.',
    'SIGNED_IN': 'You are signed in.',
    # Messages for when changing database data:
    'TOO_MUCH_DATA': 'Cannot create new data in the database. '
                     'Too many instances of a model exist already.',
    # Messages for train mode:
    'NO_CARDS_IN_DECK': 'There are no cards in deck.',
    'CARD_NOT_FOUND': 'Card with such id is not found.',
    # Other messages:
    'DEV_MESSED_UP': 'Somewhat unexpected behavior occurred, big time. '
                     'Error reported.',
}
