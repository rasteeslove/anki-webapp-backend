from statistics import mode
from rest_framework import serializers
from anki.models import Deck, Card, Stat


class DeckSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deck
        fields = '__all__'


class CardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Card
        fields = '__all__'


class StatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stat
        fields = '__all__'
