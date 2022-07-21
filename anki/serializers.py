from dataclasses import field
from statistics import mode
from rest_framework import serializers
from django.contrib.auth.models import User
from anki.models import Deck, DeckDescription, Card, Stat


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'


class DeckSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deck
        fields = '__all__'


class DeckInfoSerializer(serializers.ModelSerializer):
    description = serializers.CharField(source='description.description')
    card_number = serializers.ReadOnlyField()

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
