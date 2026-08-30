import { useMemo, useRef } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'
import { isWebGLAvailable } from './CanvasBoundary'

/**
 * Ambient particle field.
 *
 * All motion happens in the vertex shader — the CPU only uploads a time
 * uniform per frame, so this stays flat regardless of particle count. The
 * previous implementation animated per-object on the CPU and disposed nothing.
 *
 * Deliberately restrained: this sits *behind* content, so it stays low
 * contrast and slow. A background that competes with the UI is a bug.
 */

const VERTEX = /* glsl */ `
  uniform float uTime;
  uniform vec2  uPointer;
  uniform float uSize;

  attribute float aScale;
  attribute float aSpeed;
  attribute vec3  aTint;

  varying float vAlpha;
  varying vec3  vTint;

  void main() {
    vec3 pos = position;

    // Slow vertical drift, wrapped so the field never empties.
    pos.y = mod(pos.y + uTime * aSpeed * 0.35 + 30.0, 60.0) - 30.0;

    // Gentle lateral sway, offset per-particle so the field never pulses in unison.
    pos.x += sin(uTime * 0.18 + pos.y * 0.09) * 1.1;
    pos.z += cos(uTime * 0.13 + pos.x * 0.07) * 0.8;

    // Parallax toward the pointer — subtle, and scaled by depth so the
    // field reads as volumetric rather than as a flat sheet.
    float depth = smoothstep(-30.0, 20.0, pos.z);
    pos.xy += uPointer * depth * 2.6;

    vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
    gl_Position = projectionMatrix * mvPosition;

    // Perspective-correct size, clamped so near particles don't become discs.
    gl_PointSize = min(uSize * aScale * (26.0 / -mvPosition.z), 7.0);

    // Fade at both depth extremes to hide the wrap and the far plane.
    float distanceFade = 1.0 - smoothstep(24.0, 62.0, -mvPosition.z);
    vAlpha = distanceFade * (0.28 + aScale * 0.42);
    vTint  = aTint;
  }
`

const FRAGMENT = /* glsl */ `
  varying float vAlpha;
  varying vec3  vTint;

  void main() {
    // Round, soft-edged point. Discarding early is cheaper than blending
    // a fully transparent fragment.
    vec2 uv = gl_PointCoord - 0.5;
    float d = length(uv);
    if (d > 0.5) discard;

    float falloff = 1.0 - smoothstep(0.0, 0.5, d);
    falloff = pow(falloff, 1.6);

    gl_FragColor = vec4(vTint, falloff * vAlpha);
  }
`

function Particles({ count = 1400, reducedMotion = false }: { count?: number; reducedMotion?: boolean }) {
  const pointsRef = useRef<THREE.Points>(null)
  const materialRef = useRef<THREE.ShaderMaterial>(null)
  const pointer = useRef(new THREE.Vector2(0, 0))
  const smoothedPointer = useRef(new THREE.Vector2(0, 0))
  const { viewport } = useThree()

  const { geometry, uniforms } = useMemo(() => {
    const positions = new Float32Array(count * 3)
    const scales = new Float32Array(count)
    const speeds = new Float32Array(count)
    const tints = new Float32Array(count * 3)

    // Brand cyan and a violet accent, mostly cyan — a two-hue field reads as
    // depth; three or more reads as confetti.
    const cyan = new THREE.Color('#22d3ee')
    const violet = new THREE.Color('#8b5cf6')
    const deep = new THREE.Color('#0e7490')

    for (let i = 0; i < count; i += 1) {
      positions[i * 3] = (Math.random() - 0.5) * 70
      positions[i * 3 + 1] = (Math.random() - 0.5) * 60
      positions[i * 3 + 2] = (Math.random() - 0.5) * 50 - 10

      // Bias small: a few large particles carry the depth read.
      scales[i] = Math.pow(Math.random(), 2.2) * 0.9 + 0.1
      speeds[i] = 0.4 + Math.random() * 1.1

      const roll = Math.random()
      const color = roll > 0.88 ? violet : roll > 0.45 ? cyan : deep
      tints[i * 3] = color.r
      tints[i * 3 + 1] = color.g
      tints[i * 3 + 2] = color.b
    }

    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    geo.setAttribute('aScale', new THREE.BufferAttribute(scales, 1))
    geo.setAttribute('aSpeed', new THREE.BufferAttribute(speeds, 1))
    geo.setAttribute('aTint', new THREE.BufferAttribute(tints, 3))

    return {
      geometry: geo,
      uniforms: {
        uTime: { value: 0 },
        uPointer: { value: new THREE.Vector2(0, 0) },
        uSize: { value: 2.4 },
      },
    }
  }, [count])

  useFrame((state, delta) => {
    const material = materialRef.current
    if (!material) return

    // Reduced motion: hold the field static but keep it rendered.
    if (!reducedMotion) {
      material.uniforms.uTime.value += Math.min(delta, 0.05)
    }

    pointer.current.set(
      (state.pointer.x * viewport.width) / 90,
      (state.pointer.y * viewport.height) / 90,
    )
    // Critically damped follow — raw pointer values make the field twitch.
    smoothedPointer.current.lerp(pointer.current, 0.045)
    material.uniforms.uPointer.value.copy(smoothedPointer.current)

    if (pointsRef.current && !reducedMotion) {
      pointsRef.current.rotation.y += delta * 0.012
    }
  })

  return (
    <points ref={pointsRef} geometry={geometry} frustumCulled={false}>
      <shaderMaterial
        ref={materialRef}
        uniforms={uniforms}
        vertexShader={VERTEX}
        fragmentShader={FRAGMENT}
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  )
}

export interface AmbientFieldProps {
  className?: string
  density?: 'low' | 'medium' | 'high'
}

export default function AmbientField({ className, density = 'medium' }: AmbientFieldProps) {
  const reducedMotion = usePrefersReducedMotion()
  const count = density === 'low' ? 700 : density === 'high' ? 2200 : 1400

  // Don't even mount the Canvas when there is no GL context to be had.
  // The CanvasBoundary above catches the case where creation fails anyway.
  if (!isWebGLAvailable()) return null

  return (
    <div className={className} aria-hidden>
      <Canvas
        camera={{ position: [0, 0, 34], fov: 62 }}
        // Cap DPR — a 3x retina display would otherwise quadruple fragment cost
        // for a background nobody is looking at directly.
        dpr={[1, 1.6]}
        gl={{
          antialias: false,
          alpha: true,
          powerPreference: 'low-power',
        }}
        // R3F pauses rendering when the canvas leaves the viewport / tab is hidden.
        frameloop={reducedMotion ? 'demand' : 'always'}
      >
        <Particles count={count} reducedMotion={reducedMotion} />
        <fog attach="fog" args={['#05070d', 30, 80]} />
      </Canvas>
    </div>
  )
}
