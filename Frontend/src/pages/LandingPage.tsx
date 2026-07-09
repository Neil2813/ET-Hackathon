import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { HeroGlobe } from "@/components/HeroGlobe";
import { motion } from "framer-motion";
import CountUp from "@/components/CountUp";
import BlurText from "./BlurText";

const steps = [
  {
    num: "01",
    title: "DETECT",
    shortDesc: "Real-time signals from global intelligence.",
    heading: "Detect Global Disruptions",
    desc: "Monitor geopolitical events, climate risks, supplier disruptions, labor strikes, shipping delays, and intelligence feeds in real time.",
    icon: (
      <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <circle cx={12} cy={12} r={9} strokeWidth={2} strokeDasharray="4 4" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 12m-3 0a3 3 0 1 0 6 0 3 3 0 1 0-6 0" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 2v20M2 12h20" />
      </svg>
    ),
    visual: (
      <div className="space-y-3 w-full">
        <div className="flex items-center justify-between border-b border-slate-100 pb-2">
          <span className="text-[10px] font-bold tracking-wider text-red-500 uppercase">INTEL ALERT</span>
          <span className="text-[10px] text-slate-400">Just Now</span>
        </div>
        <div className="space-y-2.5">
          <div className="bg-white border border-slate-200/80 p-3.5 rounded-lg flex items-start gap-3 shadow-sm">
            <div className="w-2 h-2 rounded-full bg-red-500 mt-1.5 animate-pulse" />
            <div>
              <p className="text-xs font-bold text-slate-800">Port Congestion: Singapore</p>
              <p className="text-[10px] text-slate-500 mt-0.5">Average delay increased by 14.2 hours due to seasonal weather.</p>
            </div>
          </div>
          <div className="bg-white border border-slate-200/80 p-3.5 rounded-lg flex items-start gap-3 shadow-sm opacity-60">
            <div className="w-2 h-2 rounded-full bg-amber-500 mt-1.5" />
            <div>
              <p className="text-xs font-bold text-slate-800">Labor Strike: Rotterdam</p>
              <p className="text-[10px] text-slate-500 mt-0.5">Negotiations ongoing; potential disruption in tier-1 cargo nodes.</p>
            </div>
          </div>
        </div>
      </div>
    )
  },
  {
    num: "02",
    title: "ASSESS",
    shortDesc: "AI-driven impact analysis on your nodes.",
    heading: "Assess Business Impact",
    desc: "Analyze how disruptions affect suppliers, logistics, inventory, and operational continuity using AI-powered risk analysis.",
    icon: (
      <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 002 2h2a2 2 0 002-2z" />
      </svg>
    ),
    visual: (
      <div className="space-y-4 w-full">
        <div className="border border-slate-200 bg-white rounded-lg p-4 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-bold tracking-wider text-slate-500 uppercase">AFFECTED NODES</span>
            <span className="text-[10px] font-bold text-red-500 bg-red-50 px-2 py-0.5 rounded-full">HIGH RISK</span>
          </div>
          <div className="space-y-3 mt-3">
            <div className="space-y-1">
              <div className="flex justify-between items-center text-xs">
                <span className="text-slate-600 font-semibold">Rotterdam Warehouse</span>
                <span className="text-slate-900 font-black">72% Risk Score</span>
              </div>
              <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                <div className="bg-red-500 h-full w-[72%]" />
              </div>
            </div>
            <div className="space-y-1">
              <div className="flex justify-between items-center text-xs">
                <span className="text-slate-600 font-semibold">Frankfurt Logistics Hub</span>
                <span className="text-slate-900 font-black">45% Risk Score</span>
              </div>
              <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                <div className="bg-amber-500 h-full w-[45%]" />
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  },
  {
    num: "03",
    title: "DECIDE",
    shortDesc: "Protocol recommendations by priorities.",
    heading: "Decide Response Strategy",
    desc: "Generate intelligent recommendations ranked by business impact, historical outcomes, and operational priorities.",
    icon: (
      <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
      </svg>
    ),
    visual: (
      <div className="space-y-3 w-full">
        <p className="text-[10px] font-bold tracking-wider text-slate-500 uppercase">RECOMMENDED PROTOCOLS</p>
        <div className="space-y-2.5">
          <div className="border border-red-200 bg-red-50/10 p-3.5 rounded-lg flex items-center justify-between shadow-sm">
            <div>
              <p className="text-xs font-bold text-slate-800">Alternative Carrier: Airfreight</p>
              <p className="text-[10px] text-slate-500 mt-0.5">ETA: -18 hrs | Cost: +$4.2k | Confidence: 94%</p>
            </div>
            <span className="text-[9px] bg-red-500 text-white font-bold px-1.5 py-0.5 rounded-sm">RECOM.</span>
          </div>
          <div className="border border-slate-200 bg-white p-3.5 rounded-lg flex items-center justify-between shadow-sm opacity-70">
            <div>
              <p className="text-xs font-bold text-slate-800">Warehouse Transfer: Lyon Node</p>
              <p className="text-[10px] text-slate-500 mt-0.5">ETA: +12 hrs | Cost: +$1.8k | Confidence: 82%</p>
            </div>
            <span className="text-[9px] border border-slate-200 text-slate-500 font-bold px-1.5 py-0.5 rounded-sm">PLAN B</span>
          </div>
        </div>
      </div>
    )
  },
  {
    num: "04",
    title: "ACT",
    shortDesc: "Automated workflows to reroute.",
    heading: "Execute Response",
    desc: "Automatically trigger workflows, reroute shipments, notify stakeholders, and activate contingency plans.",
    icon: (
      <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
    visual: (
      <div className="space-y-3 w-full">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] font-bold tracking-wider text-slate-500 uppercase">WORKFLOW SEQUENCE</span>
          <span className="text-[10px] font-bold text-green-600 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-ping" />
            Active
          </span>
        </div>
        <div className="space-y-2.5">
          <div className="flex items-center gap-2.5 bg-white border border-slate-200 p-2.5 rounded-lg shadow-sm">
            <span className="w-4.5 h-4.5 rounded-full bg-green-500 text-white text-[10px] flex items-center justify-center font-bold">✓</span>
            <span className="text-xs text-slate-700">Reroute flight RF-204 authorized</span>
          </div>
          <div className="flex items-center gap-2.5 bg-white border border-slate-200 p-2.5 rounded-lg shadow-sm">
            <span className="w-4.5 h-4.5 rounded-full bg-green-500 text-white text-[10px] flex items-center justify-center font-bold">✓</span>
            <span className="text-xs text-slate-700">Vendor API dispatch completed</span>
          </div>
          <div className="flex items-center gap-2.5 bg-white border border-slate-200 p-2.5 rounded-lg shadow-sm">
            <span className="w-4 h-4 rounded-full border border-slate-300 text-slate-400 text-[10px] flex items-center justify-center font-bold animate-spin border-t-red-500"></span>
            <span className="text-xs text-slate-700 font-semibold">Notifying Command Center</span>
          </div>
        </div>
      </div>
    )
  },
  {
    num: "05",
    title: "AUDIT",
    shortDesc: "Immutable logs for compliance.",
    heading: "Audit & Learn",
    desc: "Maintain complete audit trails, monitor outcomes, and continuously improve future response strategies.",
    icon: (
      <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
      </svg>
    ),
    visual: (
      <div className="space-y-3 w-full">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] font-bold tracking-wider text-slate-500 uppercase">AUDIT REGISTER</span>
          <span className="text-[10px] text-slate-400">HASH SH256-42F9</span>
        </div>
        <div className="font-mono text-[10px] bg-slate-900 text-slate-300 p-4 rounded-lg space-y-1.5 overflow-x-auto shadow-inner w-full">
          <p className="text-green-400 font-semibold">[14:12:00Z] SUCCESS: Singapore Reroute</p>
          <p className="text-slate-400">[14:12:01Z] HASH: b49ef3d76e8ac1b9201f98d41... </p>
          <p className="text-slate-400">[14:12:02Z] LOG: Dispatched automated alerts</p>
          <p className="text-amber-400 font-semibold">[14:12:05Z] AUDIT: Record finalized in Vault</p>
        </div>
      </div>
    )
  }
];



const features = [
  {
    title: "Geo-Spatial Intelligence",
    desc: "Real-time mapping of political, climate, and labor unrest risks globally.",
    icon: (
      <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <circle cx={12} cy={12} r={10} strokeWidth={2} />
        <path strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
        <path strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" d="M2 12h20" />
      </svg>
    )
  },
  {
    title: "Counterparty Health",
    desc: "Continuous financial and operational vetting of tier 1 and tier 2 suppliers.",
    icon: (
      <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <rect x="4" y="4" width="16" height="16" rx="2" strokeWidth={2} />
        <path strokeWidth={2} strokeLinecap="round" d="M9 4v16M15 4v16M4 9h16M4 15h16" />
      </svg>
    )
  },
  {
    title: "Dynamic Rerouting",
    desc: "Algorithmic route optimization when primary corridors are compromised.",
    icon: (
      <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    )
  },
  {
    title: "API Integration Hub",
    desc: "Connect existing ERP and WMS data directly into the central fortress.",
    icon: (
      <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
      </svg>
    )
  },
  {
    title: "Quantum Encryption",
    desc: "Secure data transmission across all global logistics nodes.",
    icon: (
      <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <rect x="5" y="11" width="14" height="10" rx="2" ry="2" strokeWidth={2} />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v3M8 11V7a4 4 0 018 0v4" />
      </svg>
    )
  },
  {
    title: "Signal Monitor",
    desc: "Dark web and specialized news tracking for early threat detection.",
    icon: (
      <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <circle cx={12} cy={12} r={10} strokeWidth={2} />
        <path strokeWidth={2} strokeLinecap="round" d="M12 12m-3 0a3 3 0 1 0 6 0 3 3 0 1 0-6 0" />
        <path strokeWidth={2} strokeLinecap="round" d="M12 2v20M2 12h20" />
      </svg>
    )
  }
];

const LandingPage = () => {
  const [activeStep, setActiveStep] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % steps.length);
    }, 6000); // cycle through steps every 6 seconds

    return () => clearInterval(timer);
  }, [activeStep]);
  return (
    <div className="min-h-screen bg-white text-slate-900">
      {/* Navbar */}
      <nav className="fixed top-0 w-full z-50 border border-slate-200 bg-white">
        <div className="container mx-auto flex items-center justify-between h-14 px-6">
          <div className="flex items-center gap-3">
            <img src="/Praecantator.png" alt="Logo" className="w-8 h-8 object-contain" />
            <span className="font-headline text-xl font-bold text-red-500">Praecantator</span>
          </div>
          <div className="hidden md:flex items-center gap-8 text-body-md text-slate-500">
            <a href="#features" className="hover:text-slate-900 transition-colors">Features</a>
            <a href="#how-it-works" className="hover:text-slate-900 transition-colors">How It Works</a>
            <a href="#pricing" className="hover:text-slate-900 transition-colors">Pricing</a>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/login" className="text-body-md text-slate-500 hover:text-slate-900 transition-colors">Sign In</Link>
            <Link to="/register" className="bg-foreground text-white px-4 py-2 rounded-sm text-body-md font-medium hover:opacity-90 transition-opacity">
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative pt-24 pb-24 bg-gradient-to-b from-white to-slate-50 overflow-hidden">
        <div className="container mx-auto px-6 grid lg:grid-cols-2 gap-12 items-center">
          <div>
            <h1 className="text-display-lg leading-tight mb-6 flex flex-wrap gap-x-[0.3em]">
              <BlurText text="Your Supply Chain" delay={180} animateBy="words" direction="top" className="text-slate-900 inline" />
              <BlurText text="Doesn't Stop." delay={180} animateBy="words" direction="top" className="text-red-500 inline" />
              <BlurText text="Neither Should Your Defense." delay={180} animateBy="words" direction="top" className="text-slate-900 inline" />
            </h1>
            <p className="text-body-md text-slate-500 max-w-lg mb-10">
              Praecantator detects global disruptions and executes your response - automatically. From detection to action in minutes, not days.
            </p>
            <div className="flex items-center gap-4">
              <Link to="/register" className="bg-foreground text-white px-6 py-3 rounded-sm font-medium hover:opacity-90 transition-opacity">
                Get Started Free
              </Link>
              <a href="#how-it-works" className="border border-slate-200 bg-white px-6 py-3 rounded-sm font-medium hover:bg-slate-50 transition-colors">
                See it Live
              </a>
            </div>
          </div>
          <div className="relative w-full h-[400px] md:h-[600px] lg:max-w-[85%] lg:ml-auto">
            {/* Soft Red Radial Glow behind the globe */}
            <div
              className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[350px] h-[350px] md:w-[480px] md:h-[480px] rounded-full pointer-events-none"
              style={{
                background: 'radial-gradient(circle, rgba(239, 68, 68, 0.14) 0%, rgba(239, 68, 68, 0.04) 45%, rgba(239, 68, 68, 0) 70%)',
                filter: 'blur(15px)',
                zIndex: 0
              }}
            />
            {/* Faint Ambient Shadow */}
            <div
              className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[220px] h-[220px] md:w-[300px] md:h-[300px] rounded-full pointer-events-none"
              style={{
                background: 'radial-gradient(circle, rgba(15, 23, 42, 0.04) 0%, rgba(15, 23, 42, 0) 70%)',
                zIndex: 0
              }}
            />

            <div className="relative z-10 w-full h-full">
              <HeroGlobe />
            </div>
          </div>
        </div>
        {/* Trust stats */}
        <motion.div
          variants={{
            hidden: {},
            visible: {
              transition: {
                staggerChildren: 0.15
              }
            }
          }}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-10% 0px" }}
          className="container mx-auto px-6 mt-24 grid grid-cols-2 lg:grid-cols-4 gap-4 md:gap-8 max-w-5xl text-center"
        >
          {/* Card 1: Countries Monitored */}
          <motion.div
            variants={{
              hidden: { opacity: 0, y: 30 },
              visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94] } }
            }}
            whileHover={{
              y: -6,
              scale: 1.02,
              boxShadow: "0 10px 30px -10px rgba(0, 0, 0, 0.08), 0 1px 3px rgba(0, 0, 0, 0.02)",
              borderColor: "rgba(239, 68, 68, 0.3)" // subtle red highlight matching existing brand red
            }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className="bg-white border border-slate-200 rounded-2xl p-6 md:p-8 flex flex-col items-center justify-center cursor-default shadow-sm transition-all duration-300"
          >
            <CountUp
              from={0}
              to={139}
              duration={2}
              delay={0}
              direction="up"
              className="font-headline text-3xl md:text-4xl lg:text-5xl font-black text-slate-900"
            />
            <p className="text-label-sm text-red-500 uppercase tracking-widest mt-2">{"Countries Monitored"}</p>
          </motion.div>

          {/* Card 2: Live Data Sources */}
          <motion.div
            variants={{
              hidden: { opacity: 0, y: 30 },
              visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94] } }
            }}
            whileHover={{
              y: -6,
              scale: 1.02,
              boxShadow: "0 10px 30px -10px rgba(0, 0, 0, 0.08), 0 1px 3px rgba(0, 0, 0, 0.02)",
              borderColor: "rgba(239, 68, 68, 0.3)" // subtle red highlight matching existing brand red
            }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className="bg-white border border-slate-200 rounded-2xl p-6 md:p-8 flex flex-col items-center justify-center cursor-default shadow-sm transition-all duration-300"
          >
            <CountUp
              from={0}
              to={4}
              duration={1.8}
              delay={0.2}
              direction="up"
              className="font-headline text-3xl md:text-4xl lg:text-5xl font-black text-slate-900"
            />
            <p className="text-label-sm text-red-500 uppercase tracking-widest mt-2">{"Live Data Sources"}</p>
          </motion.div>

          {/* Card 3: Time to Response */}
          <motion.div
            variants={{
              hidden: { opacity: 0, y: 30 },
              visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94] } }
            }}
            whileHover={{
              y: -6,
              scale: 1.02,
              boxShadow: "0 10px 30px -10px rgba(0, 0, 0, 0.08), 0 1px 3px rgba(0, 0, 0, 0.02)",
              borderColor: "rgba(239, 68, 68, 0.3)" // subtle red highlight matching existing brand red
            }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className="bg-white border border-slate-200 rounded-2xl p-6 md:p-8 flex flex-col items-center justify-center cursor-default shadow-sm transition-all duration-300"
          >
            <div className="flex items-center justify-center gap-1">
              <span className="font-headline text-3xl md:text-4xl lg:text-5xl font-black text-slate-900">
                &lt;
              </span>
              <CountUp
                from={0}
                to={15}
                duration={2}
                delay={0.4}
                direction="up"
                className="font-headline text-3xl md:text-4xl lg:text-5xl font-black text-slate-900"
              />
              <span className="font-headline text-xl md:text-2xl lg:text-3xl font-black text-slate-900">
                min
              </span>
            </div>
            <p className="text-label-sm text-red-500 uppercase tracking-widest mt-2">{"Time to Response"}</p>
          </motion.div>

          {/* Card 4: Threat Detection Rate */}
          <motion.div
            variants={{
              hidden: { opacity: 0, y: 30 },
              visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94] } }
            }}
            whileHover={{
              y: -6,
              scale: 1.02,
              boxShadow: "0 10px 30px -10px rgba(0, 0, 0, 0.08), 0 1px 3px rgba(0, 0, 0, 0.02)",
              borderColor: "rgba(239, 68, 68, 0.3)" // subtle red highlight matching other cards
            }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className="bg-white border border-slate-200 rounded-2xl p-6 md:p-8 flex flex-col items-center justify-center cursor-default shadow-sm transition-all duration-300"
          >
            <div className="flex items-center justify-center gap-1">
              <CountUp
                from={0}
                to={99.9}
                duration={2}
                delay={0.6}
                direction="up"
                className="font-headline text-3xl md:text-4xl lg:text-5xl font-black text-red-500"
              />
              <span className="font-headline text-2xl md:text-3xl lg:text-4xl font-black text-red-500">
                %
              </span>
            </div>
            <p className="text-label-sm text-red-500 uppercase tracking-widest mt-2">Threat Detection Rate</p>
          </motion.div>
        </motion.div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="py-24 bg-slate-50/50">
        <div className="container mx-auto px-6">
          <div className="flex items-center gap-3 mb-16">
            <div className="sentinel-accent-bar h-8" />
            <h2 className="text-headline-md font-bold tracking-tight">How It Works</h2>
          </div>

          {/* Desktop Layout */}
          <div className="hidden lg:grid grid-cols-10 gap-12 items-start">
            {/* Left Timeline (30%) */}
            <div className="col-span-3">
              <div className="relative flex flex-col justify-between h-[360px]">
                {/* Connected vertical line */}
                <div className="absolute left-[28px] top-[16px] bottom-[16px] w-px bg-slate-200 pointer-events-none">
                  <motion.div
                    className="bg-red-500 w-full origin-top"
                    initial={{ scaleY: 0 }}
                    animate={{ scaleY: activeStep / (steps.length - 1) }}
                    transition={{ duration: 0.4, ease: "easeInOut" }}
                    style={{ height: "100%" }}
                  />
                </div>

                {steps.map((step, index) => {
                  const isActive = activeStep === index;
                  return (
                    <motion.div
                      key={step.num}
                      onClick={() => setActiveStep(index)}
                      whileHover={{ x: 6 }}
                      className="relative pl-16 pr-4 py-3 cursor-pointer group select-none flex items-center"
                    >
                      {/* Circle Node */}
                      <div className="absolute left-[12px] top-1/2 -translate-y-1/2 z-10 flex items-center justify-center">
                        <motion.div
                          animate={{
                            backgroundColor: isActive ? "#EF4444" : "#FFFFFF",
                            borderColor: isActive ? "#EF4444" : "#E2E8F0",
                            color: isActive ? "#FFFFFF" : "#64748B",
                            scale: isActive ? 1.15 : 1,
                            boxShadow: isActive ? "0 4px 16px rgba(239, 68, 68, 0.25)" : "none"
                          }}
                          transition={{ duration: 0.3 }}
                          className="w-8 h-8 rounded-full border-2 text-xs font-bold flex items-center justify-center bg-white"
                        >
                          {step.num}
                        </motion.div>
                      </div>

                      {/* Text Content */}
                      <div>
                        <h3 className={`font-headline font-bold text-sm tracking-wider transition-colors duration-300 ${isActive ? "text-red-500" : "text-slate-800 group-hover:text-slate-900"
                          }`}>
                          {step.title}
                        </h3>
                        <p className="text-xs text-slate-500 mt-1 leading-normal">
                          {step.shortDesc}
                        </p>
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            </div>

            {/* Right Information Panel (70%) */}
            <div className="col-span-7">
              <div className="bg-white border border-slate-200/80 rounded-2xl p-8 md:p-10 shadow-sm min-h-[360px] flex flex-col justify-center">
                <motion.div
                  key={activeStep}
                  initial={{ opacity: 0, y: 12, scale: 0.99 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ duration: 0.35, ease: "easeOut" }}
                  className="grid md:grid-cols-2 gap-8 items-center"
                >
                  <div>
                    <div className="flex items-center gap-2.5 text-red-500 mb-6">
                      <div className="p-2 rounded-lg border border-slate-100 bg-red-50/20">
                        {steps[activeStep].icon}
                      </div>
                      <span className="text-label-sm font-bold uppercase tracking-widest text-red-500">STEP {steps[activeStep].num}</span>
                    </div>
                    <h3 className="font-headline text-3xl font-bold tracking-tight text-slate-900 mb-4">
                      {steps[activeStep].heading}
                    </h3>
                    <p className="text-body-md text-slate-500 leading-relaxed">
                      {steps[activeStep].desc}
                    </p>
                  </div>
                  <div className="border border-slate-100 rounded-xl bg-slate-50/50 p-6 shadow-inner min-h-[220px] flex flex-col justify-center">
                    {steps[activeStep].visual}
                  </div>
                </motion.div>
              </div>
            </div>
          </div>

          {/* Mobile Accordion Layout */}
          <div className="lg:hidden space-y-4">
            {steps.map((step, index) => {
              const isOpen = activeStep === index;
              return (
                <div key={step.num} className="border border-slate-200 rounded-xl overflow-hidden bg-white shadow-sm transition-all duration-300">
                  <button
                    onClick={() => setActiveStep(isOpen ? -1 : index)}
                    className="w-full flex items-center justify-between p-5 text-left bg-white hover:bg-slate-50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <span className={`w-8 h-8 rounded-full border flex items-center justify-center font-bold text-sm transition-colors ${isOpen ? "bg-red-500 border-red-500 text-white" : "border-slate-200 text-slate-500"
                        }`}>
                        {step.num}
                      </span>
                      <div>
                        <p className={`font-headline font-bold text-sm tracking-wider ${isOpen ? "text-red-500" : "text-slate-800"}`}>{step.title}</p>
                        <p className="text-label-sm text-slate-500 mt-0.5">{step.shortDesc}</p>
                      </div>
                    </div>
                    <span>{isOpen ? "−" : "+"}</span>
                  </button>
                  {isOpen && (
                    <div className="p-5 border-t border-slate-100 bg-white">
                      <div className="flex items-center gap-2.5 text-red-500 mb-4">
                        <div className="p-2 rounded-lg border border-slate-100 bg-red-50/20">
                          {step.icon}
                        </div>
                        <span className="text-label-sm font-bold uppercase tracking-wider">STEP {step.num}</span>
                      </div>
                      <h3 className="font-headline text-lg font-bold text-slate-900 mb-2">{step.heading}</h3>
                      <p className="text-body-md text-slate-500 mb-6 leading-relaxed">{step.desc}</p>
                      <div className="border border-slate-100 p-4 rounded-xl bg-slate-50">
                        {step.visual}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-24 bg-slate-50/30">
        <div className="container mx-auto px-6">
          <div className="flex items-center justify-between mb-12">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <div className="sentinel-accent-bar h-8" />
                <h2 className="text-headline-md font-bold">Tactical Capabilities</h2>
              </div>
              <p className="text-body-md text-slate-500 ml-4">A complete arsenal of tools designed to outpace volatility and secure every link in your chain.</p>
            </div>
            <span className="text-label-sm text-red-500 uppercase tracking-widest hidden md:block">All Features</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8">
            {features.map((feat) => (
              <div
                key={feat.title}
                className="bg-white border border-slate-100 rounded-[20px] p-8 shadow-[0_4px_20px_-4px_rgba(15,23,42,0.04)] transition-all duration-300 hover:-translate-y-1.5 hover:shadow-[0_12px_24px_-4px_rgba(15,23,42,0.07)] flex flex-col items-start text-left cursor-default"
              >
                <div className="w-10 h-10 rounded-lg bg-red-50 border border-red-100 flex items-center justify-center mb-6 text-red-500">
                  {feat.icon}
                </div>
                <h3 className="font-headline font-bold text-lg text-slate-900 mb-2">{feat.title}</h3>
                <p className="text-sm text-slate-500 leading-relaxed">{feat.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-24 border-t border-b border-slate-200 bg-slate-50/50">
        <div className="container mx-auto px-6 text-center">
          <h2 className="text-headline-md font-bold mb-2">Deployment Tiers</h2>
          <p className="text-body-md text-slate-500 mb-12">Scalable protection for single-node operations to global enterprises.</p>
          <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto">
            {[
              {
                name: "STANDARD", price: "$2,400", period: "/mo", recommended: false,
                features: ["10 Monitored Nodes", "24/7 Intelligence Feed", "Standard API Access"],
                cta: "Select Deployment",
              },
              {
                name: "PROFESSIONAL", price: "$8,500", period: "/mo", recommended: true,
                features: ["50 Monitored Nodes", "Predictive Risk Modelling", "Priority Incident Response", "Full Audit History"],
                cta: "Launch Fortress",
              },
              {
                name: "ENTERPRISE", price: "CUSTOM", period: "", recommended: false,
                features: ["Unlimited Nodes", "Custom Signal Integration", "On-Prem Deployment Options"],
                cta: "Contact Command",
              },
            ].map((tier) => (
              <div key={tier.name} className={`border border-slate-200 bg-slate-50 rounded-lg p-8 text-left relative ${tier.recommended ? "ring-1 ring-red-500" : ""}`}>
                {tier.recommended && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-red-500 px-3 py-1 rounded-sm text-label-sm font-bold text-white uppercase">
                    Recommended
                  </span>
                )}
                <p className="text-label-sm uppercase tracking-widest text-slate-500 mb-4">{tier.name}</p>
                <p className="font-headline text-4xl font-bold mb-1">{tier.price}<span className="text-body-md text-slate-500">{tier.period}</span></p>
                <ul className="mt-6 space-y-3 mb-8">
                  {tier.features.map((f) => (
                    <li key={f} className="flex items-center gap-2 text-body-md">
                      <span className="text-red-500">✓</span> {f}
                    </li>
                  ))}
                </ul>
                <Link
                  to="/register"
                  className={`block w-full text-center py-3 rounded-sm font-medium transition-all ${tier.recommended
                    ? "bg-red-500 text-white hover:opacity-90"
                    : "border border-slate-200 bg-white hover:bg-slate-50"
                    }`}
                >
                  {tier.cta}
                </Link>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-200 py-8">
        <div className="container mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-label-sm text-slate-500 uppercase tracking-widest">© 2026 Praecantator. All Rights Reserved.</p>
          <div className="flex gap-6 text-label-sm text-slate-500 uppercase tracking-widest">
            <a href="#" className="hover:text-slate-900 transition-colors">Terms of Service</a>
            <a href="#" className="hover:text-slate-900 transition-colors">Privacy Policy</a>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
