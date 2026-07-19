import React from "react";
import { Sparkles } from "lucide-react";
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
          ? "bg-red-500 border-red-400 text-white"
          : "bg-card/85 hover:bg-card border-border hover:border-red-500/50 text-red-500 hover:text-red-400 shadow-[0_0_20px_rgba(239,68,68,0.15)] hover:shadow-[0_0_25px_rgba(239,68,68,0.35)]"
      }`}
      whileHover={{ scale: 1.1 }}
      whileTap={{ scale: 0.95 }}
      initial={{ opacity: 0, scale: 0.5 }}
      animate={{ opacity: 1, scale: 1 }}
      title="Praecantator AI"
    >
      <div className="relative">
        <Sparkles size={22} className={isOpen ? "" : "animate-pulse"} />
        {!isOpen && (
          <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-red-500 rounded-full border border-card">
            <span className="absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75 animate-ping" />
          </span>
        )}
      </div>
    </motion.button>
  );
};
