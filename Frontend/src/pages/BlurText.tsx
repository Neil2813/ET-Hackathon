import { motion } from "framer-motion";

interface BlurTextProps {
  text: string;
  /** Stagger delay in ms between each word/character */
  delay?: number;
  /** Whether to animate word-by-word or character-by-character */
  animateBy?: "words" | "characters";
  /** Direction the text enters from */
  direction?: "top" | "bottom" | "left" | "right";
  className?: string;
}

const BlurText = ({
  text,
  delay = 150,
  animateBy = "words",
  direction = "top",
  className = "",
}: BlurTextProps) => {
  const tokens = animateBy === "words" ? text.split(" ") : text.split("");

  const getInitial = () => {
    switch (direction) {
      case "top":    return { opacity: 0, y: -18, filter: "blur(10px)" };
      case "bottom": return { opacity: 0, y: 18,  filter: "blur(10px)" };
      case "left":   return { opacity: 0, x: -18, filter: "blur(10px)" };
      case "right":  return { opacity: 0, x: 18,  filter: "blur(10px)" };
    }
  };

  const getAnimate = () => {
    switch (direction) {
      case "top":
      case "bottom": return { opacity: 1, y: 0, filter: "blur(0px)" };
      case "left":
      case "right":  return { opacity: 1, x: 0, filter: "blur(0px)" };
    }
  };

  return (
    <span className={className} aria-label={text}>
      {tokens.map((token, i) => (
        <motion.span
          key={i}
          initial={getInitial()}
          animate={getAnimate()}
          transition={{
            duration: 0.55,
            ease: [0.25, 0.46, 0.45, 0.94],
            delay: (i * delay) / 1000,
          }}
          style={{ display: "inline-block" }}
          aria-hidden
        >
          {token}
          {/* Re-add the space between words */}
          {animateBy === "words" && i < tokens.length - 1 ? "\u00a0" : ""}
        </motion.span>
      ))}
    </span>
  );
};

export default BlurText;
