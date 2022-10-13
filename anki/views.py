"""
This is anki app's views module.

note: all requests here presume either no auth tokens, or valid JWT
      Bearer Token. Otherwise, the 401 token-related response is
      returned by the DRF middleware.
"""

import random
from time import sleep

from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db.utils import IntegrityError
from django.utils.crypto import get_random_string

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from django.contrib.auth.models import User
from anki.models import Deck, Card, DeckDescription, Stat
from anki.serializers import (UserSerializer,
                              DeckInfoSerializer,
                              DeckSerializer,
                              CardSerializer,
                              StatSerializer)
from anki.validation import (validate_and_normalize_signup_form,
                             validate_and_normalize_deck_stuff)
from anki.errors import messages
from anki.config import (ACCOUNT_VERIFICATION_QUEUE_LIMIT as QUEUE_LIMIT,
                         USER_DECK_LIMIT,
                         USER_CARD_STAT_LIMIT)

from api.settings import JWT_AUTH, SENDER_EMAIL_ADDRESS


class SignUp(APIView):
    """
    Sign up with username, email, and password.

    Endpoint: `api/signup`

    Input: request.data[username, email, password]
    Logic:
        1. Check the number of non-active users, i.e. awaiting
           verification. If >=LIMIT, do not process form and inform
           the user of the fact
        2. Validate form data and return 400 if not valid
        3. Try creating new user object with unique email and username,
           set is_active field to false, inform of EMAIL_CONFLICT or
           UNAME_CONFLICT if failed
        4. Email the provided address with the link
           containing the unique code (inform if could not send)
        5. Return the new user object as response
    """
    def post(self, request: Request) -> Response:
        # 1:
        non_active_users_num = User.objects.filter(is_active=False).count()
        if non_active_users_num >= QUEUE_LIMIT:
            return Response(
                data={
                    'code': 'QUEUE',
                    'message': messages['QUEUE'],
                },
                status=409)
        # 2:
        try:
            data = validate_and_normalize_signup_form(request.data)
        except ValidationError:
            return Response(
                data={
                    'code': 'VALIDATION',
                    'message': messages['VALIDATION'],
                },
                status=400)
        username = data['username']
        email = data['email']
        password = data['password']
        # 3:
        # ensure email is unique:
        if User.objects.filter(email=email).exists():
            return Response(
                data={
                    'code': 'EMAIL_CONFLICT',
                    'message': messages['EMAIL_CONFLICT'],
                },
                status=409)
        # generate the email code for later verification:
        email_code = get_random_string(length=32)
        # try creating the account:
        try:
            new_user = User.objects.create_user(username=username,
                                                email=email,
                                                password=password,
                                                last_name=email_code)
            new_user.is_active = False
            new_user.save()
        except IntegrityError:
            return Response(
                data={
                    'code': 'UNAME_CONFLICT',
                    'message': messages['UNAME_CONFLICT'],
                },
                status=409)
        # 4:
        emailing_succeeded = False
        try:
            success = send_mail(
                'Anki account verification',
                f'Hello,\n\n'
                f'Your email address is being used to '
                f'create an anki account for the user "{username}".\n'
                f'In order to verify the account, follow the link: '
                f'https://anki-webapp.vercel.app/auth/verify/{email_code}.\n'
                f'You have 24hrs until the link expires.\n\n'
                f'Best regards,\n'
                f'Roś',
                SENDER_EMAIL_ADDRESS,
                [email]
            )
            if success == 0:
                raise Exception()
            emailing_succeeded = True
        except Exception as e:
            print(f'Emailing error: {e}')
        # 5:
        serializer = UserSerializer(new_user)
        return Response(
            data={
                'user': serializer.data,
                'code': 'OKAY' if emailing_succeeded else 'MAIL_NOT_SENT',
                'message': (messages['OKAY']
                            if emailing_succeeded else
                            messages['MAIL_NOT_SENT']),
            },
            status=200)


class SignUpVerify(APIView):
    """
    Verify email with the code generated for a user.

    Endpoint: `api/signup-verify?code={code}`

    Input: request.query_params[code]
    Logic:
        1. Validate code: it should be a string of 32 characters
        2. Try finding user by the code
             SUCCESS -> continue
             FAILURE -> 404(user)
        3a. If user's active field is set to true
           return 200("already verified")
        3b. If user's active field is set to false
           set it to true and return 200("verified")
    """
    def get(self, request: Request) -> Response:
        code = request.query_params.get('code')
        # 1:
        if not code or type(code) != str or len(code) != 32:
            return Response(
                data={
                    'code': 'VALIDATION',
                    'message': messages['VALIDATION'],
                },
                status=400)
        # 2:
        try:
            user = User.objects.get(last_name=code)
            if user.is_active:
                # 3a:
                return Response(
                    data={
                        'code': 'VERIFIED_ALREADY',
                        'message': messages['VERIFIED_ALREADY'],
                    },
                    status=200)
            else:
                # 3b:
                user.is_active = True
                user.save()
                return Response(
                    data={
                        'code': 'VERIFIED',
                        'message': messages['VERIFIED'],
                    },
                    status=200)
        except User.DoesNotExist:
            return Response(
                data={
                    'code': 'AV_CODE_NOT_VALID',
                    'message': messages['AV_CODE_NOT_VALID'],
                },
                status=404)


class GetMe(APIView):
    """
    Get the user by the JWT token.

    Endpoint: `api/get-me`

    Input: -
    Logic:
        1. Get claimed identity from the token
        2. Anonymous user -> empty response
        3. Return user object
    """
    def get(self, request: Request) -> Response:
        sleep(2)
        # 1:
        jwt_username = request.user.username
        # 2:
        if not jwt_username:
            return Response(
                data={
                    'code': 'NOT_SIGNED_IN',
                    'message': messages['NOT_SIGNED_IN'],
                },
                status=200)
        # 3:
        user = User.objects.get(username=jwt_username)
        serializer = UserSerializer(user)
        return Response(
            data={
                'user': serializer.data,
                'code': 'SIGNED_IN',
                'message': messages['SIGNED_IN'],
            },
            status=200)


class GetDecks(APIView):
    """
    Get user's decks which are accessible to the requesting user.

    Endpoint: `api/get-decks?username={username}`

    Input: request.query_params[username]
    Logic:
        1. Validate username: it should be a string
        2. Does the {username} user exist ? continue : 404
        3. username <-> jwt ? send all decks : send public decks
           * if JWT_AUTH=False, send all decks
    """
    def get(self, request: Request) -> Response:
        username = request.query_params.get('username')
        # 1:
        if not username or type(username) != str:
            return Response(
                data={
                    'code': 'VALIDATION',
                    'message': messages['VALIDATION'],
                },
                status=400)
        # 2:
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                data={
                    'code': 'USER_NOT_FOUND',
                    'message': messages['USER_NOT_FOUND'],
                },
                status=404)
        # 3:
        jwt_username = request.user.username
        if not JWT_AUTH or username == jwt_username:
            decks = Deck.objects.all().filter(owner=user)
        else:
            decks = (Deck.objects.all().filter(owner=user)
                     .filter(public=True))
        serializer = DeckSerializer(decks, many=True)
        return Response(
            data={
                'decks': serializer.data,
                'code': 'OKAY',
                'message': messages['OKAY'],
            },
            status=200)


class GetDeckInfo(APIView):
    """
    Get deck info of a particular deck.

    Endpoint: `api/get-deck-info?username={username}&deckname={deckname}`

    Input: request.query_params[username, deckname]
    Logic:
        1. Validate username and deckname: both should be strings
        2. Does the {username} user exist ? continue : 404(user)
        3. Does the {deckname} deck exist ? continue : 404(deck)
        4. Is the deck public or JWT_AUTH=False ? send deck info :
                                                  continue
        5. username <-> jwt ? send deck info : 404(deck)
    """
    def get(self, request: Request) -> Response:
        username = request.query_params.get('username')
        deckname = request.query_params.get('deckname')
        # 1:
        if (not username or type(username) != str
                or not deckname or type(deckname) != str):
            return Response(
                data={
                    'code': 'VALIDATION',
                    'message': messages['VALIDATION'],
                },
                status=400)
        # 2:
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                data={
                    'code': 'USER_NOT_FOUND',
                    'message': messages['USER_NOT_FOUND'],
                },
                status=404)
        # 3:
        try:
            deck: Deck = Deck.objects.get(owner=user, name=deckname)
        except Deck.DoesNotExist:
            return Response(
                data={
                    'code': 'DECK_NOT_FOUND',
                    'message': messages['DECK_NOT_FOUND'],
                },
                status=404)
        # 4&5:
        if JWT_AUTH and not deck.public:
            jwt_username = request.user.username
            if username != jwt_username:
                return Response(
                    data={
                        'code': 'DECK_NOT_FOUND',
                        'message': messages['DECK_NOT_FOUND'],
                    },
                    status=404)
        serializer = DeckInfoSerializer(deck)
        return Response(
            data={
                'deckinfo': serializer.data,
                'code': 'OKAY',
                'message': messages['OKAY'],
            },
            status=200)


class GetDeckStats(APIView):
    """
    Get the stats of a particular user on a particular deck.

    Endpoint: `get-deck-stats?username={username}&deckname={deckname}`

    TODO: change the protocol to also include the username of the one
          requesting the stats to enable JWT_AUTH=False tests later

    Input: request.query_params[username, deckname]
    Logic:
        1. Validate username and deckname: both should be strings
        2. no jwt -> no stats (401) (irregardless of JWT_AUTH)
        3. Does the {username} user exist ? continue : 404(user)
        4. Does the {deckname} deck exist ? continue : 404(deck)
        5. Is the deck public ? get the user(jwt) stats : continue
        6. username <-> jwt ? get user(jwt) stats : 404(deck)
    """
    def get(self, request: Request) -> Response:
        username = request.query_params.get('username')
        deckname = request.query_params.get('deckname')
        # 1:
        if (not username or type(username) != str
                or not deckname or type(deckname) != str):
            return Response(
                data={
                    'code': 'VALIDATION',
                    'messages': messages['VALIDATION'],
                },
                status=400)
        # 2:
        jwt_user = request.user
        jwt_username = request.user.username
        if not jwt_username:
            return Response(
                data={
                    'code': 'AUTH_REQUIRED',
                    'message': messages['AUTH_REQUIRED'],
                },
                status=401)
        # 3:
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                data={
                    'code': 'USER_NOT_FOUND',
                    'message': messages['USER_NOT_FOUND'],
                },
                status=404)
        # 4:
        try:
            deck: Deck = Deck.objects.get(owner=user, name=deckname)
        except Deck.DoesNotExist:
            return Response(
                data={
                    'code': 'DECK_NOT_FOUND',
                    'message': messages['DECK_NOT_FOUND'],
                },
                status=404)
        # 5&6:
        if deck.public or username == jwt_username:
            stats = Stat.objects.all().filter(owner=jwt_user)
        else:
            return Response(
                data={
                    'code': 'DECK_NOT_FOUND',
                    'message': messages['DECK_NOT_FOUND'],
                },
                status=404)
        serializer = StatSerializer(stats, many=True)
        return Response(
            data={
                'stats': serializer.data,
                'code': 'OKAY',
                'message': messages['OKAY'],
            },
            status=200)


class GetDeckStuff(APIView):
    """
    Get all the stuff of one owns deck (i.e., name, color,
    public/private status, description, and cards) for update purposes.

    Endpoint: `get-deck-stuff?username={username}&deckname={deckname}`

    # TODO: maybe change logic to enable JWT_AUTH=False tests

    Input: request.query_params[username, deckname]
    Logic:
        1. Validate username and deckname: both should be strings
        2. no jwt -> no stuff (401) (irregardless of JWT_AUTH)
        3. username <-> jwt ? continue : 401 error
        4. Does the {deckname} deck exist ? return stuff : 404(deck)
    """
    def get(self, request: Request) -> Response:
        username = request.query_params.get('username')
        deckname = request.query_params.get('deckname')
        # 1:
        if (not username or type(username) != str
                or not deckname or type(deckname) != str):
            return Response(
                data={
                    'code': 'VALIDATION',
                    'messages': messages['VALIDATION'],
                },
                status=400)
        # 2:
        jwt_username = request.user.username
        if not jwt_username:
            return Response(
                data={
                    'code': 'AUTH_REQUIRED',
                    'message': messages['AUTH_REQUIRED'],
                },
                status=401)
        # 3:
        if username != jwt_username:
            return Response(
                data={
                    'code': 'ACCESS_DENIED',
                    'message': messages['ACCESS_DENIED'],
                },
                status=401)
        # 4:
        user = request.user
        try:
            deck = Deck.objects.get(owner=user, name=deckname)
        except Deck.DoesNotExist:
            return Response(
                data={
                    'code': 'DECK_NOT_FOUND',
                    'message': messages['DECK_NOT_FOUND'],
                },
                status=404)
        cards = Card.objects.filter(deck=deck)
        deck_serializer = DeckInfoSerializer(deck)
        card_serializer = CardSerializer(cards, many=True)
        return Response(
            data={
                'deck': deck_serializer.data,
                'cards': card_serializer.data,
                'code': 'OKAY',
                'message': messages['OKAY'],
            },
            status=200)


class UpdateDeckStuff(APIView):
    """
    Update one owns deck stuff (i.e., name, color,
    public/private status, description, and cards).

    Endpoint: `api/update-deck-stuff?username={username}`

    # TODO: maybe change logic to enable JWT_AUTH=False tests

    Input: request.query_params[username]
                  .data[{
                      deck: dict
                      cards: dict[]
                  }]
    Logic:
        1. Validate username: it should be a string
        2. Block attempts to update user data by anyone other than them
           (irregardless of JWT_AUTH)
        3. Deny non-active users this action
        4. Validate the received deck stuff
        5. Process and modify the database objects.
           If the number of decks is max, don't allow creating new ones
        6. Return the updated deck stuff
    """
    def post(self, request: Request) -> Response:
        try:
            username = request.query_params.get('username')
            # 1:
            if not username or type(username) != str:
                return Response(
                    data={
                        'code': 'VALIDATION',
                        'messages': messages['VALIDATION'],
                    },
                    status=400)
            # 2:
            jwt_username = request.user.username
            # apprehend non-auth'd users:
            if not jwt_username:
                return Response(
                    data={
                        'code': 'AUTH_REQUIRED',
                        'message': messages['AUTH_REQUIRED'],
                    },
                    status=401)
            # apprehend non-owner users:
            if username != jwt_username:
                return Response(
                    data={
                        'code': 'ACCESS_DENIED',
                        'message': messages['ACCESS_DENIED'],
                    },
                    status=401)
            # 3:
            user = request.user
            if not user.is_active:
                return Response(
                    data={
                        'code': 'VERIFICATION_REQUIRED',
                        'message': messages['VERIFICATION_REQUIRED'],
                    },
                    status=401)
            # 4:
            try:
                data = validate_and_normalize_deck_stuff(request.data)
            except ValidationError:
                return Response(
                    data={
                        'code': 'VALIDATION',
                        'messages': messages['VALIDATION'],
                    },
                    status=400)
            # 5:
            deckinfo = data.get('deck')
            cards = data.get('cards')
            # update deck:
            try:
                deck = Deck.objects.get(owner=user, pk=deckinfo['id'])
                deck.name = deckinfo['name']
                deck.color = deckinfo['color']
                deck.public = deckinfo['public']
            except Deck.DoesNotExist:
                deck_number = Deck.objects.filter(owner=user).count()
                if deck_number >= USER_DECK_LIMIT:
                    return Response(
                        data={
                            'code': 'TOO_MUCH_DATA',
                            'message': messages['TOO_MUCH_DATA'],
                        },
                        status=400)
                deck = Deck(name=deckinfo['name'], color=deckinfo['color'],
                            public=deckinfo['public'], owner=user)
            deck.save()
            # update description:
            try:
                description = DeckDescription.objects.get(deck=deck)
                description.description = deckinfo['description']
            except DeckDescription.DoesNotExist:
                description = DeckDescription(description=deckinfo['description'],
                                              deck=deck)
            description.save()
            # update cards:
            # A: remove cards with ids not present in request.data.cards
            request_cards_ids = [card['id'] for card in cards]
            db_cards = Card.objects.filter(deck=deck)
            for db_card in db_cards:
                if db_card.pk not in request_cards_ids:
                    db_card.delete()
            # B: update the received cards, create if id not present
            for card in cards:
                try:
                    card_in_db = Card.objects.get(pk=card['id'])
                    card_in_db.question = card['question']
                    card_in_db.answer = card['answer']
                except Card.DoesNotExist:
                    card_in_db = Card(question=card['question'],
                                      answer=card['answer'],
                                      deck=deck)
                card_in_db.save()
            # 6:
            deck = Deck.objects.get(name=deckinfo['name'], owner=user)
            cards = Card.objects.filter(deck=deck)
            deck_serializer = DeckInfoSerializer(deck)
            card_serializer = CardSerializer(cards, many=True)
            return Response(
                data={
                    'deck': deck_serializer.data,
                    'cards': card_serializer.data,
                    'code': 'OKAY',
                    'message': messages['OKAY'],
                },
                status=200)
        except Exception as e:
            print(e)


class RemoveDeck(APIView):
    """
    Remove a deck of a particular name of a particular user.

    Endpoint: `remove-deck/`

    Input: request.data[{
                      username: str
                      deckname: str
                  }]
    Logic:
        1. Validate username and deckname: both should be strings
        2. If JWT_AUTH=True, prevent users removing others' decks (401)
        3. Deny non-active users this action
        4. Does the {username} user exist ? continue : 404(user)
        5. Does the {deckname} deck exist ? continue : 404(deck)
        6. Remove the {deckname} deck of the {username} user
    """
    def post(self, request: Request) -> Response:
        username = request.data.get('username')
        deckname = request.data.get('deckname')
        # 1:
        if (not username or type(username) != str or
                not deckname or type(deckname) != str):
            return Response(
                data={
                    'code': 'VALIDATION',
                    'message': messages['VALIDATION'],
                },
                status=400)
        # 2:
        jwt_username = request.user.username
        if JWT_AUTH and not jwt_username:
            return Response(
                data={
                    'code': 'AUTH_REQUIRED',
                    'message': messages['AUTH_REQUIRED'],
                },
                status=401)
        if JWT_AUTH and username != jwt_username:
            return Response(
                data={
                    'code': 'ACCESS_DENIED',
                    'message': messages['ACCESS_DENIED'],
                },
                status=401)
        # 3:
        if not request.user.is_active:
            return Response(
                data={
                    'code': 'VERIFICATION_REQUIRED',
                    'message': messages['VERIFICATION_REQUIRED'],
                },
                status=401)
        # 4:
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                data={
                    'code': 'USER_NOT_FOUND',
                    'message': messages['USER_NOT_FOUND'],
                },
                status=404)
        # 5:
        try:
            deck = Deck.objects.get(owner=user, name=deckname)
        except Deck.DoesNotExist:
            return Response(
                data={
                    'code': 'DECK_NOT_FOUND',
                    'message': messages['DECK_NOT_FOUND'],
                },
                status=404)
        # 6:
        deck.delete()
        return Response(
            data={
                'code': 'OKAY',
                'message': messages['OKAY'],
            },
            status=200)


class CreateDeck(APIView):
    """
    Create a new deck with unique name for a particular user.

    Endpoint: `create-deck/`

    Input: request.data[{
                      username: str
                  }]
    Logic:
        1. Validate username: it should be a string
        2. If JWT_AUTH=True, prevent users creating decks
           for others (401)
        3. Deny non-active users this action
        4. Does the {username} user exist ? continue : 404(user)
        5. Create a new {random_name} deck for the {username} user
           and return it in the response
    """
    def post(self, request: Request) -> Response:
        username = request.data.get('username')
        # 1:
        if not username or type(username) != str:
            return Response(
                data={
                    'code': 'VALIDATION',
                    'message': messages['VALIDATION'],
                },
                status=400)
        # 2:
        jwt_username = request.user.username
        if JWT_AUTH and not jwt_username:
            return Response(
                data={
                    'code': 'AUTH_REQUIRED',
                    'message': messages['AUTH_REQUIRED'],
                },
                status=401)
        if JWT_AUTH and username != jwt_username:
            return Response(
                data={
                    'code': 'ACCESS_DENIED',
                    'message': messages['ACCESS_DENIED'],
                },
                status=401)
        # 3:
        if not request.user.is_active:
            return Response(
                data={
                    'code': 'VERIFICATION_REQUIRED',
                    'message': messages['VERIFICATION_REQUIRED'],
                },
                status=401)
        # 4:
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                data={
                    'code': 'USER_NOT_FOUND',
                    'message': messages['USER_NOT_FOUND'],
                },
                status=404)
        # 5:
        # ensure there are not too much user decks in the database:
        deck_number = Deck.objects.filter(owner=user).count()
        if deck_number >= USER_DECK_LIMIT:
            return Response(
                data={
                    'code': 'TOO_MUCH_DATA',
                    'message': messages['TOO_MUCH_DATA'],
                },
                status=400)
        # create a new deck with unique name:
        index = 1
        while index < USER_DECK_LIMIT:
            try:
                deck = Deck(name=f'New Deck {index}',
                            color='#6a6a6a',
                            public=False, owner=user)
                deck.save()
                break
            except IntegrityError:
                index += 1
        else:
            return Response(
                data={
                    'code': 'DEV_MESSED_UP',
                    'message': messages['DEV_MESSED_UP'],
                },
                status=500)
        description = DeckDescription(description='No description yet.',
                                      deck=deck)
        description.save()
        card = Card(question='Is this deck empty?',
                    answer='It is :)',
                    deck=deck)
        card.save()
        serializer = DeckSerializer(deck)
        return Response(
            data={
                'decks': [serializer.data],
                'code': 'OKAY',
                'message': messages['OKAY'],
            },
            status=200)


class PullNextCard(APIView):
    """
    Get a not-exactly-random card from a particular deck.
    To clarify: "not-exactly-random" means the next card that
    the backend find appropriate to give to a user.
    NOTE: it IS random for now :)

    Basically the logic of this view is the biggest pain in the ass
    of the whole app.

    Endpoint: `pull-next-card?deck_owner_username={username}&deckname={deckname}`

    # TODO: maybe change logic to enable JWT_AUTH=False tests

    Input: request.query_params[username, deckname]
    Logic:
        1. Validate username and deckname: both should be strings
        2. no jwt -> no stuff (401) (irregardless of JWT_AUTH)
        3. Does the {username} user exist ? continue : 404(user)
        4. Does the {deckname} deck exist ? continue : 404(deck)
        5. Check if deck visibility allows the requesting party to pull
           cards
        6. [tmp] Get RANDOM card from the deck
    """
    def get(self, request: Request) -> Response:
        username = request.query_params.get('deck_owner_username')
        deckname = request.query_params.get('deckname')
        # 1:
        if (not username or type(username) != str or
                not deckname or type(deckname) != str):
            return Response(
                data={
                    'code': 'VALIDATION',
                    'message': messages['VALIDATION'],
                },
                status=401)
        # 2:
        jwt_username = request.user.username
        if not jwt_username:
            return Response(
                data={
                    'code': 'AUTH_REQUIRED',
                    'message': messages['AUTH_REQUIRED'],
                },
                status=401)
        # 3:
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                data={
                    'code': 'USER_NOT_FOUND',
                    'message': messages['USER_NOT_FOUND'],
                },
                status=404)
        # 4:
        try:
            deck = Deck.objects.get(owner=user, name=deckname)
        except Deck.DoesNotExist:
            return Response(
                data={
                    'code': 'DECK_NOT_FOUND',
                    'message': messages['DECK_NOT_FOUND'],
                },
                status=404)
        # 5:
        if jwt_username != username and not deck.public:
            return Response(
                data={
                    'code': 'DECK_NOT_FOUND',
                    'message': messages['DECK_NOT_FOUND'],
                },
                status=404)
        # 6:
        cards = list(Card.objects.filter(deck=deck))
        if not cards:
            return Response(
                data={
                    'code': 'NO_CARDS_IN_DECK',
                    'message': messages['NO_CARDS_IN_DECK'],
                },
                status=200)
        else:
            random_card = random.choice(cards)
            card_serializer = CardSerializer(random_card)
            return Response(
                data={
                    'card': card_serializer.data,
                    'code': 'OKAY',
                    'message': messages['OKAY'],
                },
                status=200)


class PostFeedback(APIView):
    """
    Post feedback on a particular card of a particular deck as a
    particular user.

    Endpoint: `post-feedback`

    TODO: change the protocol to also include the username of the one
          leaving the feedback to enable JWT_AUTH=False tests later

    Input: request.data[{
                      deck_owner_username: string
                      deckname: string
                      card_id: number
                      feedback: boolean
                  }]
    Logic:
        1. Validate request data
        2. no jwt -> no posting feedback (401) (irregardless of
                                                JWT_AUTH)
        3. Deny non-active users this action
        4. Does the {deck_owner_username} user exist ? continue
                                                     : 404(user)
        5. Does the {deckname} deck exist ? continue : 404(deck)
        6. Does the {card_id} card exist ? continue : 404(card)
        7. Check if deck visibility allows the requesting party to post
           feedback
        8. Create new Stat(jwt.user, deck) with specified feedback
           If the number of user stats on card is max, delete
           the oldest one
    """
    def post(self, request: Request) -> Response:
        # 1:
        data = request.data
        if (type(data.get('deck_owner_username')) != str
                or type(data.get('deckname')) != str
                or type(data.get('card_id')) != int
                or type(data.get('feedback')) != bool):
            return Response(
                data={
                    'code': 'VALIDATION',
                    'message': messages['VALIDATION'],
                },
                status=400)
        deck_owner_username = data['deck_owner_username']
        deckname = data['deckname']
        card_id = data['card_id']
        feedback = data['feedback']
        # 2:
        jwt_username = request.user.username
        if not jwt_username:
            return Response(
                data={
                    'code': 'AUTH_REQUIRED',
                    'message': messages['AUTH_REQUIRED'],
                },
                status=401)
        jwt_user = request.user
        # 3:
        if not jwt_user.is_active:
            return Response(
                data={
                    'code': 'VERIFICATION_REQUIRED',
                    'message': messages['VERIFICATION_REQUIRED'],
                },
                status=401)
        # 4:
        try:
            user = User.objects.get(username=deck_owner_username)
        except User.DoesNotExist:
            return Response(
                data={
                    'code': 'USER_NOT_FOUND',
                    'message': messages['USER_NOT_FOUND'],
                },
                status=404)
        # 5:
        try:
            deck = Deck.objects.get(owner=user, name=deckname)
        except Deck.DoesNotExist:
            return Response(
                data={
                    'code': 'DECK_NOT_FOUND',
                    'message': messages['DECK_NOT_FOUND'],
                },
                status=404)
        # 6:
        if jwt_username != deck_owner_username and not deck.public:
            return Response(
                data={
                    'code': 'DECK_NOT_FOUND',
                    'message': messages['DECK_NOT_FOUND'],
                },
                status=404)
        # 7:
        try:
            card = Card.objects.get(deck=deck, pk=card_id)
        except Deck.DoesNotExist:
            return Response(
                data={
                    'code': 'CARD_NOT_FOUND',
                    'message': messages['CARD_NOT_FOUND'],
                },
                status=404)
        # 8:
        stat = Stat(feedback=feedback,
                    owner=jwt_user,
                    card=card)
        stat.save()
        user_card_stat_num = Stat.objects.filter(owner=jwt_user,
                                                 card=card).count()
        if user_card_stat_num > USER_CARD_STAT_LIMIT:
            stat = Stat.objects.filter(owner=jwt_user,
                                       card=card).earliest()
            stat.delete()
        return Response(
            data={
                'code': 'OKAY',
                'message': messages['OKAY'],
            },
            status=200)


# TMP:
class TmpCVFeedback(APIView):
    """
    Tmp
    """
    def post(self, request: Request) -> Response:
        data = request.data
        msg = data['message']
        try:
            success = send_mail(
                'CV feedback',
                msg,
                SENDER_EMAIL_ADDRESS,
                ['krastsislau@gmail.com']
            )
            if success == 0:
                raise Exception()
        except Exception as e:
            return Response(status=400)
        return Response()
