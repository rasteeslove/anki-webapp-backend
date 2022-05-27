from typing import Any

from django.http import Http404

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from django.contrib.auth.models import User
from anki.models import Deck, Card, DeckDescription, Stat
from anki.serializers import (DeckInfoSerializer,
                              DeckSerializer,
                              CardSerializer,
                              StatSerializer)


class GetDecks(APIView):
    """
    Get all decks of a user.

    Endpoint: `api/get-decks?username={username}`

    Get a username, return decks of a user whose username that is.
    If no such user, return 404.

    TODO: auth and public/private decks
    """
    def get(self, request: Request, format: Any = None) -> Response:
        username = request.query_params.get('username')
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise Http404   # TODO: add meta info maybe

        decks = Deck.objects.all().filter(owner=user)
        serializer = DeckSerializer(decks, many=True)
        return Response(serializer.data)


class GetDeckInfo(APIView):
    """
    Get deck info.

    Endpoint: `api/get-deck-info?username={username}&deckname={deckname}`

    Get a username and deckname, return basic deck deck information
    + the description of a deck of a passed name of a user
    whose username is the passed one.
    If no such deck and/or user, return 404.

    TODO: auth and public/private decks
    """
    def get(self, request: Request, format: Any = None) -> Response:
        username = request.query_params.get('username')
        deckname = request.query_params.get('deckname')
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise Http404   # TODO: add meta info maybe

        try:
            deck = Deck.objects.get(owner=user, name=deckname)
        except Deck.DoesNotExist:
            raise Http404   # TODO: add meta info maybe

        serializer = DeckInfoSerializer(deck)
        return Response(serializer.data)


class GetDeckStats(APIView):
    """
    Get user's stats on a deck.

    Endpoint: `get-deck-stats?username={username}&deckname={deckname}`

    Get a username and deckname, return stats of a deck
    of a passed name of a user whose username is the passed one.
    If no such deck and/or user, return 404.

    TODO: auth and public/private decks
    """
    def get(self, request: Request, format: Any = None) -> Response:
        username = request.query_params.get('username')
        deckname = request.query_params.get('deckname')
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise Http404   # TODO: add meta info maybe

        try:
            deck = Deck.objects.get(owner=user, name=deckname)
        except Deck.DoesNotExist:
            raise Http404   # TODO: add meta info maybe

        # TODO: decide upon what to return as the stats
        return Response()


class GetDeckStuff(APIView):
    """
    Get all the stuff of a deck (i.e., name, color, public/private status,
    description, and cards) for update purposes.

    Endpoint: `get-deck-stuff?username={username}&deckname={deckname}`

    TODO: auth
    """
    def get(self, request: Request, format: Any = None) -> Response:
        username = request.query_params.get('username')
        deckname = request.query_params.get('deckname')
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise Http404   # TODO: add meta info maybe

        try:
            deck = Deck.objects.get(owner=user, name=deckname)
        except Deck.DoesNotExist:
            raise Http404   # TODO: add meta info maybe

        cards = Card.objects.filter(deck=deck)

        deck_serializer = DeckInfoSerializer(deck)
        card_serializer = CardSerializer(cards, many=True)
        return Response({
                'deck': deck_serializer.data,
                'cards': card_serializer.data
            })


class UpdateDeckStuff(APIView):
    """
    Update a deck's stuff (i.e., name, color, public/private status,
    description, and cards).

    Endpoint: `api/update-deck-stuff`

    TODO: auth
    """
    def post(self, request: Request, format: Any = None) -> Response:
        username = request.query_params.get('username')
        deckinfo = request.data.get('deck')
        cards = request.data.get('cards')

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise Http404   # TODO: add meta info maybe

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
    """
    def get(self, request: Request, format: Any = None) -> Response:
        pass


class PostFeedback(APIView):
    """
    Post feedback on a card that a user got.
    """
    def post(self, request: Request, format: Any = None) -> Response:
        pass
