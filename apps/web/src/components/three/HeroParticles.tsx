import { useRef, useMemo } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { isWebGLAvailable } from './CanvasBoundary'

// ── logo shape generator ────────────────────────────────────────────────────
function hexEdgePoints(cx: number, cy: number, r: number, n: number, z = 0) {
  const pts: number[] = []
  for (let i = 0; i < n; i++) {
    const t = i / n
    const edge = Math.floor(t * 6)
    const et = (t * 6) % 1
    const a1 = (edge / 6) * Math.PI * 2 - Math.PI / 6
    const a2 = ((edge + 1) / 6) * Math.PI * 2 - Math.PI / 6
    pts.push(
      cx + Math.cos(a1) * r * (1 - et) + Math.cos(a2) * r * et,
      cy + Math.sin(a1) * r * (1 - et) + Math.sin(a2) * r * et,
      z,
    )
  }
  return pts
}

function buildLogoPositions(total: number): Float32Array {
  const outerN = Math.floor(total * 0.44)
  const innerN = Math.floor(total * 0.34)
  const diamN  = total - outerN - innerN

  const outer = hexEdgePoints(0, 0, 1.0,  outerN, 0)
  const inner = hexEdgePoints(0, 0, 0.62, innerN, 0.1)

  // diamond (4-sided) inside
  const diam: number[] = []
  for (let i = 0; i < diamN; i++) {
    const t = i / diamN
    const side = Math.floor(t * 4)
    const st = (t * 4) % 1
    const corners = [
      [0, 0.38, 0.2], [0.33, 0.14, 0.2],
      [0, -0.1, 0.2], [-0.33, 0.14, 0.2],
    ]
    const [ax, ay, az] = corners[side]
    const [bx, by, bz] = corners[(side + 1) % 4]
    diam.push(ax * (1 - st) + bx * st, ay * (1 - st) + by * st, az * (1 - st) + bz * st)
  }

  return new Float32Array([...outer, ...inner, ...diam])
}

// ── shaders ─────────────────────────────────────────────────────────────────
const VERT = /* glsl */ `
  uniform float uTime;
  uniform float uMorph;      // 0=scattered  1=logo
  uniform vec2  uMouse;      // NDC [-1,1]
  uniform float uHover;      // 0→1

  attribute vec3 aFree;      // scattered rest position
  attribute vec3 aLogo;      // logo rest position
  attribute float aScale;
  attribute vec3 aTint;

  varying float vAlpha;
  varying vec3  vTint;

  void main() {
    // lerp between free drift and logo shape
    vec3 pos = mix(aFree, aLogo, uMorph);

    // gentle idle drift (only in free region)
    float driftAmt = 1.0 - uMorph * 0.7;
    pos.x += sin(uTime * 0.4 + aFree.y * 2.1) * 0.06 * driftAmt;
    pos.y += cos(uTime * 0.3 + aFree.x * 1.7) * 0.06 * driftAmt;
    pos.z += sin(uTime * 0.25 + aFree.z * 3.0) * 0.04 * driftAmt;

    // mouse repulsion (world-space, logo is in ~[-1,1] range)
    vec2 mWorld = uMouse * 1.8;
    vec2 delta  = pos.xy - mWorld;
    float dist  = length(delta);
    float rep   = uHover * 0.55 / (dist * dist + 0.08);
    pos.xy += normalize(delta) * rep * smoothstep(1.2, 0.0, dist);

    vec4 mv = modelViewMatrix * vec4(pos, 1.0);
    gl_Position  = projectionMatrix * mv;
    gl_PointSize = min(aScale * 180.0 / -mv.z, 5.0);

    float fade = 1.0 - smoothstep(18.0, 28.0, -mv.z);
    vAlpha = fade * mix(0.25 + aScale * 0.55, 0.85, uMorph * 0.6);
    vTint  = aTint;
  }
`

const FRAG = /* glsl */ `
  varying float vAlpha;
  varying vec3  vTint;

  void main() {
    vec2 uv = gl_PointCoord - 0.5;
    float d = length(uv);
    if (d > 0.5) discard;
    float f = pow(1.0 - smoothstep(0.0, 0.5, d), 1.8);
    gl_FragColor = vec4(vTint, f * vAlpha);
  }
`

// ── inner scene ──────────────────────────────────────────────────────────────
function Scene({ count = 2400, morphed }: { count: number; morphed: boolean }) {
  const matRef  = useRef<THREE.ShaderMaterial>(null)
  const { viewport, pointer } = useThree()
  const morphTarget = useRef(0)

  const { geo, uniforms } = useMemo(() => {
    const logo   = buildLogoPositions(count)
    const free   = new Float32Array(count * 3)
    const scales = new Float32Array(count)
    const tints  = new Float32Array(count * 3)
    const cyan   = new THREE.Color('#06b6d4')
    const violet = new THREE.Color('#8b5cf6')
    const dim    = new THREE.Color('#0e7490')

    for (let i = 0; i < count; i++) {
      const r = 3.5 + Math.random() * 8
      const θ = Math.random() * Math.PI * 2
      const φ = Math.acos(2 * Math.random() - 1)
      free[i * 3]     = r * Math.sin(φ) * Math.cos(θ)
      free[i * 3 + 1] = r * Math.sin(φ) * Math.sin(θ)
      free[i * 3 + 2] = (Math.random() - 0.5) * 6 - 4
      scales[i] = Math.pow(Math.random(), 2.4) * 0.9 + 0.1
      const c = Math.random() > 0.82 ? violet : Math.random() > 0.4 ? cyan : dim
      tints[i * 3] = c.r; tints[i * 3 + 1] = c.g; tints[i * 3 + 2] = c.b
    }

    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(logo, 3))
    g.setAttribute('aLogo',    new THREE.BufferAttribute(logo, 3))
    g.setAttribute('aFree',    new THREE.BufferAttribute(free, 3))
    g.setAttribute('aScale',   new THREE.BufferAttribute(scales, 1))
    g.setAttribute('aTint',    new THREE.BufferAttribute(tints, 3))

    return {
      geo: g,
      uniforms: {
        uTime:  { value: 0 },
        uMorph: { value: 0 },
        uMouse: { value: new THREE.Vector2() },
        uHover: { value: 0 },
      },
    }
  }, [count])

  useFrame((_, delta) => {
    const m = matRef.current
    if (!m) return
    m.uniforms.uTime.value += Math.min(delta, 0.05)

    // smooth morph toward target
    morphTarget.current = morphed ? 1 : 0
    m.uniforms.uMorph.value += (morphTarget.current - m.uniforms.uMorph.value) * 0.04

    // mouse
    m.uniforms.uMouse.value.set(
      (pointer.x * viewport.width)  / (viewport.width  * 1.2),
      (pointer.y * viewport.height) / (viewport.height * 1.2),
    )
    m.uniforms.uHover.value += (1 - m.uniforms.uHover.value) * 0.06
  })

  return (
    <points geometry={geo} frustumCulled={false}>
      <shaderMaterial
        ref={matRef}
        uniforms={uniforms}
        vertexShader={VERT}
        fragmentShader={FRAG}
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  )
}

// ── public component ─────────────────────────────────────────────────────────
export interface HeroParticlesProps {
  className?: string
  morphed?: boolean
  count?: number
}

export default function HeroParticles({
  className,
  morphed = false,
  count = 2400,
}: HeroParticlesProps) {
  if (!isWebGLAvailable()) return null
  return (
    <div className={className} aria-hidden>
      <Canvas
        camera={{ position: [0, 0, 5], fov: 55 }}
        dpr={[1, 1.5]}
        gl={{ antialias: false, alpha: true, powerPreference: 'low-power' }}
      >
        <Scene count={count} morphed={morphed} />
      </Canvas>
    </div>
  )
}
