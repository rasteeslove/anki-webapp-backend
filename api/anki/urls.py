from django.urls import path
from anki.views import (GetDecks,
                        GetDeckInfo,
                        GetDeckStats,
                        GetDeckStuff,
                        UpdateDeckStuff,
                        PullNextCard,
                        PostFeedback)


anki_urls = [
    path('get-decks', GetDecks.as_view()),
    path('get-deck-info', GetDeckInfo.as_view()),
    path('get-deck-stats', GetDeckStats.as_view()),
    path('get-deck-stuff', GetDeckStuff.as_view()),
    path('update-deck-stuff', UpdateDeckStuff.as_view()),
    path('pull-next-card', PullNextCard.as_view()),
    path('post-feedback', PostFeedback.as_view()),
]