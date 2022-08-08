from django.urls import path
from anki.views import (SignUp,
                        SignUpVerify,
                        GetMe,
                        GetDecks,
                        GetDeckInfo,
                        GetDeckStats,
                        GetDeckStuff,
                        UpdateDeckStuff,
                        PullNextCard,
                        PostFeedback)


anki_urls = [
    path('signup/', SignUp.as_view()),
    path('signup-verify', SignUpVerify.as_view()),
    path('get-me', GetMe.as_view()),
    path('get-decks', GetDecks.as_view()),
    path('get-deck-info', GetDeckInfo.as_view()),
    path('get-deck-stats', GetDeckStats.as_view()),
    path('get-deck-stuff', GetDeckStuff.as_view()),
    path('update-deck-stuff', UpdateDeckStuff.as_view()),
    path('pull-next-card', PullNextCard.as_view()),
    path('post-feedback/', PostFeedback.as_view()),
]
