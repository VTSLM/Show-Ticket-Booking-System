import React from 'react';

export const ScreenCurve: React.FC = () => {
  return (
    <div className="relative w-full max-w-3xl mx-auto flex flex-col items-center mb-8 select-none">
      {/* Light projection trapezoid beam */}
      <div
        className="w-full h-16 pointer-events-none opacity-40"
        style={{
          background: 'linear-gradient(180deg, rgba(59, 130, 246, 0.25) 0%, rgba(59, 130, 246, 0) 100%)',
          clipPath: 'polygon(15% 0%, 85% 0%, 100% 100%, 0% 100%)',
        }}
      />

      {/* Curved Glowing Cinema Screen Bar */}
      <div className="relative w-full flex items-center justify-center -mt-8">
        <svg
          viewBox="0 0 800 60"
          className="w-full h-12 filter drop-shadow-[0_8px_16px_rgba(59,130,246,0.5)]"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Subtle Outer Glow */}
          <path
            d="M 50 45 Q 400 5 750 45"
            stroke="url(#screen-glow)"
            strokeWidth="10"
            strokeLinecap="round"
            opacity="0.3"
          />
          {/* Main Curved Screen Beam */}
          <path
            d="M 50 45 Q 400 5 750 45"
            stroke="url(#screen-gradient)"
            strokeWidth="5"
            strokeLinecap="round"
          />
          <defs>
            <linearGradient id="screen-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#1E3A8A" stopOpacity="0.4" />
              <stop offset="25%" stopColor="#3B82F6" />
              <stop offset="50%" stopColor="#93C5FD" />
              <stop offset="75%" stopColor="#3B82F6" />
              <stop offset="100%" stopColor="#1E3A8A" stopOpacity="0.4" />
            </linearGradient>
            <linearGradient id="screen-glow" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#2563EB" stopOpacity="0" />
              <stop offset="50%" stopColor="#60A5FA" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#2563EB" stopOpacity="0" />
            </linearGradient>
          </defs>
        </svg>

        <span className="absolute text-[11px] font-semibold tracking-[0.25em] text-blue-300 uppercase opacity-90 drop-shadow">
          SCREEN THIS WAY
        </span>
      </div>
    </div>
  );
};
