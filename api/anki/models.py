from datetime import datetime as dt
from django.db import models
from django.contrib.auth.models import User


class Deck(models.Model):
    """
    The model for a deck.
    """
    name: models.CharField = models.CharField(max_length=32, default='')
    color: models.CharField = models.CharField(max_length=10, default='')
    description: models.TextField = models.TextField(default='')
    owner: models.ForeignKey = models.ForeignKey(User,
                                                 on_delete=models.CASCADE,
                                                 related_name='deck',
                                                 null=True)


class Card(models.Model):
    """
    The model for a deck card.
    """
    question: models.TextField = models.TextField(default='')
    answer: models.TextField = models.TextField(default='')
    deck: models.ForeignKey = models.ForeignKey(Deck,
                                                on_delete=models.CASCADE,
                                                related_name='card',
                                                null=True)


class Stat(models.Model):
    """
    The model for a user's stat on a card.
    """
    datetime: models.DateTimeField = models.DateTimeField(default=dt.now,
                                                          blank=True)
    feedback: models.BooleanField = models.BooleanField(default=False)
    owner: models.ForeignKey = models.ForeignKey(User,
                                                 on_delete=models.CASCADE,
                                                 related_name='owner_stat',
                                                 null=True)
    card: models.ForeignKey = models.ForeignKey(Card,
                                                on_delete=models.CASCADE,
                                                related_name='card_stat',
                                                null=True)
