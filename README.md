# anki-webapp-backend
The back-end for the Anki web app (https://github.com/rasteeslove/anki-webapp).

### Design

API endpoints:

(note: all requests to the API are accompanied by a token if the user is auth'd)

##### auth

- api/auth/token {username} {password} : managed by drf-simplejwt
- api/auth/token/refresh {username} {token} : managed by drf-simplejwt

##### deckspace

- api/get-decks {username} : get decks base data for a username (if {username} not yours, public decks are retrieved)
- api/get-deck-info {username} {deckname} : get full data for a specific deck of a specific user (if it's accessable)
- api/get-deck-stats {username} {deckname} ? : get stats of a deck for the client to render (format to be determined)

##### editmode

- api/get-deck-cards {username} {deckname} : get accessable deck's cards (to be used for editing)
- api/add-deck {deckname}
- api/upd-deck {deckname} {deck data}
- api/rm-deck {username} {deckname}

##### trainmode

- api/get-question {deckname}
- api/send-feedback {deckname} {card id} {success}
