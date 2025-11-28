# Backend API for Laser Tag Game

FastAPI backend with dataset/sqlite database for a laser tag game.

## Features

- ✅ Wipe DB on startup (configurable via environment variable)
- ✅ Player registration with username, returns player ID
- ✅ Hit tracking: records when a player hits another player
- ✅ Score tracking: automatically increments player scores on hits
- ✅ Leaderboard: shows players, scores, and detailed hit statistics

## Setup

Install dependencies:
```bash
uv sync
```

## Running the Server

Run the FastAPI server:
```bash
uvicorn src.backend.main:app --reload
```

Or with custom host/port:
```bash
uvicorn src.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Wipe Database on Startup

Set the `WIPE_DB_ON_STARTUP` environment variable to `true`:
```bash
WIPE_DB_ON_STARTUP=true uvicorn src.backend.main:app --reload
```

## API Endpoints

### `POST /players`
Create a new player.

**Request:**
```json
{
  "username": "player1"
}
```

**Response:**
```json
{
  "id": 1,
  "username": "player1",
  "score": 0
}
```

### `GET /players/{player_id}`
Get player information by ID.

**Response:**
```json
{
  "id": 1,
  "username": "player1",
  "score": 5
}
```

### `POST /hits`
Record a hit between two players. Automatically increments the hitter's score.

**Request:**
```json
{
  "hitter_id": 1,
  "target_id": 2
}
```

**Response:**
```json
{
  "id": 1,
  "hitter_id": 1,
  "target_id": 2,
  "timestamp": "2024-01-01T12:00:00"
}
```

### `GET /leaderboard`
Get the leaderboard with all players, their scores, and hit statistics.

**Response:**
```json
{
  "players": [
    {
      "player_id": 1,
      "username": "player1",
      "score": 10,
      "hits_given": [
        {
          "target_id": 2,
          "target_username": "player2",
          "hit_count": 5
        },
        {
          "target_id": 3,
          "target_username": "player3",
          "hit_count": 5
        }
      ]
    }
  ]
}
```

### `GET /health`
Health check endpoint.

### `GET /`
Root endpoint with API information.

## Database Schema

- **players**: `id`, `username`, `score`
- **hits**: `id`, `hitter_id`, `target_id`, `timestamp`

The database file is stored as `laser_tag.db` in the project root.