import { useEffect, useRef, useState } from "react";

interface CountUpProps {
  from?: number;
  to: number;
  duration?: number;
  /** Delay in seconds before the animation starts */
  delay?: number;
  direction?: "up" | "down";
  className?: string;
}

function easeOutQuart(t: number): number {
  return 1 - Math.pow(1 - t, 4);
}

const CountUp = ({
  from = 0,
  to,
  duration = 2,
  delay = 0,
  className = "",
}: CountUpProps) => {
  const [value, setValue] = useState(from);
  const ref = useRef<HTMLSpanElement>(null);
  const hasAnimated = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !hasAnimated.current) {
          hasAnimated.current = true;
          observer.disconnect();

          const startTime = performance.now() + delay * 1000;
          const range = to - from;
          const isDecimal = !Number.isInteger(to) || !Number.isInteger(from);

          let raf: number;

          const tick = (now: number) => {
            if (now < startTime) {
              raf = requestAnimationFrame(tick);
              return;
            }
            const elapsed = now - startTime;
            const progress = Math.min(elapsed / (duration * 1000), 1);
            const eased = easeOutQuart(progress);
            const current = from + range * eased;
            setValue(isDecimal ? Math.round(current * 10) / 10 : Math.round(current));

            if (progress < 1) {
              raf = requestAnimationFrame(tick);
            }
          };

          raf = requestAnimationFrame(tick);
          return () => cancelAnimationFrame(raf);
        }
      },
      { threshold: 0.3 }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [from, to, duration, delay]);

  // Format: show one decimal place only when the target itself has decimals
  const formatted = !Number.isInteger(to)
    ? value.toFixed(1)
    : value.toLocaleString();

  return (
    <span ref={ref} className={className}>
      {formatted}
    </span>
  );
};

export default CountUp;
