import React, { useEffect, useRef, useState } from "react";
import Globe from "react-globe.gl";
import * as THREE from "three";
import darkEarthUrl from "@/assets/dark-earth.png";

export function HeroGlobe() {
  const globeRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const animationFrameRef = useRef<number | null>(null);

  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.offsetWidth,
          height: containerRef.current.offsetHeight || 600,
        });
      }
    };
    window.addEventListener("resize", updateSize);
    updateSize();
    // Slight delay to ensure parent has rendered and has a size
    setTimeout(updateSize, 100);
    return () => window.removeEventListener("resize", updateSize);
  }, []);

  // Premium Custom Earth material: Graphite continents, charcoal oceans, copper-amber lights, subtle terrain bump map
  const customMaterial = React.useMemo(() => {
    const loader = new THREE.TextureLoader();

    // Load local high-resolution dark earth texture and topology bump map
    const globeTexture = loader.load(darkEarthUrl);
    const bumpMap = loader.load("https://unpkg.com/three-globe/example/img/earth-topology.png");

    return new THREE.MeshStandardMaterial({
      map: globeTexture,
      bumpMap: bumpMap,
      bumpScale: 1.5, // Subtle terrain texture relief
      roughness: 0.8, // Matte texture for realistic appearance
      metalness: 0.1, // Subtle graphite/slate look
      color: new THREE.Color("#ffffff"), // Keep the original charcoal/graphite colors of the texture
      emissiveMap: globeTexture, // Emissive mapping to isolate glowing city lights
      emissive: new THREE.Color("#ffaa44"), // Warm copper/amber city lights
      emissiveIntensity: 1.8, // Elegant, high-contrast glow
    });
  }, []);

  useEffect(() => {
    if (globeRef.current) {
      // Disable autoRotate on controls since we are rotating the globe group manually
      // to keep camera and lighting coordinates absolutely static.
      const controls = globeRef.current.controls();
      controls.enableZoom = false;
      controls.autoRotate = false;

      // Set initial POV with an altitude of 2.4 (~20% smaller than the original 2.0 altitude)
      globeRef.current.pointOfView({ lat: 22.3193, lng: 114.1694, altitude: 2.4 });

      const scene = globeRef.current.scene();

      // Configure cinematic lights with neutral white lighting to avoid tinting the globe
      // Remove default lights
      const lightsToRemove = scene.children.filter(
        (child: any) => child.type === "AmbientLight" || child.type === "DirectionalLight"
      );
      lightsToRemove.forEach((light: any) => scene.remove(light));

      // Neutral white Key light: Soft key light from the upper left
      const keyLight = new THREE.DirectionalLight("#ffffff", 1.8);
      keyLight.position.set(-200, 200, 150);
      scene.add(keyLight);

      // Neutral white Fill light: Subtle fill light from the opposite side
      const fillLight = new THREE.DirectionalLight("#ffffff", 0.5);
      fillLight.position.set(200, -100, 50);
      scene.add(fillLight);

      // Neutral white Ambient light: Soft ambient light so the entire globe remains visible
      const ambientLight = new THREE.AmbientLight("#ffffff", 0.4);
      scene.add(ambientLight);

      // Custom animation loop to rotate the globe mesh and create a subtle floating motion
      const clock = new THREE.Clock();

      const animate = () => {
        if (globeRef.current) {
          const elapsed = clock.getElapsedTime();

          // Find the main ThreeGlobe group inside the scene
          const globeObj = scene.children.find(
            (child: any) => child.type === "Group"
          );

          if (globeObj) {
            // Linear rotation: 1 complete rotation every 80 seconds
            globeObj.rotation.y = (elapsed * (2 * Math.PI / 80)) % (2 * Math.PI);

            // Extremely subtle floating motion (y-oscillation)
            globeObj.position.y = Math.sin(elapsed * 0.6) * 1.5;

            // Extremely subtle tilt oscillation (x and z axes)
            globeObj.rotation.x = Math.sin(elapsed * 0.4) * 0.015;
            globeObj.rotation.z = Math.cos(elapsed * 0.4) * 0.015;
          }
        }
        animationFrameRef.current = requestAnimationFrame(animate);
      };

      animate();
    }

    return () => {
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, []);

  // Premium global connections (12 strategic routes)
  const connectionArcs = React.useMemo(() => {
    const paths = [
      { startLat: 40.7128, startLng: -74.0060, endLat: 51.5074, endLng: -0.1278, alt: 0.04 }, // New York -> London
      { startLat: 51.5074, startLng: -0.1278, endLat: 50.1109, endLng: 8.6821, alt: 0.02 },  // London -> Frankfurt
      { startLat: 50.1109, startLng: 8.6821, endLat: 25.2048, endLng: 55.2708, alt: 0.05 },  // Frankfurt -> Dubai
      { startLat: 25.2048, startLng: 55.2708, endLat: 19.0760, endLng: 72.8777, alt: 0.03 },  // Dubai -> Mumbai
      { startLat: 19.0760, startLng: 72.8777, endLat: 1.3521, endLng: 103.8198, alt: 0.04 },  // Mumbai -> Singapore
      { startLat: 1.3521, startLng: 103.8198, endLat: 35.6762, endLng: 139.6503, alt: 0.04 }, // Singapore -> Tokyo
      { startLat: 35.6762, startLng: 139.6503, endLat: -33.8688, endLng: 151.2093, alt: 0.06 },// Tokyo -> Sydney
      { startLat: -33.8688, startLng: 151.2093, endLat: 34.0522, endLng: -118.2437, alt: 0.07 },// Sydney -> Los Angeles
      { startLat: 34.0522, startLng: -118.2437, endLat: 40.7128, endLng: -74.0060, alt: 0.04 },// Los Angeles -> New York
      { startLat: 51.5074, startLng: -0.1278, endLat: 35.6762, endLng: 139.6503, alt: 0.07 }, // London -> Tokyo
      { startLat: 48.8566, startLng: 2.3522, endLat: -23.5505, endLng: -46.6333, alt: 0.06 }, // Paris -> Sao Paulo
      { startLat: 31.2304, startLng: 121.4737, endLat: 47.6062, endLng: -122.3321, alt: 0.05 } // Shanghai -> Seattle
    ];

    // Map each path to both a static thin line and a flowing animated particle
    return paths.flatMap((path, i) => {
      const delay = Math.random();
      const speed = 1800 + Math.random() * 1000;
      return [
        {
          ...path,
          id: `static-${i}`,
          isParticle: false,
          color: "rgba(239, 68, 68, 0.25)", // Semi-transparent red
          stroke: 0.85, // Thicker static lines
          dashLength: 1,
          dashGap: 0,
          animateTime: 0
        },
        {
          ...path,
          id: `particle-${i}`,
          isParticle: true,
          color: "#ef4444", // Bright glowing red particle
          stroke: 1.75, // Thicker flowing particles
          dashLength: 0.04, // Very short dash representing a particle
          dashGap: 0.96,
          dashInitialGap: delay,
          animateTime: speed
        }
      ];
    });
  }, []);

  // Compute unique endpoints to render tiny glowing nodes
  const connectionNodes = React.useMemo(() => {
    const nodesMap = new Map<string, { lat: number; lng: number }>();
    const getKey = (lat: number, lng: number) => `${lat.toFixed(2)},${lng.toFixed(2)}`;

    connectionArcs.forEach((arc) => {
      const startKey = getKey(arc.startLat, arc.startLng);
      if (!nodesMap.has(startKey)) {
        nodesMap.set(startKey, { lat: arc.startLat, lng: arc.startLng });
      }
      const endKey = getKey(arc.endLat, arc.endLng);
      if (!nodesMap.has(endKey)) {
        nodesMap.set(endKey, { lat: arc.endLat, lng: arc.endLng });
      }
    });

    return Array.from(nodesMap.values());
  }, [connectionArcs]);

  return (
    <div
      ref={containerRef}
      className="w-full h-full min-h-[400px] md:min-h-[600px] cursor-grab active:cursor-grabbing bg-transparent relative overflow-visible flex items-center justify-center"
    >
      <Globe
        ref={globeRef}
        width={dimensions.width}
        height={dimensions.height}
        backgroundColor="rgba(0,0,0,0)" // Transparent canvas to float on white page
        globeMaterial={customMaterial}

        // Arcs layer configuration
        arcsData={connectionArcs}
        arcStartLat="startLat"
        arcStartLng="startLng"
        arcEndLat="endLat"
        arcEndLng="endLng"
        arcColor="color"
        arcStroke="stroke"
        arcAltitude="alt"
        arcDashLength="dashLength"
        arcDashGap="dashGap"
        arcDashInitialGap="dashInitialGap"
        arcDashAnimateTime="animateTime"

        // Points (glowing nodes) layer configuration
        pointsData={connectionNodes}
        pointLat="lat"
        pointLng="lng"
        pointColor={() => "#ef4444"}
        pointRadius={0.8} // Thicker nodes to match lines
        pointAltitude={0.005} // Physically attached to the surface

        // Cool atmosphere halo
        showAtmosphere={true}
        atmosphereColor="#7dd3fc" // Thin cool atmospheric edge
        atmosphereAltitude={0.09}
      />
    </div>
  );
}
