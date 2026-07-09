import React from "react";

export const BrandLoader = () => {
  return (
    <div className="relative flex items-center justify-center">
      {/* Outer big circular ring pulsing/blinking slowly */}
      <div className="absolute w-24 h-24 rounded-full border border-sentinel-red/30 animate-[ping_3s_ease-in-out_infinite] opacity-75" />
      <div className="absolute w-20 h-20 rounded-full border-[2px] border-brand-red/50 animate-[pulse_2s_ease-in-out_infinite]" />
      
      {/* Inner circular wrapper for the logo */}
      <div className="relative w-16 h-16 rounded-full overflow-hidden flex items-center justify-center bg-background/80 backdrop-blur-sm border-[2px] border-sentinel-red shadow-[0_0_15px_rgba(219,29,73,0.5)] animate-[pulse_4s_ease-in-out_infinite]">
        <img 
          src="/Praecantator.png" 
          alt="Praecantator Loading" 
          className="w-12 h-12 object-contain animate-[pulse_3s_ease-in-out_infinite]"
        />
      </div>
    </div>
  );
};
