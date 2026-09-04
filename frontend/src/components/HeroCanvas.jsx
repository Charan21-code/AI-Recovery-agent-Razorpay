import React, { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Float } from '@react-three/drei';
import * as THREE from 'three';

const ParticleNetwork = () => {
  const pointsRef = useRef();
  const linesRef = useRef();

  // Generate random points in a sphere
  const count = 300;
  const radius = 10;
  
  const [positions, lines, colors] = useMemo(() => {
    const pos = new Float32Array(count * 3);
    const col = new Float32Array(count * 3);
    const color = new THREE.Color();
    
    for (let i = 0; i < count; i++) {
      const theta = Math.random() * 2 * Math.PI;
      const phi = Math.acos((Math.random() * 2) - 1);
      const r = radius * Math.cbrt(Math.random());
      
      const x = r * Math.sin(phi) * Math.cos(theta);
      const y = r * Math.sin(phi) * Math.sin(theta);
      const z = r * Math.cos(phi);
      
      pos[i * 3] = x;
      pos[i * 3 + 1] = y;
      pos[i * 3 + 2] = z;
      
      // Gradient from Violet to Cyan to Mint
      const normalizedY = (y + radius) / (radius * 2);
      if (normalizedY > 0.6) {
        color.set('#00F5A0'); // Mint top
      } else if (normalizedY > 0.3) {
        color.set('#00CEFF'); // Cyan middle
      } else {
        color.set('#6C5CE7'); // Violet bottom
      }
      
      col[i * 3] = color.r;
      col[i * 3 + 1] = color.g;
      col[i * 3 + 2] = color.b;
    }
    
    // Create connection lines
    const lineIndices = [];
    const connectDistance = 3.5;
    
    for (let i = 0; i < count; i++) {
      for (let j = i + 1; j < count; j++) {
        const dx = pos[i * 3] - pos[j * 3];
        const dy = pos[i * 3 + 1] - pos[j * 3 + 1];
        const dz = pos[i * 3 + 2] - pos[j * 3 + 2];
        const dist = Math.sqrt(dx*dx + dy*dy + dz*dz);
        
        if (dist < connectDistance) {
          lineIndices.push(i, j);
        }
      }
    }
    
    return [pos, new Uint16Array(lineIndices), col];
  }, [count, radius]);

  useFrame((state, delta) => {
    if (pointsRef.current && linesRef.current) {
      pointsRef.current.rotation.y += delta * 0.05;
      pointsRef.current.rotation.x += delta * 0.02;
      linesRef.current.rotation.y += delta * 0.05;
      linesRef.current.rotation.x += delta * 0.02;
    }
  });

  return (
    <group>
      <points ref={pointsRef}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            count={positions.length / 3}
            array={positions}
            itemSize={3}
          />
          <bufferAttribute
            attach="attributes-color"
            count={colors.length / 3}
            array={colors}
            itemSize={3}
          />
        </bufferGeometry>
        <pointsMaterial
          size={0.15}
          vertexColors
          transparent
          opacity={0.8}
          sizeAttenuation
        />
      </points>
      <lineSegments ref={linesRef}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            count={positions.length / 3}
            array={positions}
            itemSize={3}
          />
          <bufferAttribute
            attach="index"
            count={lines.length}
            array={lines}
            itemSize={1}
          />
        </bufferGeometry>
        <lineBasicMaterial
          color="#A29BFE"
          transparent
          opacity={0.15}
          depthWrite={false}
        />
      </lineSegments>
    </group>
  );
};

export default function HeroCanvas() {
  return (
    <div style={{ width: '100%', height: '100%', position: 'absolute', top: 0, left: 0 }}>
      <Canvas camera={{ position: [0, 0, 15], fov: 60 }}>
        <fog attach="fog" args={['#050508', 10, 25]} />
        <ambientLight intensity={0.5} />
        <Float speed={1.5} rotationIntensity={0.5} floatIntensity={0.5}>
          <ParticleNetwork />
        </Float>
        <OrbitControls 
          enableZoom={false} 
          enablePan={false}
          autoRotate 
          autoRotateSpeed={0.5}
        />
      </Canvas>
    </div>
  );
}
