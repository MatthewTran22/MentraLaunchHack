"""Pydantic models for request/response schemas."""
from datetime import datetime
from typing import List, Literal

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
    team: Literal["yellow", "green"] = Field(
        ...,
        description="Player team (yellow or green)",
        example="yellow"
    )
    stream_url: str | None = Field(
        default=None,
        description="Optional RTMP stream URL for the player",
        example="rtmp://example.com/live/stream1"
    )


class PlayerResponse(BaseModel):
    """Response model for player information."""
    id: int = Field(..., description="Unique player ID", example=1)
    username: str = Field(..., description="Player username", example="player1")
    score: int = Field(default=0, description="Player's current score", example=5)
    team: str = Field(..., description="Player team (yellow or green)", example="yellow")
    stream_url: str | None = Field(default=None, description="Stream URL for the player", example="rtmp://example.com/live/stream1")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "username": "player1",
                "score": 5,
                "team": "yellow",
                "stream_url": "rtmp://example.com/live/stream1"
            }
        }


class HitCreate(BaseModel):
    """Request model for recording a hit."""
    hitter_username: str = Field(..., description="Username of the player who made the hit", example="player1")
    target_team: Literal["yellow", "green"] = Field(..., description="Team that was hit", example="green")

    class Config:
        json_schema_extra = {
            "example": {
                "hitter_username": "player1",
                "target_team": "green"
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
    team: str = Field(..., description="Player team (yellow or green)", example="yellow")
    stream_url: str | None = Field(default=None, description="Stream URL for the player", example="rtmp://example.com/live/stream1")
    hits_given: List[HitCount] = Field(default_factory=list)


class TeamLeaderboard(BaseModel):
    """Model for team leaderboard entry."""
    team: str = Field(..., description="Team name (yellow or green)", example="yellow")
    total_score: int = Field(..., description="Total score of all players in the team", example=25)
    players: List[PlayerLeaderboard] = Field(..., description="List of players in the team sorted by score (descending)")


class LeaderboardResponse(BaseModel):
    """Response model for leaderboard."""
    teams: List[TeamLeaderboard] = Field(..., description="List of teams with their players sorted by total score (descending)")

    class Config:
        json_schema_extra = {
            "example": {
                "teams": [
                    {
                        "team": "yellow",
                        "total_score": 25,
                        "players": [
                            {
                                "player_id": 1,
                                "username": "player1",
                                "score": 15,
                                "team": "yellow",
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
                                        "hit_count": 10
                                    }
                                ]
                            },
                            {
                                "player_id": 3,
                                "username": "player3",
                                "score": 10,
                                "team": "yellow",
                                "stream_url": "rtmp://example.com/live/stream3",
                                "hits_given": [
                                    {
                                        "target_id": 2,
                                        "target_username": "player2",
                                        "hit_count": 10
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        "team": "green",
                        "total_score": 7,
                        "players": [
                            {
                                "player_id": 2,
                                "username": "player2",
                                "score": 7,
                                "team": "green",
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

