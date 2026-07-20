import React from "react";
import { motion } from "framer-motion";

interface FloatingButtonProps {
  onClick: () => void;
  isOpen: boolean;
}

export const FloatingButton: React.FC<FloatingButtonProps> = ({ onClick, isOpen }) => {
  return (
    <motion.button
      onClick={onClick}
      className={`fixed bottom-6 right-6 z-50 flex items-center justify-center w-14 h-14 rounded-full shadow-2xl transition-all duration-300 border backdrop-blur-md cursor-pointer ${
        isOpen
          ? "bg-red-500/10 border-red-500/40 shadow-[0_0_25px_rgba(239,68,68,0.35)]"
          : "bg-card/85 hover:bg-card border-border hover:border-red-500/50 shadow-[0_0_20px_rgba(239,68,68,0.15)] hover:shadow-[0_0_30px_rgba(239,68,68,0.40)]"
      }`}
      whileHover={{ scale: 1.1 }}
      whileTap={{ scale: 0.95 }}
      initial={{ opacity: 0, scale: 0.5 }}
      animate={{ opacity: 1, scale: 1 }}
      title="Praecantator AI"
    >
      <div className="relative flex items-center justify-center">
        {/* Loading logo as the button icon */}
        <img
          src="/loadinglogo.png"
          alt="Praecantator AI"
          className={`w-9 h-9 object-contain select-none transition-all duration-300 ${
            isOpen ? "opacity-70 scale-90" : "opacity-100 animate-[spin_8s_linear_infinite]"
          }`}
          draggable={false}
        />

        {/* Live indicator ping dot */}
        {!isOpen && (
          <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-red-500 rounded-full border border-card">
            <span className="absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75 animate-ping" />
          </span>
        )}
      </div>
    </motion.button>
  );
};
