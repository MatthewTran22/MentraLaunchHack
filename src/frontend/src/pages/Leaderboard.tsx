import { useState, useEffect, useCallback } from 'react';

interface HitCount {
  target_id: number;
  target_username: string;
  hit_count: number;
}

interface Player {
  player_id: number;
  username: string;
  score: number;
  team: string;
  stream_url: string | null;
  hits_given: HitCount[];
}

interface TeamLeaderboard {
  team: string;
  total_score: number;
  players: Player[];
}

interface LeaderboardResponse {
  teams: TeamLeaderboard[];
}

interface TeamScore {
  name: string;
  score: number;
  color: string;
  accentGlow: string;
  players: Player[];
}

interface StreamSlot {
  id: number;
  label: string;
  streamUrl: string;
  isLive: boolean;
  playerUsername?: string;
}

// Team color mappings
const TEAM_COLORS: Record<string, { color: string; accentGlow: string; name: string }> = {
  yellow: {
    color: '#FFD93D',
    accentGlow: 'rgba(255, 217, 61, 0.6)',
    name: 'Team Yellow',
  },
  green: {
    color: '#4ADE80',
    accentGlow: 'rgba(74, 222, 128, 0.6)',
    name: 'Team Green',
  },
};

export default function Leaderboard() {
  // Initialize with default teams to prevent undefined access
  const [teams, setTeams] = useState<TeamScore[]>([
    {
      name: TEAM_COLORS.yellow.name,
      score: 0,
      color: TEAM_COLORS.yellow.color,
      accentGlow: TEAM_COLORS.yellow.accentGlow,
      players: [],
    },
    {
      name: TEAM_COLORS.green.name,
      score: 0,
      color: TEAM_COLORS.green.color,
      accentGlow: TEAM_COLORS.green.accentGlow,
      players: [],
    },
  ]);
  const [mounted, setMounted] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [streams, setStreams] = useState<StreamSlot[]>([
    { id: 1, label: 'CAM 01', streamUrl: '', isLive: false },
    { id: 2, label: 'CAM 02', streamUrl: '', isLive: false },
    { id: 3, label: 'CAM 03', streamUrl: '', isLive: false },
    { id: 4, label: 'CAM 04', streamUrl: '', isLive: false },
  ]);

  const fetchLeaderboard = useCallback(async () => {
    try {
      setError(null);
      const response = await fetch('http://localhost:7777/api/leaderboard');
      if (!response.ok) {
        throw new Error(`Failed to fetch leaderboard: ${response.statusText}`);
      }
      const data: LeaderboardResponse = await response.json();
      
      // Map API response to frontend format
      const mappedTeams: TeamScore[] = data.teams.map((team) => {
        const teamConfig = TEAM_COLORS[team.team] || {
          color: '#FAFAFA',
          accentGlow: 'rgba(255, 255, 255, 0.5)',
          name: `Team ${team.team}`,
        };
        
        return {
          name: teamConfig.name,
          score: team.total_score,
          color: teamConfig.color,
          accentGlow: teamConfig.accentGlow,
          players: team.players,
        };
      });

      // Ensure we have at least yellow and green teams (even if empty)
      const teamMap = new Map(mappedTeams.map(t => [t.name, t]));
      
      // Add missing teams with zero scores
      ['yellow', 'green'].forEach((teamKey) => {
        const teamConfig = TEAM_COLORS[teamKey];
        if (!teamMap.has(teamConfig.name)) {
          mappedTeams.push({
            name: teamConfig.name,
            score: 0,
            color: teamConfig.color,
            accentGlow: teamConfig.accentGlow,
            players: [],
          });
        }
      });

      // Sort by score (descending)
      mappedTeams.sort((a, b) => b.score - a.score);
      
      setTeams(mappedTeams);

      // Update streams from player stream_urls
      const allPlayers = mappedTeams.flatMap(team => team.players);
      const playersWithStreams = allPlayers.filter(p => p.stream_url);
      
      const streamLabels = ['CAM 01', 'CAM 02', 'CAM 03', 'CAM 04'];
      const updatedStreams: StreamSlot[] = streamLabels.map((label, index) => {
        const player = playersWithStreams[index];
        return {
          id: index + 1,
          label,
          streamUrl: player?.stream_url || '',
          isLive: !!player?.stream_url,
          playerUsername: player?.username,
        };
      });
      
      setStreams(updatedStreams);
      setLoading(false);
    } catch (err) {
      console.error('Error fetching leaderboard:', err);
      setError(err instanceof Error ? err.message : 'Failed to load leaderboard');
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setMounted(true);
    fetchLeaderboard();
    
    // Poll for updates every 2 seconds
    const interval = setInterval(fetchLeaderboard, 2000);
    
    return () => clearInterval(interval);
  }, [fetchLeaderboard]);

  const leader = teams.length > 0 && teams.length > 1 
    ? (teams[0].score >= teams[1].score ? 0 : 1)
    : 0;
  const isTie = teams.length > 1 && teams[0].score === teams[1].score;

  return (
    <div className="min-h-screen bg-[#0a0a0a] relative overflow-hidden">
      {/* Subtle noise texture overlay */}
      <div 
        className="fixed inset-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
        }}
      />

      {/* Ambient glow effects */}
      <div 
        className="fixed top-[-20%] left-[-10%] w-[50%] h-[60%] rounded-full blur-[120px] opacity-20 transition-opacity duration-1000"
        style={{ 
          background: teams[0]?.accentGlow || TEAM_COLORS.yellow.accentGlow,
          opacity: mounted && teams.length > 0 ? 0.15 : 0 
        }}
      />
      <div 
        className="fixed bottom-[-20%] right-[-10%] w-[50%] h-[60%] rounded-full blur-[120px] opacity-20 transition-opacity duration-1000"
        style={{ 
          background: teams[1]?.accentGlow || teams[0]?.accentGlow || TEAM_COLORS.green.accentGlow,
          opacity: mounted && teams.length > 0 ? 0.08 : 0 
        }}
      />

      {/* Main content */}
      <div className="relative z-10 min-h-screen flex flex-col items-center justify-center px-6 py-12">
        
        {/* Header */}
        <header 
          className={`mb-16 text-center transition-all duration-700 ${mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}
        >
          <h1 
            className="text-5xl sm:text-6xl md:text-7xl font-light tracking-[0.2em] text-[#e8e8e8] uppercase"
            style={{ fontFamily: "'Bebas Neue', 'Oswald', sans-serif" }}
          >
            Leaderboard
          </h1>
          <div className="mt-4 h-px w-32 mx-auto bg-gradient-to-r from-transparent via-[#333] to-transparent" />
        </header>

        {/* Score cards */}
        <div className="w-full max-w-4xl grid grid-cols-1 md:grid-cols-2 gap-8 md:gap-12">
          {teams.map((team, index) => (
            <div
              key={team.name}
              className={`relative group transition-all duration-700 ${
                mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
              }`}
              style={{ transitionDelay: `${150 + index * 100}ms` }}
            >
              {/* Card */}
              <div 
                className="relative p-8 md:p-12 rounded-2xl border transition-all duration-500"
                style={{
                  background: 'rgba(18, 18, 18, 0.6)',
                  backdropFilter: 'blur(20px)',
                  borderColor: !isTie && leader === index 
                    ? `${team.color}40` 
                    : 'rgba(40, 40, 40, 0.8)',
                  boxShadow: !isTie && leader === index 
                    ? `0 0 60px -20px ${team.accentGlow}` 
                    : 'none',
                }}
              >
                {/* Leader badge */}
                {!isTie && leader === index && (
                  <div 
                    className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full text-xs tracking-[0.3em] uppercase font-medium"
                    style={{ 
                      background: team.color,
                      color: index === 0 ? '#1a1a1a' : '#1a1a1a',
                    }}
                  >
                    Leading
                  </div>
                )}

                {/* Team indicator */}
                <div className="flex items-center gap-3 mb-8">
                  <div 
                    className="w-3 h-3 rounded-full"
                    style={{ 
                      background: team.color,
                      boxShadow: `0 0 12px ${team.accentGlow}`,
                    }}
                  />
                  <span 
                    className="text-sm tracking-[0.25em] uppercase"
                    style={{ 
                      color: team.color,
                      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                    }}
                  >
                    {team.name}
                  </span>
                </div>

                {/* Score display */}
                <div className="text-center">
                  <div 
                    className="text-8xl md:text-9xl font-extralight tabular-nums transition-all duration-300"
                    style={{ 
                      color: team.color,
                      fontFamily: "'Bebas Neue', 'Oswald', sans-serif",
                      textShadow: `0 0 40px ${team.accentGlow}`,
                    }}
                  >
                    {team.score}
                  </div>
                  <div 
                    className="mt-2 text-xs tracking-[0.4em] uppercase"
                    style={{ color: 'rgba(150, 150, 150, 0.6)' }}
                  >
                    Points
                  </div>
                </div>

                {/* Players list */}
                {team.players.length > 0 && (
                  <div className="mt-8 space-y-3">
                    <div 
                      className="text-xs tracking-[0.3em] uppercase mb-4 text-center"
                      style={{ color: 'rgba(150, 150, 150, 0.5)' }}
                    >
                      Players
                    </div>
                    {team.players.map((player) => (
                      <div
                        key={player.player_id}
                        className="flex items-center justify-between p-3 rounded-lg"
                        style={{
                          background: 'rgba(255, 255, 255, 0.03)',
                          border: '1px solid rgba(255, 255, 255, 0.05)',
                        }}
                      >
                        <div className="flex items-center gap-3 flex-1">
                          <div 
                            className="text-sm font-medium"
                            style={{ color: 'rgba(200, 200, 200, 0.9)' }}
                          >
                            {player.username}
                          </div>
                        </div>
                        <div 
                          className="text-sm tabular-nums"
                          style={{ color: team.color }}
                        >
                          {player.score}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Empty state */}
                {team.players.length === 0 && (
                  <div 
                    className="mt-8 text-center py-6"
                    style={{ color: 'rgba(100, 100, 100, 0.5)' }}
                  >
                    <div className="text-xs tracking-[0.2em] uppercase">
                      No players yet
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Tie indicator */}
        {isTie && teams[0].score > 0 && (
          <div 
            className={`mt-12 text-center transition-all duration-500 ${mounted ? 'opacity-100' : 'opacity-0'}`}
          >
            <span 
              className="px-6 py-2 rounded-full text-sm tracking-[0.3em] uppercase"
              style={{
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                color: 'rgba(200, 200, 200, 0.7)',
              }}
            >
              Tied
            </span>
          </div>
        )}

        {/* Camera Streams Section */}
        <div 
          className={`w-full max-w-6xl mt-20 transition-all duration-700 ${
            mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
          }`}
          style={{ transitionDelay: '500ms' }}
        >
          {/* Section header */}
          <div className="flex items-center gap-4 mb-8">
            <div className="h-px flex-1 bg-gradient-to-r from-transparent via-[#333] to-transparent" />
            <h2 
              className="text-sm tracking-[0.4em] uppercase"
              style={{ 
                color: 'rgba(150, 150, 150, 0.6)',
                fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
              }}
            >
              Live Feeds
            </h2>
            <div className="h-px flex-1 bg-gradient-to-r from-transparent via-[#333] to-transparent" />
          </div>

          {/* Stream grid */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {streams.map((stream, index) => (
              <div
                key={stream.id}
                className={`relative aspect-video rounded-xl overflow-hidden transition-all duration-700 group ${
                  mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
                }`}
                style={{ 
                  transitionDelay: `${600 + index * 80}ms`,
                  background: 'rgba(18, 18, 18, 0.6)',
                  backdropFilter: 'blur(20px)',
                  border: '1px solid rgba(40, 40, 40, 0.8)',
                }}
              >
                {/* Stream content or placeholder */}
                {stream.streamUrl ? (
                  <video
                    src={stream.streamUrl}
                    autoPlay
                    muted
                    playsInline
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    {/* Camera icon */}
                    <div 
                      className="w-12 h-12 rounded-full flex items-center justify-center mb-3 transition-all duration-300 group-hover:scale-110"
                      style={{
                        background: 'rgba(255, 255, 255, 0.03)',
                        border: '1px solid rgba(255, 255, 255, 0.08)',
                      }}
                    >
                      <svg 
                        width="20" 
                        height="20" 
                        viewBox="0 0 24 24" 
                        fill="none" 
                        stroke="currentColor" 
                        strokeWidth="1.5"
                        style={{ color: 'rgba(100, 100, 100, 0.6)' }}
                      >
                        <path d="M23 7l-7 5 7 5V7z" />
                        <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
                      </svg>
                    </div>
                    <span 
                      className="text-xs tracking-[0.2em] uppercase"
                      style={{ color: 'rgba(80, 80, 80, 0.8)' }}
                    >
                      No Signal
                    </span>
                  </div>
                )}

                {/* Scanline effect overlay */}
                <div 
                  className="absolute inset-0 pointer-events-none opacity-30"
                  style={{
                    background: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.1) 2px, rgba(0,0,0,0.1) 4px)',
                  }}
                />

                {/* Corner brackets */}
                <div className="absolute top-2 left-2 w-4 h-4 border-l border-t transition-all duration-300" style={{ borderColor: 'rgba(80, 80, 80, 0.4)' }} />
                <div className="absolute top-2 right-2 w-4 h-4 border-r border-t transition-all duration-300" style={{ borderColor: 'rgba(80, 80, 80, 0.4)' }} />
                <div className="absolute bottom-2 left-2 w-4 h-4 border-l border-b transition-all duration-300" style={{ borderColor: 'rgba(80, 80, 80, 0.4)' }} />
                <div className="absolute bottom-2 right-2 w-4 h-4 border-r border-b transition-all duration-300" style={{ borderColor: 'rgba(80, 80, 80, 0.4)' }} />

                {/* Camera label */}
                <div 
                  className="absolute top-3 left-3 flex items-center gap-2"
                >
                  {/* Live indicator dot */}
                  <div 
                    className={`w-2 h-2 rounded-full ${stream.isLive ? 'animate-pulse' : ''}`}
                    style={{ 
                      background: stream.isLive ? '#ef4444' : 'rgba(60, 60, 60, 0.8)',
                      boxShadow: stream.isLive ? '0 0 8px rgba(239, 68, 68, 0.6)' : 'none',
                    }}
                  />
                  <span 
                    className="text-[10px] tracking-[0.2em] uppercase font-medium"
                    style={{ 
                      color: stream.isLive ? 'rgba(239, 68, 68, 0.9)' : 'rgba(100, 100, 100, 0.7)',
                      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                    }}
                  >
                    {stream.playerUsername || stream.label}
                  </span>
                </div>

                {/* REC indicator for live streams */}
                {stream.isLive && (
                  <div 
                    className="absolute top-3 right-3 px-2 py-0.5 rounded text-[9px] tracking-wider font-bold"
                    style={{
                      background: 'rgba(239, 68, 68, 0.2)',
                      border: '1px solid rgba(239, 68, 68, 0.4)',
                      color: '#ef4444',
                    }}
                  >
                    REC
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Loading state */}
        {loading && (
          <div 
            className={`mt-16 text-center transition-all duration-500 ${
              mounted ? 'opacity-100' : 'opacity-0'
            }`}
            style={{ transitionDelay: '400ms' }}
          >
            <div 
              className="text-sm tracking-[0.2em] uppercase"
              style={{ color: 'rgba(150, 150, 150, 0.5)' }}
            >
              Loading...
            </div>
          </div>
        )}

        {/* Error state */}
        {error && !loading && (
          <div 
            className={`mt-16 text-center transition-all duration-500 ${
              mounted ? 'opacity-100' : 'opacity-0'
            }`}
            style={{ transitionDelay: '400ms' }}
          >
            <div 
              className="px-6 py-3 rounded-lg text-sm tracking-[0.2em] uppercase"
              style={{
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                color: 'rgba(239, 68, 68, 0.9)',
              }}
            >
              {error}
            </div>
            <button
              onClick={fetchLeaderboard}
              className="mt-4 px-4 py-2 rounded text-xs tracking-[0.2em] uppercase"
              style={{
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                color: 'rgba(200, 200, 200, 0.7)',
              }}
            >
              Retry
            </button>
          </div>
        )}
      </div>

      {/* Load Google Fonts */}
      <link 
        href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=JetBrains+Mono:wght@300;400&display=swap" 
        rel="stylesheet" 
      />
    </div>
  );
}
