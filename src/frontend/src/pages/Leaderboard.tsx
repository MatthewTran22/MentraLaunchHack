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
  gradientFrom: string;
  gradientTo: string;
  players: Player[];
}

interface StreamSlot {
  id: number;
  label: string;
  streamUrl: string;
  isLive: boolean;
  playerUsername?: string;
}

// Team color mappings - sports broadcast style
const TEAM_COLORS: Record<string, { color: string; accentGlow: string; name: string; gradientFrom: string; gradientTo: string; abbrev: string }> = {
  yellow: {
    color: '#FFD93D',
    accentGlow: 'rgba(255, 217, 61, 0.8)',
    name: 'YELLOW',
    gradientFrom: '#FFD93D',
    gradientTo: '#F59E0B',
    abbrev: 'YLW',
  },
  green: {
    color: '#4ADE80',
    accentGlow: 'rgba(74, 222, 128, 0.8)',
    name: 'GREEN',
    gradientFrom: '#4ADE80',
    gradientTo: '#22C55E',
    abbrev: 'GRN',
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
      gradientFrom: TEAM_COLORS.yellow.gradientFrom,
      gradientTo: TEAM_COLORS.yellow.gradientTo,
      players: [],
    },
    {
      name: TEAM_COLORS.green.name,
      score: 0,
      color: TEAM_COLORS.green.color,
      accentGlow: TEAM_COLORS.green.accentGlow,
      gradientFrom: TEAM_COLORS.green.gradientFrom,
      gradientTo: TEAM_COLORS.green.gradientTo,
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
      const response = await fetch('https://gobbler-working-bluebird.ngrok-free.app/api/leaderboard', {
        headers: new Headers({
          "ngrok-skip-browser-warning": "true", // The value can be anything, but "true" is common
        }),
      });
      if (!response.ok) {
        throw new Error(`Failed to fetch leaderboard: ${response.statusText}`);
      }
      const data: LeaderboardResponse = await response.json();
      
      // Map API response to frontend format
      const mappedTeams: TeamScore[] = data.teams.map((team) => {
        const teamConfig = TEAM_COLORS[team.team] || {
          color: '#FAFAFA',
          accentGlow: 'rgba(255, 255, 255, 0.5)',
          name: team.team.toUpperCase(),
          gradientFrom: '#FAFAFA',
          gradientTo: '#E5E5E5',
        };
        
        return {
          name: teamConfig.name,
          score: team.total_score,
          color: teamConfig.color,
          accentGlow: teamConfig.accentGlow,
          gradientFrom: teamConfig.gradientFrom,
          gradientTo: teamConfig.gradientTo,
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
            gradientFrom: teamConfig.gradientFrom,
            gradientTo: teamConfig.gradientTo,
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
  
  // Get all players sorted by score for the ticker
  const allPlayersSorted = [...teams.flatMap(t => t.players)].sort((a, b) => b.score - a.score);

  return (
    <div className="h-screen bg-[#0a0a0f] relative overflow-hidden">
      {/* Animated background grid */}
      <div 
        className="fixed inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)`,
          backgroundSize: '50px 50px',
        }}
      />

      {/* Dramatic gradient overlays */}
      <div className="fixed inset-0 bg-gradient-to-b from-black/50 via-transparent to-black/80" />
      <div className="fixed inset-0 bg-gradient-to-r from-black/30 via-transparent to-black/30" />

      {/* Team glow effects */}
      <div 
        className="fixed top-0 left-0 w-1/2 h-full transition-opacity duration-1000"
        style={{ 
          background: `radial-gradient(ellipse at 20% 30%, ${teams[0]?.accentGlow || TEAM_COLORS.yellow.accentGlow} 0%, transparent 50%)`,
          opacity: mounted ? 0.15 : 0 
        }}
      />
      <div 
        className="fixed top-0 right-0 w-1/2 h-full transition-opacity duration-1000"
        style={{ 
          background: `radial-gradient(ellipse at 80% 30%, ${teams[1]?.accentGlow || TEAM_COLORS.green.accentGlow} 0%, transparent 50%)`,
          opacity: mounted ? 0.15 : 0 
        }}
      />

      {/* Main content */}
      <div className="relative z-10 h-screen flex flex-col">
        
        {/* Top broadcast bar */}
        <div 
          className={`w-full bg-gradient-to-r from-red-600/90 via-red-500/90 to-red-600/90 py-1 transition-all duration-500 shrink-0 ${
            mounted ? 'translate-y-0 opacity-100' : '-translate-y-full opacity-0'
          }`}
          style={{ backdropFilter: 'blur(10px)' }}
        >
          <div className="flex items-center justify-center gap-4 px-4">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-white rounded-full animate-pulse" />
              <span className="text-white text-sm font-bold tracking-wider uppercase">LIVE</span>
            </div>
            <div className="h-4 w-px bg-white/30" />
            <span className="text-white/90 text-sm font-medium tracking-wide">View Pew</span>
            <div className="h-4 w-px bg-white/30" />
            <span className="text-white/70 text-xs tracking-wider">MENTRA ARENA</span>
          </div>
        </div>

        {/* Main content area */}
        <div className="flex-1 flex flex-col px-3 py-2 min-h-0">
          
          {/* Camera Streams Section - NOW AT TOP */}
          <div 
            className={`w-full max-w-6xl mx-auto transition-all duration-700 flex-1 min-h-0 ${
              mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
            }`}
            style={{ transitionDelay: '200ms' }}
          >
            {/* Stream grid - 2x2 layout */}
            <div className="grid grid-cols-2 gap-2 h-full">
              {streams.map((stream, index) => (
                <div
                  key={stream.id}
                  className={`relative rounded-lg overflow-hidden transition-all duration-700 group ${
                    mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
                  }`}
                  style={{ 
                    transitionDelay: `${300 + index * 80}ms`,
                    background: 'linear-gradient(135deg, rgba(20,20,25,0.9) 0%, rgba(10,10,15,0.95) 100%)',
                    border: stream.isLive ? '2px solid rgba(239, 68, 68, 0.3)' : '1px solid rgba(255,255,255,0.08)',
                    boxShadow: stream.isLive ? '0 0 30px rgba(239, 68, 68, 0.1)' : 'none',
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
                        className="w-10 h-10 rounded-full flex items-center justify-center mb-1 transition-all duration-300 group-hover:scale-110"
                        style={{
                          background: 'rgba(255, 255, 255, 0.03)',
                          border: '1px solid rgba(255, 255, 255, 0.08)',
                        }}
                      >
                        <svg 
                          width="16" 
                          height="16" 
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
                        className="text-[10px] tracking-widest uppercase font-medium"
                        style={{ color: 'rgba(80, 80, 80, 0.8)' }}
                      >
                        Awaiting Signal
                      </span>
                    </div>
                  )}

                  {/* Broadcast overlay effect */}
                  <div 
                    className="absolute inset-0 pointer-events-none"
                    style={{
                      background: 'linear-gradient(180deg, transparent 60%, rgba(0,0,0,0.4) 100%)',
                    }}
                  />

                  {/* Scanline effect overlay */}
                  <div 
                    className="absolute inset-0 pointer-events-none opacity-20"
                    style={{
                      background: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.15) 2px, rgba(0,0,0,0.15) 4px)',
                    }}
                  />

                  {/* Corner recording brackets */}
                  <div className="absolute top-1 left-1 w-3 h-3 border-l border-t transition-all duration-300" style={{ borderColor: stream.isLive ? 'rgba(239, 68, 68, 0.6)' : 'rgba(80, 80, 80, 0.4)' }} />
                  <div className="absolute top-1 right-1 w-3 h-3 border-r border-t transition-all duration-300" style={{ borderColor: stream.isLive ? 'rgba(239, 68, 68, 0.6)' : 'rgba(80, 80, 80, 0.4)' }} />
                  <div className="absolute bottom-1 left-1 w-3 h-3 border-l border-b transition-all duration-300" style={{ borderColor: stream.isLive ? 'rgba(239, 68, 68, 0.6)' : 'rgba(80, 80, 80, 0.4)' }} />
                  <div className="absolute bottom-1 right-1 w-3 h-3 border-r border-b transition-all duration-300" style={{ borderColor: stream.isLive ? 'rgba(239, 68, 68, 0.6)' : 'rgba(80, 80, 80, 0.4)' }} />

                  {/* Camera label */}
                  <div 
                    className="absolute bottom-1 left-1 flex items-center gap-1 px-1.5 py-0.5 rounded"
                    style={{
                      background: 'rgba(0,0,0,0.7)',
                      backdropFilter: 'blur(4px)',
                    }}
                  >
                    <div 
                      className={`w-1.5 h-1.5 rounded-full ${stream.isLive ? 'animate-pulse' : ''}`}
                      style={{ 
                        background: stream.isLive ? '#ef4444' : 'rgba(60, 60, 60, 0.8)',
                        boxShadow: stream.isLive ? '0 0 8px rgba(239, 68, 68, 0.6)' : 'none',
                      }}
                    />
                    <span 
                      className="text-[9px] tracking-wider uppercase font-bold"
                      style={{ 
                        color: stream.isLive ? '#fff' : 'rgba(100, 100, 100, 0.7)',
                        fontFamily: "'JetBrains Mono', monospace",
                      }}
                    >
                      {stream.playerUsername || stream.label}
                    </span>
                  </div>

                  {/* REC indicator for live streams */}
                  {stream.isLive && (
                    <div 
                      className="absolute top-1 right-6 flex items-center gap-0.5 px-1 py-0.5 rounded"
                      style={{
                        background: 'rgba(239, 68, 68, 0.9)',
                      }}
                    >
                      <div className="w-1 h-1 bg-white rounded-full animate-pulse" />
                      <span className="text-[8px] text-white font-bold tracking-wider">REC</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Compact Scoreboard - IN THE MIDDLE */}
          <div 
            className={`w-full max-w-4xl mx-auto mt-2 shrink-0 transition-all duration-700 ${
              mounted ? 'opacity-100 scale-100' : 'opacity-0 scale-95'
            }`}
            style={{ transitionDelay: '500ms' }}
          >
            {/* Scoreboard container */}
            <div 
              className="relative rounded-lg overflow-hidden"
              style={{
                background: 'linear-gradient(180deg, rgba(20,20,25,0.95) 0%, rgba(10,10,15,0.98) 100%)',
                border: '1px solid rgba(255,255,255,0.1)',
                boxShadow: '0 15px 50px rgba(0,0,0,0.4)',
              }}
            >
              {/* Top accent bar */}
              <div className="h-0.5 w-full bg-gradient-to-r from-yellow-500 via-white to-green-500" />
              
              {/* Compact Score display area */}
              <div className="flex items-center justify-center py-2 px-4">
                {/* Team 1 (Yellow) */}
                <div className="flex-1 flex items-center justify-end gap-2 pr-4">
                  {/* Leader indicator */}
                  {!isTie && leader === 0 && (
                    <span className="text-lg" style={{ filter: 'drop-shadow(0 0 8px rgba(255,200,0,0.5))' }}>👑</span>
                  )}
                  <div className="text-right">
                    <div 
                      className="text-xs font-bold tracking-[0.2em] uppercase mb-1"
                      style={{ 
                        color: teams[0]?.color,
                        fontFamily: "'JetBrains Mono', monospace",
                      }}
                    >
                      {teams[0]?.name}
                    </div>
                    <div 
                      className="text-4xl md:text-5xl font-black tabular-nums leading-none"
                      style={{ 
                        color: teams[0]?.color,
                        fontFamily: "'Bebas Neue', sans-serif",
                        textShadow: `0 0 30px ${teams[0]?.accentGlow}`,
                      }}
                    >
                      {teams[0]?.score || 0}
                    </div>
                  </div>
                </div>

                {/* VS Divider */}
                <div className="flex flex-col items-center px-4">
                  <div 
                    className="w-10 h-10 rounded-full flex items-center justify-center"
                    style={{
                      background: 'linear-gradient(180deg, #1a1a1f 0%, #0a0a0f 100%)',
                      border: '2px solid rgba(255,255,255,0.1)',
                      boxShadow: '0 0 20px rgba(0,0,0,0.5)',
                    }}
                  >
                    <span 
                      className="text-sm font-black text-white/70 tracking-wider"
                      style={{ fontFamily: "'Bebas Neue', sans-serif" }}
                    >
                      VS
                    </span>
                  </div>
                  {/* Tie indicator */}
                  {isTie && teams[0]?.score > 0 && (
                    <div 
                      className="mt-1 px-1.5 py-0.5 rounded-full text-[7px] font-bold tracking-wider uppercase"
                      style={{
                        background: 'linear-gradient(90deg, #FFD93D, #4ADE80)',
                        color: '#000',
                      }}
                    >
                      TIED
                    </div>
                  )}
                </div>

                {/* Team 2 (Green) */}
                <div className="flex-1 flex items-center justify-start gap-2 pl-4">
                  <div className="text-left">
                    <div 
                      className="text-xs font-bold tracking-[0.2em] uppercase mb-1"
                      style={{ 
                        color: teams[1]?.color,
                        fontFamily: "'JetBrains Mono', monospace",
                      }}
                    >
                      {teams[1]?.name}
                    </div>
                    <div 
                      className="text-4xl md:text-5xl font-black tabular-nums leading-none"
                      style={{ 
                        color: teams[1]?.color,
                        fontFamily: "'Bebas Neue', sans-serif",
                        textShadow: `0 0 30px ${teams[1]?.accentGlow}`,
                      }}
                    >
                      {teams[1]?.score || 0}
                    </div>
                  </div>
                  {/* Leader indicator */}
                  {!isTie && leader === 1 && (
                    <span className="text-lg" style={{ filter: 'drop-shadow(0 0 8px rgba(255,200,0,0.5))' }}>👑</span>
                  )}
                </div>
              </div>

              {/* Bottom stats bar */}
              <div 
                className="px-3 py-1 flex items-center justify-between text-[9px]"
                style={{
                  background: 'rgba(0,0,0,0.4)',
                  borderTop: '1px solid rgba(255,255,255,0.05)',
                }}
              >
                <div className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full" style={{ background: teams[0]?.color }} />
                  <span className="text-white/40 tracking-wider uppercase">{teams[0]?.players.length || 0} Players</span>
                </div>

                {!isTie && Math.abs((teams[0]?.score || 0) - (teams[1]?.score || 0)) > 0 && (
                  <div className="text-white/25 tracking-wider">
                    +{Math.abs((teams[0]?.score || 0) - (teams[1]?.score || 0))} pts lead
                  </div>
                )}

                <div className="flex items-center gap-2">
                  <span className="text-white/40 tracking-wider uppercase">{teams[1]?.players.length || 0} Players</span>
                  <div className="w-1.5 h-1.5 rounded-full" style={{ background: teams[1]?.color }} />
                </div>
              </div>
            </div>
          </div>

          {/* Player Rankings Ticker */}
          {allPlayersSorted.length > 0 && (
            <div 
              className={`w-full max-w-4xl mx-auto mt-2 shrink-0 transition-all duration-700 ${
                mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
              }`}
              style={{ transitionDelay: '600ms' }}
            >
              <div 
                className="rounded overflow-hidden"
                style={{
                  background: 'rgba(15,15,20,0.9)',
                  border: '1px solid rgba(255,255,255,0.08)',
                }}
              >
                {/* Player list - horizontal scroll on mobile, grid on desktop */}
                <div className="grid grid-cols-6 divide-x divide-white/5">
                  {allPlayersSorted.slice(0, 6).map((player, index) => {
                    const teamConfig = TEAM_COLORS[player.team];
                    return (
                      <div
                        key={player.player_id}
                        className="px-2 py-1.5 flex flex-col items-center text-center hover:bg-white/5 transition-colors"
                      >
                        {/* Rank badge */}
                        <div 
                          className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                            index === 0 ? 'bg-yellow-500/20 text-yellow-400' :
                            index === 1 ? 'bg-gray-400/20 text-gray-300' :
                            index === 2 ? 'bg-orange-600/20 text-orange-400' :
                            'bg-white/5 text-white/40'
                          }`}
                        >
                          {index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : index + 1}
                        </div>
                        
                        {/* Player name */}
                        <span className="text-white/80 text-[9px] font-medium truncate w-full">{player.username}</span>
                        
                        {/* Score with team color */}
                        <div className="flex items-center gap-0.5">
                          <div 
                            className="w-1 h-1 rounded-full"
                            style={{ background: teamConfig?.color || '#fff' }}
                          />
                          <span 
                            className="text-xs font-bold tabular-nums"
                            style={{ color: teamConfig?.color || '#fff' }}
                          >
                            {player.score}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

        {/* Bottom ticker bar */}
        <div 
          className={`w-full py-1.5 shrink-0 transition-all duration-700 ${
            mounted ? 'opacity-100' : 'opacity-0'
          }`}
          style={{ 
            transitionDelay: '700ms',
            background: 'linear-gradient(90deg, rgba(15,15,20,0.95), rgba(20,20,25,0.95), rgba(15,15,20,0.95))',
            borderTop: '1px solid rgba(255,255,255,0.05)',
          }}
        >
          <div className="flex items-center justify-center gap-4 px-4 text-[10px]">
            <span className="text-white/30 tracking-wider uppercase">Mentra Launch Hack 2025</span>
            <span className="text-white/10">•</span>
            <span className="text-yellow-500/60 tracking-wider uppercase font-medium">
              {teams[0]?.name}: {teams[0]?.score || 0}
            </span>
            <span className="text-white/30">vs</span>
            <span className="text-green-500/60 tracking-wider uppercase font-medium">
              {teams[1]?.name}: {teams[1]?.score || 0}
            </span>
          </div>
        </div>
        </div>

        {/* Loading state */}
        {loading && (
          <div 
            className={`fixed bottom-6 right-6 transition-all duration-500 ${
              mounted ? 'opacity-100' : 'opacity-0'
            }`}
          >
            <div 
              className="flex items-center gap-3 px-4 py-2 rounded-lg"
              style={{
                background: 'rgba(15,15,20,0.9)',
                border: '1px solid rgba(255,255,255,0.1)',
              }}
            >
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
              <span className="text-white/50 text-xs tracking-wider uppercase">Syncing...</span>
            </div>
          </div>
        )}

        {/* Error state */}
        {error && !loading && (
          <div 
            className={`fixed bottom-6 left-1/2 -translate-x-1/2 transition-all duration-500 ${
              mounted ? 'opacity-100' : 'opacity-0'
            }`}
          >
            <div 
              className="flex items-center gap-4 px-6 py-3 rounded-lg"
              style={{
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
              }}
            >
              <span className="text-red-400 text-sm">{error}</span>
              <button
                onClick={fetchLeaderboard}
                className="px-3 py-1 rounded text-xs tracking-wider uppercase font-bold transition-all hover:bg-white/10"
                style={{
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  color: 'rgba(200, 200, 200, 0.7)',
                }}
              >
                Retry
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Load Google Fonts */}
      <link 
        href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=JetBrains+Mono:wght@300;400;700&display=swap" 
        rel="stylesheet" 
      />

      {/* Custom animation styles */}
      <style>{`
        @keyframes pulse-glow {
          0%, 100% { opacity: 0.5; }
          50% { opacity: 1; }
        }
      `}</style>
    </div>
  );
}
