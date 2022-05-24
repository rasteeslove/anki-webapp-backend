from datetime import datetime as dt
from django.db import models
from django.contrib.auth.models import User


class Deck(models.Model):
    """
    The model for a deck.
    """
    name: models.CharField = models.CharField(max_length=32, default='')
    color: models.CharField = models.CharField(max_length=10, default='')
    public: models.BooleanField = models.BooleanField(default=False)
    owner: models.ForeignKey = models.ForeignKey(User,
                                                 on_delete=models.CASCADE,
                                                 related_name='deck',
                                                 null=True)

    def __str__(self) -> str:
        return self.name


class DeckDescription(models.Model):
    """
    The model of a deck description.

    NOTE: it's separate from the deck model for the sake of
    more atomic structure and (a bit) faster API interaction.
    """
    description: models.TextField = models.TextField(default='')
    deck: models.OneToOneField = models.OneToOneField(Deck,
                                                      on_delete=models.CASCADE,
                                                      related_name='description')

    def __str__(self):
        return f'{self.deck}\'s description'


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

    def __str__(self):
        return f'{self.deck}.{self.pk}'


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

    def __str__(self):
        return  f'{self.owner} on {self.card}'
