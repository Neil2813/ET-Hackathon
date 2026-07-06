import type { RouteOption } from "@/types/workflow";

export type MonteCarloSummary = {
  runs: number;
  protectedRate: number;
  averageDelayDays: number;
  expectedExposureAvoidedUsd: number;
  routeReliability: number;
  worstCaseLossUsd: number;
  recommendation: "Approve Cape VLCC + SPR bridge" | "Escalate to energy war room";
  probeNode: {
    id: string;
    name: string;
    exposureScore: number;
    dailyThroughputUsd: number;
    stockoutDays: number;
    riskUsd: number;
  };
};

type Rng = () => number;

const createRng = (seed: number): Rng => {
  let value = seed % 2147483647;
  if (value <= 0) value += 2147483646;

  return () => {
    value = (value * 16807) % 2147483647;
    return (value - 1) / 2147483646;
  };
};

const randomBetween = (rng: Rng, min: number, max: number) => min + (max - min) * rng();

export const runDemoMonteCarlo = (
  routes: RouteOption[],
  seed: number,
  runs = 500,
): MonteCarloSummary => {
  const rng = createRng(seed);
  const recommendedRoute = routes.find((route) => route.recommended) ?? routes[0];
  const probeNode = {
    id: `synthetic_probe_${seed}`,
    name: "SPR + Refinery Stress Probe",
    exposureScore: recommendedRoute.recommended ? 86 : 72,
    dailyThroughputUsd: recommendedRoute.recommended ? 612000000 : 420000000,
    stockoutDays: recommendedRoute.recommended ? 9.5 : 6.8,
    riskUsd: 0,
  };
  let protectedRuns = 0;
  let totalDelayDays = 0;
  let totalExposureAvoided = 0;
  let reliableRuns = 0;
  let worstCaseLoss = 0;

  for (let index = 0; index < runs; index += 1) {
    const disruptionDays = randomBetween(rng, 18, 38);
    const portClearanceDrag = randomBetween(rng, 0.6, recommendedRoute.recommended ? 2.2 : 4.1);
    const routeTransitDays =
      recommendedRoute.lane === "Cape of Good Hope"
        ? randomBetween(rng, 20.5, 25.8)
        : randomBetween(rng, 7.2, 13.0);

    const reroutePenalty =
      recommendedRoute.lane === "Cape of Good Hope"
        ? randomBetween(rng, 1.2, 3.8)
        : randomBetween(rng, 4.5, 12.0);
    const arrivalDays = routeTransitDays + portClearanceDrag + reroutePenalty;
    const reserveBridgeDays = probeNode.stockoutDays + randomBetween(rng, 7.5, 13.5);
    const marginDays = reserveBridgeDays - arrivalDays;
    const protectedScenario = marginDays >= 0;
    const continuityGapDays = Math.max(0, arrivalDays - reserveBridgeDays);
    const exposureAvoided = protectedScenario
      ? probeNode.dailyThroughputUsd * randomBetween(rng, 7.5, 12.5)
      : probeNode.dailyThroughputUsd * randomBetween(rng, 1.4, 4.9);
    const lossIfMissed = probeNode.dailyThroughputUsd * Math.max(0.35, continuityGapDays) * randomBetween(rng, 0.45, 0.95);

    if (protectedScenario) protectedRuns += 1;
    if (arrivalDays <= disruptionDays) reliableRuns += 1;

    totalDelayDays += continuityGapDays;
    totalExposureAvoided += exposureAvoided;
    worstCaseLoss = Math.max(worstCaseLoss, lossIfMissed);
  }

  const protectedRate = protectedRuns / runs;
  const routeReliability = reliableRuns / runs;
  probeNode.riskUsd = Math.round(worstCaseLoss);

  return {
    runs,
    protectedRate,
    averageDelayDays: totalDelayDays / runs,
    expectedExposureAvoidedUsd: totalExposureAvoided / runs,
    routeReliability,
    worstCaseLossUsd: worstCaseLoss,
    recommendation:
      protectedRate >= 0.72 && routeReliability >= 0.7 ? "Approve Cape VLCC + SPR bridge" : "Escalate to energy war room",
    probeNode,
  };
};
