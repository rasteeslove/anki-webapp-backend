from dataclasses import field
from statistics import mode
from rest_framework import serializers
from anki.models import Deck, DeckDescription, Card, Stat


class DeckSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deck
        fields = '__all__'


class DeckInfoSerializer(serializers.ModelSerializer):
    description = serializers.CharField(source='description.description')
    
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
