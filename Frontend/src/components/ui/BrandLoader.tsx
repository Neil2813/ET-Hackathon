import React from "react";

export const BrandLoader = () => {
  return (
    <div className="flex flex-col items-center justify-center">
      {/* Self-contained styling to guarantee animations and styles */}
      <style>{`
        @keyframes loader-spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes text-fade {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.6; }
        }
        @keyframes logo-breathe {
          0%, 100% { transform: scale(1.00); }
          50% { transform: scale(1.02); }
        }
        .custom-spin-arc {
          animation: loader-spin 1.3s linear infinite;
        }
        .custom-text-fade {
          animation: text-fade 3s ease-in-out infinite;
        }
        .custom-logo-breathe {
          animation: logo-breathe 3s ease-in-out infinite;
          transform-origin: center;
        }
      `}</style>

      <div className="relative flex items-center justify-center w-24 h-24">
        {/* Soft single radial glow behind the loader */}
        <div 
          className="absolute rounded-full bg-red-500/5 blur-xl pointer-events-none" 
          style={{ width: '120px', height: '120px', borderRadius: '9999px' }}
        />

        {/* Rotating Loading Arc (◜ shape) wrapping the logo with 6px visual spacing */}
        <svg 
          className="absolute inset-0 w-full h-full custom-spin-arc" 
          viewBox="0 0 100 100"
        >
          <circle
            cx="50"
            cy="50"
            r="46"
            fill="none"
            stroke="#ef4444"
            strokeWidth="2"
            strokeLinecap="round"
            strokeDasharray="70 220"
          />
        </svg>

        {/* Perfectly Circular Logo Sticker Container (80px) with overflow-hidden */}
        <div 
          className="relative w-20 h-20 rounded-full overflow-hidden bg-transparent flex items-center justify-center custom-logo-breathe"
          style={{ borderRadius: '9999px' }}
        >
          <img
            src="/loadinglogo.png"
            alt="Loading Logo"
            className="w-full h-full object-cover rounded-full scale-105 select-none pointer-events-none"
            draggable={false}
          />
        </div>
      </div>

      {/* Enterprise Status Message */}
      <div className="mt-6 flex items-center justify-center h-4">
        <p className="font-mono text-[9px] tracking-[0.25em] text-slate-400 font-semibold uppercase custom-text-fade select-none">
          Initializing secure node
        </p>
      </div>
    </div>
  );
};
