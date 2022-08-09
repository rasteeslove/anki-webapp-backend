"""
This is anki app's views module.

note: all requests here presume either no auth tokens, or valid JWT
      Bearer Token. Otherwise, the 401 token-related response is
      returned by the DRF middleware.
"""

import random

from django.core.exceptions import ValidationError
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

from api.settings import JWT_AUTH

# TODO: consider different error response codes
# TODO: dont allow non-active users to do much in the app
#       bc they need to verify email first
# TODO: add meaningful messages to all responses


class SignUp(APIView):
    """
    Sign up with username, email, and password.

    Endpoint: `api/signup`

    Input: request.data[username, email, password]
    Logic:
        1. Validate form data and return 400 if not valid
        2. Try creating new user object, set active field to false
        3. Email the provided address with the link
           containing the unique code
        4. Return the new user object as response
    """
    def post(self, request: Request) -> Response:
        # 1:
        try:
            data = validate_and_normalize_signup_form(request.data)
        except ValidationError as e:
            print(e)   # TODO: differentiate Response by the message
            return Response(
                data={
                    'message': 'validation failed'
                },
                status=400
            )
        username = data['username']
        email = data['email']
        password = data['password']
        # 2:
        # ensure email is unique:
        if User.objects.filter(email=email).exists():
            return Response(
                data={
                    'message': 'couldn\'t create new user. '
                               'email not unique'
                },
                status=409)
        email_code = get_random_string(length=32)
        try:
            new_user = User.objects.create_user(username=username,
                                                email=email,
                                                password=password,
                                                last_name=email_code)
            new_user.active = False
            new_user.save()
        except IntegrityError:
            return Response(
                data={
                    'message': 'couldn\'t create new user. '
                               'username not unique'
                },
                status=409)
        # 3:
        # TODO: use AWS SES (should be done in the "API safety" PR)
        #       alongside the limits on database objects, times to
        #       live, and regular object cleaning
        # 4:
        # TODO: don't return email code (important)
        serializer = UserSerializer(new_user)
        return Response(serializer.data)


class SignUpVerify(APIView):
    """
    Verify email with the code generated for a user.

    Endpoint: `api/signup-verify?code={code}`

    Input: request.query_params[code]
    Logic:
        1. Try finding user by the code
             SUCCESS -> continue
             FAILURE -> 404(user)
        2a. If user's active field is set to true
           return 200("already verified")
        2b. If user's active field is set to false
           set it to true and return 200("verified")
    """
    def get(self, request: Request) -> Response:
        code = request.query_params.get('code')
        # 1:
        try:
            user = User.objects.get(last_name=code)
            if user.active:
                # 2a:
                return Response(
                    data={
                        'message': 'already verified'
                    },
                    status=200)
            else:
                # 2b:
                user.active = True
                user.save()
                return Response(
                    data={
                        'message': 'verified'
                    },
                    status=200)
        except User.DoesNotExist:
            return Response(
                data={
                    'message': 'code not valid for any user'
                },
                status=404)


class GetMe(APIView):
    """
    Get the user by the provided JWT token.

    Endpoint: `api/get-me`

    TODO: don't return too much data bc the email code gets exposed
          among other things

    Input: -
    Logic:
        1. Get claimed username from the token
        2. Anonymous user -> empty response   TODO: maybe consider
                                                    different approach
        3. Return user object
    """
    def get(self, request: Request) -> Response:
        # 1:
        jwt_username = request.user.username
        # 2:
        if not jwt_username:
            return Response()  # (EMPTY RESPONSE IF NO TOKEN)
        # 3:
        user = User.objects.get(username=jwt_username)
        serializer = UserSerializer(user)
        return Response(serializer.data)


class GetDecks(APIView):
    """
    Get user's decks which are accessible to the requesting user.

    Endpoint: `api/get-decks?username={username}`

    Input: request.query_params[username]
    Logic:
        1. Does the {username} user exist ? continue : 404 
        2. username <-> jwt ? send all decks : send public decks
    """
    def get(self, request: Request) -> Response:
        username = request.query_params.get('username')
        # 1:
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                data={
                    'message': f'{username} user not found'
                },
                status=404)
        # 2:
        jwt_username = request.user.username
        if not JWT_AUTH or username == jwt_username:
            decks = Deck.objects.all().filter(owner=user)
        else:
            decks = (Deck.objects.all().filter(owner=user)
                     .filter(public=True))
        serializer = DeckSerializer(decks, many=True)
        return Response(serializer.data)


class GetDeckInfo(APIView):
    """
    Get deck info of a particular deck.

    Endpoint: `api/get-deck-info?username={username}&deckname={deckname}`

    Input: request.query_params[username, deckname]
    Logic:
        1. Does the {username} user exist ? continue : 404(user) 
        2. Does the {deckname} deck exist ? continue : 404(deck) 
        3. Is the deck public ? send deck info : continue
        4. username <-> jwt ? send deck info : 404(deck)
    """
    def get(self, request: Request) -> Response:
        username = request.query_params.get('username')
        deckname = request.query_params.get('deckname')
        # 1:
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                data={
                    'message': f'{username} user not found'
                },
                status=404)
        # 2:
        try:
            deck: Deck = Deck.objects.get(owner=user, name=deckname)
        except Deck.DoesNotExist:
            return Response(
                data={
                    'message': f'{deckname} deck not found'
                },
                status=404)
        # 3&4:
        if JWT_AUTH and not deck.public:
            jwt_username = request.user.username
            if username != jwt_username:
                return Response(
                    data={
                        'message': f'{deckname} deck not found'
                    },
                    status=404)
        serializer = DeckInfoSerializer(deck)
        return Response(serializer.data)


class GetDeckStats(APIView):
    """
    Get the stats of a particular user on a particular deck.

    Endpoint: `get-deck-stats?username={username}&deckname={deckname}`

    TODO: change the protocol to also include the username of the one
          requesting the stats to enable JWT_AUTH=False tests later

    Input: request.query_params[username, deckname]
    Logic:
        1. no jwt -> no stats (401) (irregardless of JWT_AUTH)
        2. Does the {username} user exist ? continue : 404(user)
        3. Does the {deckname} deck exist ? continue : 404(deck)
        4. Is the deck public ? get the user(jwt) stats : continue
        5. username <-> jwt ? get user(jwt) stats : 404(deck)
    """
    def get(self, request: Request) -> Response:
        username = request.query_params.get('username')
        deckname = request.query_params.get('deckname')
        # 1:
        jwt_user = request.user
        jwt_username = request.user.username
        if not jwt_username:
            return Response(status=401)
        # 2:
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                data={
                    'message': f'{username} user not found'
                },
                status=404)
        # 3:
        try:
            deck: Deck = Deck.objects.get(owner=user, name=deckname)
        except Deck.DoesNotExist:
            return Response(
                data={
                    'message': f'{deckname} deck not found'
                },
                status=404)
        # 4&5:
        if deck.public or username == jwt_username:
            stats = Stat.objects.all().filter(owner=jwt_user)
        else:
            return Response(
                data={
                    'message': f'{deckname} deck not found'
                },
                status=404)
        serializer = StatSerializer(stats, many=True)
        return Response(serializer.data)


class GetDeckStuff(APIView):
    """
    Get all the stuff of one owns deck (i.e., name, color,
    public/private status, description, and cards) for update purposes.

    Endpoint: `get-deck-stuff?username={username}&deckname={deckname}`

    # TODO: maybe change logic to enable JWT_AUTH=False tests

    Input: request.query_params[username, deckname]
    Logic:
        1. no jwt -> no stuff (401) (irregardless of JWT_AUTH)
        2. username <-> jwt ? continue : 401 error
        3. Does the {deckname} deck exist ? return stuff : 404(deck)
    """
    def get(self, request: Request) -> Response:
        username = request.query_params.get('username')
        deckname = request.query_params.get('deckname')
        # 1:
        jwt_username = request.user.username
        if not jwt_username:
            return Response(status=401)
        # 2:
        if username != jwt_username:
            return Response(status=401)
        # 3:
        user = request.user
        try:
            deck = Deck.objects.get(owner=user, name=deckname)
        except Deck.DoesNotExist:
            return Response(
                data={
                    'message': f'{deckname} deck not found'
                },
                status=404)
        cards = Card.objects.filter(deck=deck)
        deck_serializer = DeckInfoSerializer(deck)
        card_serializer = CardSerializer(cards, many=True)
        return Response({
            'deck': deck_serializer.data,
            'cards': card_serializer.data
        })


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
        1. Block attempts to update user data by anyone other than them
           (irregardless of JWT_AUTH)
        2. Validate the received deck stuff
        3. Process and modify the database objects
        4. Return the updated deck stuff
    """
    def post(self, request: Request) -> Response:
        # 1:
        username = request.query_params.get('username')
        jwt_username = request.user.username
        if username != jwt_username:
            return Response(status=401)
        # 2:
        try:
            data = validate_and_normalize_deck_stuff(request.data)
        except ValidationError as e:
            print(e)   # TODO: differentiate Response by the message
            return Response(
                data={
                    'message': 'validation failed'
                },
                status=400
            )
        # 3:
        deckinfo = data.get('deck')
        cards = data.get('cards')
        user = request.user
        try:
            deck = Deck.objects.get(owner=user, pk=deckinfo['id'])
            deck.name = deckinfo['name']
            deck.color = deckinfo['color']
            deck.public = deckinfo['public']
        except Deck.DoesNotExist:
            deck = Deck(name=deckinfo['name'], color=deckinfo['color'],
                        public=deckinfo['public'], owner=user)
        deck.save()
        try:
            description = DeckDescription.objects.get(deck=deck)
            description.description = deckinfo['description']
        except DeckDescription.DoesNotExist:
            description = DeckDescription(description=deckinfo['description'],
                                          deck=deck)
        description.save()
        # cards:
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
        # 4:
        deck = Deck.objects.get(name=deckinfo['name'], owner=user)
        cards = Card.objects.filter(deck=deck)
        deck_serializer = DeckInfoSerializer(deck)
        card_serializer = CardSerializer(cards, many=True)
        return Response({
            'deck': deck_serializer.data,
            'cards': card_serializer.data
        })


class RemoveDeck(APIView):
    """
    Remove a deck of a particular name of a particular user.

    Endpoint: `remove-deck?username={username}&deckname={deckname}`
    """
    def post(self):
        pass


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
        1. no jwt -> no stuff (401) (irregardless of JWT_AUTH)
        2. Does the {username} user exist ? continue : 404(user)
        3. Does the {deckname} deck exist ? continue : 404(deck)
        4. [tmp] Get random card from the deck
    """
    def get(self, request: Request) -> Response:
        username = request.query_params.get('deck_owner_username')
        deckname = request.query_params.get('deckname')
        # 1:
        jwt_username = request.user.username
        if not jwt_username:
            return Response(status=401)
        # 2:
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                data={
                    'message': f'{username} user not found'
                },
                status=404)
        # 3:
        try:
            deck = Deck.objects.get(owner=user, name=deckname)
        except Deck.DoesNotExist:
            return Response(
                data={
                    'message': f'{deckname} deck not found'
                },
                status=404)
        # 4:
        cards = list(Card.objects.filter(deck=deck))
        if not cards:
            return Response('no cards in deck')
        else:
            random_card = random.choice(cards)
            card_serializer = CardSerializer(random_card)
            return Response(card_serializer.data)


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
        1. no jwt -> no posting feedback (401) (irregardless of
                                                JWT_AUTH)
        2. Does the {deck_owner_username} user exist ? continue
                                                     : 404(user)
        3. Does the {deckname} deck exist ? continue : 404(deck)
        4. Does the {card_id} card exist ? continue : 404(card)
        5. Create new Stat(jwt.user, deck) with specified feedback
    """
    def post(self, request: Request) -> Response:
        deck_owner_username = request.data.get('deck_owner_username')
        deckname = request.data.get('deckname')
        card_id = request.data.get('card_id')
        feedback = request.data.get('feedback')
        # 1:
        jwt_username = request.user.username
        if not jwt_username:
            return Response(status=401)
        jwt_user = request.user
        # 2:
        try:
            user = User.objects.get(username=deck_owner_username)
        except User.DoesNotExist:
            return Response(
                data={
                    'message': f'{deck_owner_username} user not found'
                },
                status=404)
        # 3:
        try:
            deck = Deck.objects.get(owner=user, name=deckname)
        except Deck.DoesNotExist:
            return Response(
                data={
                    'message': f'{deckname} deck not found'
                },
                status=404)
        # 4:
        try:
            card = Card.objects.get(deck=deck, pk=card_id)
        except Deck.DoesNotExist:
            return Response(
                data={
                    'message': f'{card_id} card not found'
                },
                status=404)
        # 5:
        stat = Stat(feedback=feedback,
                    owner=jwt_user,
                    card=card)
        stat.save()
        return Response()
