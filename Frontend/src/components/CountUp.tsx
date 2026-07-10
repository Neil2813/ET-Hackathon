import { useEffect, useRef } from "react";
import { motion, useMotionValue, useTransform, animate, useInView } from "framer-motion";

interface CountUpProps {
  from?: number;
  to: number;
  duration?: number;
  delay?: number;
  direction?: "up" | "down";
  className?: string;
}

export default function CountUp({
  from = 0,
  to,
  duration = 2,
  delay = 0,
  direction = "up",
  className = "",
}: CountUpProps) {
  const ref = useRef<HTMLSpanElement>(null);
  // Animates when the element is in the viewport (triggers once)
  const isInView = useInView(ref, { once: true, margin: "-10% 0px" });

  const count = useMotionValue(direction === "up" ? from : to);
  
  // Format the number to round it to the nearest integer, or support decimals if target value has them
  const rounded = useTransform(count, (latest) => {
    const hasDecimals = to % 1 !== 0;
    return hasDecimals ? latest.toFixed(1) : Math.round(latest).toString();
  });

  useEffect(() => {
    if (!isInView) return;

    // Delayed trigger for staggered visual appearance
    const timer = setTimeout(() => {
      animate(count, direction === "up" ? to : from, {
        duration: duration,
        ease: "easeOut", // Smooth ease-out animation
      });
    }, delay * 1000);

    return () => clearTimeout(timer);
  }, [isInView, count, from, to, duration, delay, direction]);

  return (
    <motion.span ref={ref} className={className}>
      {rounded}
    </motion.span>
  );
}
