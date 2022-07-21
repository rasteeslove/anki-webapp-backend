from typing import Any

from django.http import HttpResponse, HttpResponseNotFound

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


class GetMe(APIView):
    """
    Get the user by the provided JWT token.

    Params: ?jwt
    """
    def get(self, request: Request, format: Any = None) -> Response:
        jwt_username = request.user.username
        if not jwt_username:
            return Response()   # empty response if no token
        try:
            user = User.objects.get(username=jwt_username)
        except:
            return HttpResponseNotFound(f'{jwt_username} user not found')
        serializer = UserSerializer(user)
        return Response(serializer.data)


class GetDecks(APIView):
    """
    Get all user's decks which are accessable to the requesting one.

    Endpoint: `api/get-decks?username={username}`

    Params: username, ?jwt 
    Logic: 
        1. Does the {username} user exist ? continue : 404 
        2. username <-> jwt ? send all decks : send public decks
    """
    def get(self, request: Request, format: Any = None) -> Response:
        username = request.query_params.get('username')
        # 1:
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return HttpResponseNotFound(f'{username} user not found')
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
        1. Does the {username} user exist ? continue : 404(user) 
        2. Does the {deckname} deck exist ? continue : 404(deck) 
        3. Is the deck public ? send deck info : continue
        4. username <-> jwt ? send deck info : 404(deck)
    """
    def get(self, request: Request, format: Any = None) -> Response:
        username = request.query_params.get('username')
        deckname = request.query_params.get('deckname')
        # 1:
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return HttpResponseNotFound(f'{username} user not found')
        # 2:
        try:
            deck: Deck = Deck.objects.get(owner=user, name=deckname)
        except Deck.DoesNotExist:
            return HttpResponseNotFound(f'{deckname} deck not found')
        # 3&4:
        if JWT_AUTH and not deck.public:
            jwt_username = request.user.username
            if username != jwt_username:
                return HttpResponseNotFound(f'{deckname} deck not found')
        serializer = DeckInfoSerializer(deck)
        return Response(serializer.data)


class GetDeckStats(APIView):
    """
    Get user's stats on a deck if allowed.

    Endpoint: `get-deck-stats?username={username}&deckname={deckname}`

    Params: username, deckname, jwt
    Logic:
        0. no jwt -> no stats (401) (irregardless of JWT_AUTH)
        1. Does the {username} user exist ? continue : 404(user) 
        2. Does the {deckname} deck exist ? continue : 404(deck) 
        3. Is the deck public ? get the user(jwt) stats : continue
        4. username <-> jwt ? get user(jwt) stats : 404(deck)
    """
    def get(self, request: Request, format: Any = None) -> Response:
        username = request.query_params.get('username')
        deckname = request.query_params.get('deckname')
        # 0:
        jwt_username = request.user.username
        if not jwt_username:
            return HttpResponse(status=401)
        # 1:
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return HttpResponseNotFound(f'{username} user not found')
        # 2:
        try:
            deck: Deck = Deck.objects.get(owner=user, name=deckname)
        except Deck.DoesNotExist:
            return HttpResponseNotFound(f'{deckname} deck not found')
        # 3&4:
        if deck.public or username == jwt_username:
            stats = Stat.objects.all().filter(owner=jwt_username)
        else:
            return HttpResponseNotFound(f'{deckname} deck not found')
        serializer = StatSerializer(stats, many=True)
        return Response(serializer.data)


class GetDeckStuff(APIView):
    """
    Get all the stuff of {my} deck (i.e., name, color,
    public/private status, description, and cards) for update purposes.

    Endpoint: `get-deck-stuff?username={username}&deckname={deckname}`

    Params: username, deckname, jwt
    Logic:
        0. no jwt -> no stuff (401)
        1. Does the {username} user exist ? continue : 404(user) 
        2. username <-> jwt ? continue : 401 error
        3. Does the {deckname} deck exist ? return stuff : 404(deck) 
    """
    def get(self, request: Request, format: Any = None) -> Response:
        username = request.query_params.get('username')
        deckname = request.query_params.get('deckname')
        # 0:
        jwt_username = request.user.username
        if not jwt_username:
            return HttpResponse(status=401)
        # 1:
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return HttpResponseNotFound(f'{username} user not found')
        # 2:
        if username != jwt_username:
            return HttpResponse(status=401)
        # 3:
        try:
            deck = Deck.objects.get(owner=user, name=deckname)
        except Deck.DoesNotExist:
            return HttpResponseNotFound(f'{deckname} deck not found')
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

    Endpoint: `api/update-deck-stuff`

    Input: jwt, deck stuff
    1. Process (jwt)user's deck stuff and modify the database objects
    """
    def post(self, request: Request, format: Any = None) -> Response:
        username = request.query_params.get('username')
        deckinfo = request.data.get('deck')
        cards = request.data.get('cards')
        jwt_username = request.user.username
        if username != jwt_username:
            return HttpResponse(status=401)
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return HttpResponseNotFound(f'{username} user not found')
        try:
            deck = Deck.objects.get(owner=user, pk=deckinfo.id)
            deck.name = deckinfo.name
            deck.color = deckinfo.color
            deck.public = deckinfo.public
        except Deck.DoesNotExist:
            deck = Deck(name=deckinfo.name, color=deckinfo.color,
                        public=deckinfo.public, owner=user)
        deck.save()
        try:
            description = DeckDescription.objects.get(deck=deck)
            description.description = deckinfo.description
        except DeckDescription.DoesNotExist:
            description = DeckDescription(description=deckinfo.description,
                                          deck=deck)
        description.save()
        for card in cards:
            try:
                card_in_db = Card.objects.get(pk=card.id)
                card_in_db.question = card.question
                card_in_db.answer = card.answer
            except Card.DoesNotExist:
                card_in_db = Card(question = card.question,
                                  answer = card.answer,
                                  deck=deck)
            card_in_db.save()
        return Response()


class PullNextCard(APIView):
    """
    Get a not-exactly-random card from a deck.
    To clarify: "not-exactly-random" means the next card that
    the backend find appropriate to give to a user.

    Basically the logic of this view is the biggest pain in the ass
    of the whole app.
    """
    def get(self, request: Request, format: Any = None) -> Response:
        pass  # here the app supposedly accesses all the stats on
              # a deck and decides what card is the most suitable to
              # return.


class PostFeedback(APIView):
    """
    Post feedback on a card that a user got.
    """
    def post(self, request: Request, format: Any = None) -> Response:
        pass
