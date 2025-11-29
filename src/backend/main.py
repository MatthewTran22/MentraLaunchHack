"""FastAPI application for laser tag game backend."""
import os
import random
from datetime import datetime

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .database import get_db, init_db
from .models import (
    HitCreate,
    HitResponse,
    LeaderboardResponse,
    PlayerCreate,
    PlayerLeaderboard,
    PlayerResponse,
    HitCount,
    StreamAssign,
    StreamResponse,
    TeamLeaderboard,
)

# Initialize FastAPI app
app = FastAPI(
    title="Laser Tag Game API",
    description="""
    Backend API for laser tag game with player tracking and scoring.
    
    ## Features
    
    * **Player Management**: Register players and track their scores
    * **Hit Tracking**: Record hits between players and automatically update scores
    * **Leaderboard**: View player rankings with detailed hit statistics
    
    ## Database
    
    The API uses SQLite with the `dataset` library. The database file is stored as `laser_tag.db` in the project root.
    
    ## Configuration
    
    Set `WIPE_DB_ON_STARTUP=true` environment variable to wipe the database on server startup.
    """,
    version="1.0.0",
    root_path="/api",
    contact={
        "name": "Laser Tag Game API",
    },
    license_info={
        "name": "MIT",
    },
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration: Wipe DB on startup (set via environment variable)
WIPE_DB_ON_STARTUP = os.getenv("WIPE_DB_ON_STARTUP", "false").lower() == "true"


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db(wipe_on_startup=WIPE_DB_ON_STARTUP)


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up database connection on shutdown."""
    from .database import close_db
    close_db()


@app.get(
    "/",
    tags=["Info"],
    summary="Root endpoint",
    description="Get API information and status",
    response_description="API information including version and configuration"
)
async def root():
    """
    Root endpoint that returns API information.
    
    Returns basic information about the API including version and whether
    the database is configured to wipe on startup.
    """
    return {
        "message": "Laser Tag Game API",
        "version": "1.0.0",
        "wipe_on_startup": WIPE_DB_ON_STARTUP,
    }


@app.post(
    "/players",
    response_model=PlayerResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Players"],
    summary="Create or reset a player",
    description="Register a new player or reset an existing player's score and hits",
    responses={
        201: {
            "description": "Player created or reset successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "username": "player1",
                        "score": 0,
                        "team": "yellow",
                        "stream_url": "rtmp://example.com/live/stream1"
                    }
                }
            }
        }
    }
)
async def create_player(player: PlayerCreate):
    """
    Create a new player or reset an existing player.
    
    This endpoint registers a new player in the game, or if the player already exists,
    it resets their score to 0, updates their team, and clears all their hits.
    
    - **username**: Must be between 1-100 characters
    - **team**: Must be either "yellow" or "green"
    - **stream_url**: Optional RTMP stream URL for the player
    - Returns the player ID which is used for hit tracking
    
    **Note**: If a username already exists, the player's score is reset to 0 and all
    their hits (both as hitter and target) are deleted. The player's team and stream_url
    are updated to the new values provided.
    """
    db = get_db()
    players_table = db["players"]
    hits_table = db["hits"]
    
    # Check if username already exists
    existing = players_table.find_one(username=player.username)
    
    if existing:
        # Player exists - reset their score and clear all hits
        player_id = existing["id"]
        
        # Reset player score, update team and stream_url
        players_table.update(
            {
                "id": player_id,
                "score": 0,
                "team": player.team,
                "stream_url": player.stream_url,
            },
            ["id"]
        )
        
        # Delete all hits where this player was the hitter
        hits_by_player = list(hits_table.find(hitter_id=player_id))
        for hit in hits_by_player:
            hits_table.delete(id=hit["id"])
        
        # Delete all hits where this player was the target
        hits_on_player = list(hits_table.find(target_id=player_id))
        for hit in hits_on_player:
            hits_table.delete(id=hit["id"])
        
        return PlayerResponse(
            id=player_id,
            username=player.username,
            score=0,
            team=player.team,
            stream_url=player.stream_url
        )
    else:
        # Create new player
        player_data = {
            "username": player.username,
            "score": 0,
            "team": player.team,
            "stream_url": player.stream_url,
        }
        player_id = players_table.insert(player_data)
        
        return PlayerResponse(
            id=player_id,
            username=player.username,
            score=0,
            team=player.team,
            stream_url=player.stream_url
        )


@app.post(
    "/players/stream",
    response_model=StreamResponse,
    status_code=status.HTTP_200_OK,
    tags=["Players"],
    summary="Assign stream to player",
    description="Assign a stream URL to a player by their username",
    responses={
        200: {
            "description": "Stream assigned successfully",
            "content": {
                "application/json": {
                    "example": {
                        "username": "player1",
                        "stream_url": "rtmp://example.com/live/stream1"
                    }
                }
            }
        },
        404: {
            "description": "Player not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Player with username 'player1' not found"
                    }
                }
            }
        }
    }
)
async def assign_stream(stream: StreamAssign):
    """
    Assign a stream URL to a player.
    
    This endpoint assigns a stream URL to a player identified by their username.
    The stream URL is stored in the database and can be retrieved when querying player information.
    
    - **username**: The username of the player to assign the stream to
    - **stream_url**: The stream URL to assign
    
    **Note**: If the player doesn't exist, a 404 error is returned.
    """
    db = get_db()
    players_table = db["players"]
    
    # Check if player exists
    player = players_table.find_one(username=stream.username)
    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Player with username '{stream.username}' not found"
        )
    
    # Update player with stream URL
    players_table.update(
        {"id": player["id"], "stream_url": stream.stream_url},
        ["id"]
    )
    
    return StreamResponse(
        username=stream.username,
        stream_url=stream.stream_url
    )


@app.post(
    "/hits",
    response_model=HitResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Hits"],
    summary="Record a hit",
    description="Record a hit on a target team and automatically update the hitter's score",
    responses={
        201: {
            "description": "Hit recorded successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "hitter_id": 1,
                        "target_id": 2,
                        "timestamp": "2024-01-01T12:00:00"
                    }
                }
            }
        },
        400: {
            "description": "Invalid hit (e.g., hitting own team)",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Players cannot hit their own team"
                    }
                }
            }
        },
        404: {
            "description": "Player or team not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Hitter with username 'player1' not found"
                    }
                }
            }
        }
    }
)
async def record_hit(hit: HitCreate):
    """
    Record a hit on a target team.
    
    This endpoint records when one player hits a team. A random player from the target
    team is selected as the target, and the hitter's score is automatically incremented by 1 point.
    
    - **hitter_username**: The username of the player who made the hit
    - **target_team**: The team that was hit (yellow or green)
    
    **Rules**:
    - Players cannot hit their own team (returns 400 error)
    - The hitter must exist in the database (returns 404 if not found)
    - The target team must have at least one player (returns 404 if no players found)
    - Each hit increments the hitter's score by 1
    """
    db = get_db()
    players_table = db["players"]
    hits_table = db["hits"]
    
    # Validate hitter exists by username
    hitter = players_table.find_one(username=hit.hitter_username)
    if not hitter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hitter with username '{hit.hitter_username}' not found"
        )
    
    hitter_id = hitter["id"]
    hitter_team = hitter.get("team", "yellow")
    
    # Prevent hitting own team
    if hitter_team.lower() == hit.target_team.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Players cannot hit their own team"
        )
    
    # Find all players on the target team
    target_players = list(players_table.find(team=hit.target_team))
    if not target_players:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No players found on team '{hit.target_team}'"
        )
    
    # Select a random player from the target team
    target = random.choice(target_players)
    target_id = target["id"]
    
    # Record the hit
    hit_data = {
        "hitter_id": hitter_id,
        "target_id": target_id,
        "timestamp": datetime.utcnow(),
    }
    hit_id = hits_table.insert(hit_data)
    
    # Update scores: hitter gets +1 point
    players_table.update(
        {"id": hitter_id, "score": hitter.get("score", 0) + 1},
        ["id"]
    )
    
    # Get the created hit
    created_hit = hits_table.find_one(id=hit_id)
    return HitResponse(**created_hit)


@app.get(
    "/leaderboard",
    response_model=LeaderboardResponse,
    tags=["Leaderboard"],
    summary="Get leaderboard",
    description="Get the complete leaderboard with team scores and detailed hit statistics",
    responses={
        200: {
            "description": "Leaderboard retrieved successfully",
            "content": {
                "application/json": {
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
            }
        }
    }
)
async def get_leaderboard():
    """
    Get the leaderboard with teams, players, scores, and hit statistics.
    
    Returns a complete leaderboard showing:
    - Teams sorted by total score (highest first)
    - Each team's total score
    - Players within each team sorted by score (highest first)
    - Each player's current score
    - Detailed statistics showing who each player hit and how many times
    
    The leaderboard is sorted in descending order by team total score, so the team with
    the highest total score appears first.
    """
    db = get_db()
    players_table = db["players"]
    hits_table = db["hits"]
    
    # Get all players
    all_players = list(players_table.all())
    
    # Group players by team
    teams_dict = {}
    
    for player in all_players:
        player_id = player["id"]
        team = player.get("team", "yellow")  # Default to yellow if team not set
        
        # Get all hits made by this player
        hits_by_player = list(hits_table.find(hitter_id=player_id))
        
        # Count hits per target
        hit_counts = {}
        for hit in hits_by_player:
            target_id = hit["target_id"]
            hit_counts[target_id] = hit_counts.get(target_id, 0) + 1
        
        # Build hit count list with target usernames
        hits_given = []
        for target_id, count in hit_counts.items():
            target_player = players_table.find_one(id=target_id)
            if target_player:
                hits_given.append(
                    HitCount(
                        target_id=target_id,
                        target_username=target_player["username"],
                        hit_count=count,
                    )
                )
        
        player_entry = PlayerLeaderboard(
            player_id=player_id,
            username=player["username"],
            score=player["score"],
            team=team,
            stream_url=player.get("stream_url"),
            hits_given=hits_given,
        )
        
        # Add player to their team
        if team not in teams_dict:
            teams_dict[team] = []
        teams_dict[team].append(player_entry)
    
    # Build team leaderboard
    team_leaderboards = []
    for team_name, players in teams_dict.items():
        # Sort players by score (descending)
        players.sort(key=lambda x: x.score, reverse=True)
        
        # Calculate total team score
        total_score = sum(player.score for player in players)
        
        team_leaderboards.append(
            TeamLeaderboard(
                team=team_name,
                total_score=total_score,
                players=players,
            )
        )
    
    # Sort teams by total score (descending)
    team_leaderboards.sort(key=lambda x: x.total_score, reverse=True)
    
    return LeaderboardResponse(teams=team_leaderboards)


@app.post(
    "/reset",
    tags=["Admin"],
    summary="Reset leaderboard",
    description="Reset all player scores to 0 and delete all hits",
    responses={
        200: {
            "description": "Leaderboard reset successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Leaderboard reset successfully",
                        "players_reset": 5,
                        "hits_deleted": 42
                    }
                }
            }
        }
    }
)
async def reset_leaderboard():
    """
    Reset the leaderboard by clearing all scores and hits.
    
    This endpoint:
    - Sets all player scores to 0
    - Deletes all hits from the database
    - Preserves player information (username, team, stream_url)
    
    Use this to start a new game round while keeping all registered players.
    """
    db = get_db()
    players_table = db["players"]
    hits_table = db["hits"]
    
    # Get all players and reset their scores
    all_players = list(players_table.all())
    players_reset = 0
    
    for player in all_players:
        players_table.update(
            {
                "id": player["id"],
                "score": 0,
            },
            ["id"]
        )
        players_reset += 1
    
    # Delete all hits
    all_hits = list(hits_table.all())
    hits_deleted = 0
    
    for hit in all_hits:
        hits_table.delete(id=hit["id"])
        hits_deleted += 1
    
    return {
        "message": "Leaderboard reset successfully",
        "players_reset": players_reset,
        "hits_deleted": hits_deleted,
    }


@app.get(
    "/health",
    tags=["Info"],
    summary="Health check",
    description="Check if the API is running and healthy",
    response_description="Health status of the API"
)
async def health_check():
    """
    Health check endpoint.
    
    Use this endpoint to verify that the API is running and responding.
    Returns a simple status message.
    """
    return {"status": "healthy"}

