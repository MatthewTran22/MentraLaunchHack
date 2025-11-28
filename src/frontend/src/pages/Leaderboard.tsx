import { useState, useEffect } from 'react';

interface TeamScore {
  name: string;
  score: number;
  color: string;
  accentGlow: string;
}

interface StreamSlot {
  id: number;
  label: string;
  streamUrl: string;
  isLive: boolean;
}

export default function Leaderboard() {
  const [teams, setTeams] = useState<TeamScore[]>([
    { name: 'Team 1', score: 0, color: '#FFD93D', accentGlow: 'rgba(255, 217, 61, 0.6)' },
    { name: 'Team 2', score: 0, color: '#FAFAFA', accentGlow: 'rgba(255, 255, 255, 0.5)' },
  ]);
  const [mounted, setMounted] = useState(false);
  const [streams] = useState<StreamSlot[]>([
    { id: 1, label: 'CAM 01', streamUrl: '', isLive: false },
    { id: 2, label: 'CAM 02', streamUrl: '', isLive: false },
    { id: 3, label: 'CAM 03', streamUrl: '', isLive: false },
    { id: 4, label: 'CAM 04', streamUrl: '', isLive: false },
  ]);

  useEffect(() => {
    setMounted(true);
  }, []);

  const leader = teams[0].score >= teams[1].score ? 0 : 1;
  const isTie = teams[0].score === teams[1].score;

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
          background: teams[0].accentGlow,
          opacity: mounted ? 0.15 : 0 
        }}
      />
      <div 
        className="fixed bottom-[-20%] right-[-10%] w-[50%] h-[60%] rounded-full blur-[120px] opacity-20 transition-opacity duration-1000"
        style={{ 
          background: teams[1].accentGlow,
          opacity: mounted ? 0.08 : 0 
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

                {/* Score controls */}
                <div className="mt-10 flex items-center justify-center gap-4">
                  <button
                    onClick={() => {
                      const newTeams = [...teams];
                      newTeams[index].score = Math.max(0, newTeams[index].score - 1);
                      setTeams(newTeams);
                    }}
                    className="w-12 h-12 rounded-full flex items-center justify-center transition-all duration-200 hover:scale-110 active:scale-95"
                    style={{
                      background: 'rgba(255, 255, 255, 0.05)',
                      border: '1px solid rgba(255, 255, 255, 0.1)',
                    }}
                  >
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ color: 'rgba(200, 200, 200, 0.7)' }}>
                      <path d="M5 12h14" />
                    </svg>
                  </button>
                  
                  <button
                    onClick={() => {
                      const newTeams = [...teams];
                      newTeams[index].score += 1;
                      setTeams(newTeams);
                    }}
                    className="w-14 h-14 rounded-full flex items-center justify-center transition-all duration-200 hover:scale-110 active:scale-95"
                    style={{
                      background: `linear-gradient(135deg, ${team.color}20, ${team.color}40)`,
                      border: `1px solid ${team.color}50`,
                      boxShadow: `0 0 20px -5px ${team.accentGlow}`,
                    }}
                  >
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ color: team.color }}>
                      <path d="M12 5v14M5 12h14" />
                    </svg>
                  </button>
                </div>
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
                    {stream.label}
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

        {/* Reset button */}
        <button
          onClick={() => {
            setTeams(teams.map(t => ({ ...t, score: 0 })));
          }}
          className={`mt-16 px-8 py-3 rounded-lg text-xs tracking-[0.3em] uppercase transition-all duration-500 hover:bg-[rgba(255,255,255,0.08)] ${
            mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
          }`}
          style={{
            background: 'rgba(255, 255, 255, 0.03)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            color: 'rgba(150, 150, 150, 0.5)',
            transitionDelay: '400ms',
          }}
        >
          Reset Scores
        </button>
      </div>

      {/* Load Google Fonts */}
      <link 
        href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=JetBrains+Mono:wght@300;400&display=swap" 
        rel="stylesheet" 
      />
    </div>
  );
}
