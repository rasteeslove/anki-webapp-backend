import random

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
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

from api.settings import JWT_AUTH

# TODO: consider different error response codes


class SignUp(APIView):
    """
    Sign up view.

    Endpoint: `api/signup`

    Input: username, email, password
    Logic:
        0. [token present -> the middleware checks token validity]
        1. If there's a token, return 400
        2. Validate data (including email) and return 400 if not valid
        3. Create new user object, set active field to false
        4. Send an email to the provided address with the link
           containing the unique code
        5. Return the new user object as response
    """
    def post(self, request: Request) -> Response:
        username = request.data.get('username')
        email = request.data.get('email')
        password = request.data.get('password')
        # 1:
        jwt_username = request.user.username
        if jwt_username:
            return Response(
                data={
                    'message': 'you aren\'t supposed to register while logged in'
                },
                status=400)
        # 2:
        # string lengths:
        try:
            assert len(username) <= 20
            assert len(email) <= 20
            assert len(password) <= 20
        except AssertionError:
            return Response(
                data={
                    'message': 'cred strings too long (>20)'
                },
                status=400)
        # email:
        try:
            validate_email(email)
        except ValidationError:
            return Response(
                data={
                    'message': 'invalid email'
                },
                status=400)
        # 3:
        try:
            new_user = User.objects.create_user(username=username,
                                                email=email,
                                                password=password,
                                                last_name=get_random_string(length=32))
            new_user.active = False
        except Exception as e:
            print(e)
            return Response(
                data={
                    'message': 'provided username/email already exists'
                },
                status=400)
        # 4:
        # TODO: use AWS SES
        # 5:
        serializer = UserSerializer(new_user)
        return Response(serializer.data)


class SignUpVerify(APIView):
    """
    Sign up verification view.

    Endpoint: `api/signup-verify?code={code}`

    Params: code
    Logic:
        0. [token present -> the middleware checks token validity]
        1. Extract user data from the query parameter code
        2. Try finding user by the extracted data
             SUCCESS -> continue
             FAILURE -> 404(user)
        3. If user's active field is set to true
           return 200("already verified")
        4. If user's active field is set to false
           set it to true and return 200("verified")
    """
    pass


class GetMe(APIView):
    """
    Get the user by the provided JWT token.

    Endpoint: `api/get-me`

    Params: ?jwt
    Logic:
        0. [token present -> the middleware checks token validity]
        1. Get claimed username from the token
        2. Anonymous user -> empty response   TODO: maybe consider
                                                    different approach
        3. Return user object
    """

    def get(self, request: Request) -> Response:
        jwt_username = request.user.username
        if not jwt_username:
            return Response()  # (EMPTY RESPONSE IF NO TOKEN)
        try:
            user = User.objects.get(username=jwt_username)
        except User.DoesNotExist:
            return Response(
                data={
                    'message': f'{jwt_username} user not found'
                },
                status=404)
        serializer = UserSerializer(user)
        return Response(serializer.data)


class GetDecks(APIView):
    """
    Get all user's decks which are accessible to the requesting one.

    Endpoint: `api/get-decks?username={username}`

    Params: username, ?jwt
    Logic:
        0. [token present -> the middleware checks token validity]
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
    Get deck info if allowed.

    Endpoint: `api/get-deck-info?username={username}&deckname={deckname}`

    Params: username, deckname, ?jwt
    Logic:
        0. [token present -> the middleware checks token validity]
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
    Get user's stats on a deck if allowed.

    Endpoint: `get-deck-stats?username={username}&deckname={deckname}`

    Params: username, deckname, jwt
    Logic:
        0. [token present -> the middleware checks token validity]
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
            stats = Stat.objects.all().filter(owner=jwt_username)
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
    Get all the stuff of {my} deck (i.e., name, color,
    public/private status, description, and cards) for update purposes.

    Endpoint: `get-deck-stuff?username={username}&deckname={deckname}`

    Params: username, deckname, jwt
    Logic:
        0. [token present -> the middleware checks token validity]
        1. no jwt -> no stuff (401)
        2. Does the {username} user exist ? continue : 404(user)
        3. username <-> jwt ? continue : 401 error
        4. Does the {deckname} deck exist ? return stuff : 404(deck)
    """

    def get(self, request: Request) -> Response:
        username = request.query_params.get('username')
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
        if username != jwt_username:
            return Response(status=401)
        # 4:
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
    Update {my} deck's stuff (i.e., name, color, public/private status,
    description, and cards).

    Endpoint: `api/update-deck-stuff?username={username}`

    Input: jwt, username, deck stuff
    Logic:
        0. [token present -> the middleware checks token validity]
        1. Validate the received request data against some schema
        2. Process (jwt)user's deck stuff and modify the database objects
        3. Return the updated deck stuff
    """

    def post(self, request: Request) -> Response:
        # 1: TODO: VALIDATE DATA
        username = request.query_params.get('username')
        deckinfo = request.data.get('deck')
        cards = request.data.get('cards')
        # 2:
        jwt_username = request.user.username
        if username != jwt_username:
            return Response(status=401)
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                data={
                    'message': f'{username} user not found'
                },
                status=404)
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
        # 3:
        deck = Deck.objects.get(name=deckinfo['name'], owner=user)
        cards = Card.objects.filter(deck=deck)
        deck_serializer = DeckInfoSerializer(deck)
        card_serializer = CardSerializer(cards, many=True)
        return Response({
            'deck': deck_serializer.data,
            'cards': card_serializer.data
        })


class PullNextCard(APIView):
    """
    Get a not-exactly-random card from a deck.
    To clarify: "not-exactly-random" means the next card that
    the backend find appropriate to give to a user.
    NOTE: it IS random for now :)

    Basically the logic of this view is the biggest pain in the ass
    of the whole app.

    Endpoint: `pull-next-card?deck_owner_username={username}&deckname={deckname}`

    Params: username, deckname, jwt
    Logic:
        0. [token present -> the middleware checks token validity]
        1. no jwt -> no stuff (401)
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
    Post feedback on a card that a user got.

    Endpoint: `post-feedback`

    TODO: change the protocol to also include the username of the one
          leaving the feedback to enable JWT_AUTH=False tests later

    Input: jwt, deck_owner_username, deckname, card_id, feedback
    Logic:
        0. [token present -> the middleware checks token validity]
        1. no jwt -> no posting feedback (401)
        2. Does the jwt user exist ? continue : 401
        3. Does the {deck_owner_username} user exist ? continue
                                                     : 404(user)
        4. Does the {deckname} deck exist ? continue : 404(deck)
        5. Does the {card_id} card exist ? continue : 404(card)
        6. Create new Stat(jwt.user, deck) with specified feedback
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
        # 2:
        try:
            jwt_user = User.objects.get(username=jwt_username)
        except User.DoesNotExist:
            return Response(
                data={
                    'message': f'{jwt_username} user not found'
                },
                status=404)
        # 3:
        try:
            user = User.objects.get(username=deck_owner_username)
        except User.DoesNotExist:
            return Response(
                data={
                    'message': f'{deck_owner_username} user not found'
                },
                status=404)
        # 4:
        try:
            deck = Deck.objects.get(owner=user, name=deckname)
        except Deck.DoesNotExist:
            return Response(
                data={
                    'message': f'{deckname} deck not found'
                },
                status=404)
        # 5:
        try:
            card = Card.objects.get(deck=deck, pk=card_id)
        except Deck.DoesNotExist:
            return Response(
                data={
                    'message': f'{card_id} card not found'
                },
                status=404)
        # 6:
        stat = Stat(feedback=feedback,
                    owner=jwt_user,
                    card=card)
        stat.save()
        return Response()
