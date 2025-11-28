"""FastAPI application for laser tag game backend."""
import os
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
WIPE_DB_ON_STARTUP = os.getenv("WIPE_DB_ON_STARTUP", "true").lower() == "true"


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
    summary="Create a new player",
    description="Register a new player with a username and get their unique player ID",
    responses={
        201: {
            "description": "Player created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "username": "player1",
                        "score": 0,
                        "team": "yellow"
                    }
                }
            }
        },
        400: {
            "description": "Username already exists",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Username 'player1' already exists"
                    }
                }
            }
        }
    }
)
async def create_player(player: PlayerCreate):
    """
    Create a new player and return their ID.
    
    This endpoint registers a new player in the game. Each player gets a unique ID
    and starts with a score of 0.
    
    - **username**: Must be unique and between 1-100 characters
    - **team**: Must be either "yellow" or "green"
    - Returns the player ID which is used for hit tracking
    
    **Note**: Usernames must be unique. If a username already exists, a 400 error is returned.
    """
    db = get_db()
    players_table = db["players"]
    
    # Check if username already exists
    existing = players_table.find_one(username=player.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{player.username}' already exists"
        )
    
    # Create new player
    player_data = {
        "username": player.username,
        "score": 0,
        "team": player.team,
        "stream_url": None,
    }
    player_id = players_table.insert(player_data)
    
    return PlayerResponse(id=player_id, username=player.username, score=0, team=player.team, stream_url=None)


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
    description="Record a hit between two players and automatically update the hitter's score",
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
            "description": "Invalid hit (e.g., self-hit)",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Players cannot hit themselves"
                    }
                }
            }
        },
        404: {
            "description": "Player not found",
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
    Record a hit between two players.
    
    This endpoint records when one player hits another player. The hitter's score
    is automatically incremented by 1 point.
    
    - **hitter_username**: The username of the player who made the hit
    - **target_username**: The username of the player who was hit
    
    **Rules**:
    - Players cannot hit themselves (returns 400 error)
    - Both players must exist in the database (returns 404 if not found)
    - Each hit increments the hitter's score by 1
    """
    db = get_db()
    players_table = db["players"]
    hits_table = db["hits"]
    
    # Validate players exist by username
    hitter = players_table.find_one(username=hit.hitter_username)
    if not hitter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hitter with username '{hit.hitter_username}' not found"
        )
    
    target = players_table.find_one(username=hit.target_username)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target with username '{hit.target_username}' not found"
        )
    
    # Prevent self-hits
    if hit.hitter_username == hit.target_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Players cannot hit themselves"
        )
    
    hitter_id = hitter["id"]
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

