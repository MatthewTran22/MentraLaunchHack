"""Pydantic models for request/response schemas."""
from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class PlayerCreate(BaseModel):
    """Request model for creating a new player."""
    username: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Player username",
        example="player1"
    )


class PlayerResponse(BaseModel):
    """Response model for player information."""
    id: int = Field(..., description="Unique player ID", example=1)
    username: str = Field(..., description="Player username", example="player1")
    score: int = Field(default=0, description="Player's current score", example=5)
    stream_url: str | None = Field(default=None, description="Stream URL for the player", example="rtmp://example.com/live/stream1")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "username": "player1",
                "score": 5,
                "stream_url": "rtmp://example.com/live/stream1"
            }
        }


class HitCreate(BaseModel):
    """Request model for recording a hit."""
    hitter_username: str = Field(..., description="Username of the player who made the hit", example="player1")
    target_username: str = Field(..., description="Username of the player who was hit", example="player2")

    class Config:
        json_schema_extra = {
            "example": {
                "hitter_username": "player1",
                "target_username": "player2"
            }
        }


class HitResponse(BaseModel):
    """Response model for hit information."""
    id: int = Field(..., description="Unique hit ID", example=1)
    hitter_id: int = Field(..., description="ID of the player who made the hit", example=1)
    target_id: int = Field(..., description="ID of the player who was hit", example=2)
    timestamp: datetime = Field(..., description="When the hit occurred", example="2024-01-01T12:00:00")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "hitter_id": 1,
                "target_id": 2,
                "timestamp": "2024-01-01T12:00:00"
            }
        }


class HitCount(BaseModel):
    """Model for hit count statistics."""
    target_id: int
    target_username: str
    hit_count: int


class PlayerLeaderboard(BaseModel):
    """Model for leaderboard entry."""
    player_id: int
    username: str
    score: int
    stream_url: str | None = Field(default=None, description="Stream URL for the player", example="rtmp://example.com/live/stream1")
    hits_given: List[HitCount] = Field(default_factory=list)


class LeaderboardResponse(BaseModel):
    """Response model for leaderboard."""
    players: List[PlayerLeaderboard] = Field(..., description="List of players sorted by score (descending)")

    class Config:
        json_schema_extra = {
            "example": {
                "players": [
                    {
                        "player_id": 1,
                        "username": "player1",
                        "score": 10,
                        "stream_url": "rtmp://example.com/live/stream1",
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
                    },
                    {
                        "player_id": 2,
                        "username": "player2",
                        "score": 7,
                        "stream_url": "rtmp://example.com/live/stream2",
                        "hits_given": [
                            {
                                "target_id": 1,
                                "target_username": "player1",
                                "hit_count": 7
                            }
                        ]
                    }
                ]
            }
        }


class StreamAssign(BaseModel):
    """Request model for assigning stream to a player."""
    username: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Player username",
        example="player1"
    )
    stream_url: str = Field(
        ...,
        description="Stream URL",
        example="rtmp://example.com/live/stream1"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "username": "player1",
                "stream_url": "rtmp://example.com/live/stream1"
            }
        }


class StreamResponse(BaseModel):
    """Response model for stream assignment."""
    username: str = Field(..., description="Player username", example="player1")
    stream_url: str = Field(..., description="Stream URL", example="rtmp://example.com/live/stream1")

    class Config:
        json_schema_extra = {
            "example": {
                "username": "player1",
                "stream_url": "rtmp://example.com/live/stream1"
            }
        }

