from django.contrib import admin
from anki.models import Deck, DeckDescription, Card, Stat


admin.site.register(Deck)
admin.site.register(DeckDescription)
admin.site.register(Card)
admin.site.register(Stat)
