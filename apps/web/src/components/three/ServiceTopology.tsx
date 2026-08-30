import { useMemo, useRef, useState } from 'react'
import { Canvas, useFrame, type ThreeEvent } from '@react-three/fiber'
import { Billboard, Line, OrbitControls, Text } from '@react-three/drei'
import * as THREE from 'three'
import type { Application } from '@/lib/api/types'
import { normalizeEnum } from '@/lib/utils'
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'

/**
 * Service topology as an orbital graph.
 *
 * Services are grouped into one ring per cloud provider, each ring on its own
 * tilted orbit. This is a genuine read of the registry — ring = provider,
 * node colour = provider, node size = how completely the service is
 * configured — not decoration wearing a 3D costume.
 *
 * Colours come from the validated categorical ramp, in the same fixed
 * provider order the dashboard uses, so a service is the same colour in both
 * places.
 */

const PROVIDER_ORDER = ['gcp', 'aws', 'azure', 'unknown'] as const
type Provider = (typeof PROVIDER_ORDER)[number]

const PROVIDER_COLOR: Record<Provider, string> = {
  gcp: '#0599b3', // series-1
  aws: '#9567e4', // series-2
  azure: '#219c6f', // series-3
  unknown: '#5b6b85',
}

interface NodeDatum {
  app: Application
  provider: Provider
  position: THREE.Vector3
  color: string
  /** 0-1: how many integration fields are filled in. */
  completeness: number
  ringIndex: number
}

function completenessOf(app: Application): number {
  const checks = [
    app.github_repo,
    app.argocd_app_name,
    app.grafana_dashboard,
    app.application_owner,
    app.description,
    app.gke_cluster_name || app.eks_cluster_name || app.aks_cluster_name,
  ]
  const filled = checks.filter((v) => typeof v === 'string' && v.trim().length > 0).length
  return filled / checks.length
}

function ServiceNode({
  node,
  onSelect,
  reducedMotion,
}: {
  node: NodeDatum
  onSelect: (app: Application) => void
  reducedMotion: boolean
}) {
  const meshRef = useRef<THREE.Mesh>(null)
  const [hovered, setHovered] = useState(false)

  const radius = 0.16 + node.completeness * 0.16

  useFrame((state) => {
    const mesh = meshRef.current
    if (!mesh) return
    const target = hovered ? 1.45 : 1
    mesh.scale.lerp(new THREE.Vector3(target, target, target), 0.18)
    if (!reducedMotion) {
      // Tiny bob, phase-shifted per node so the field never pulses in unison.
      mesh.position.y =
        node.position.y + Math.sin(state.clock.elapsedTime * 0.9 + node.position.x) * 0.06
    }
  })

  const handleClick = (event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation()
    onSelect(node.app)
  }

  return (
    <group position={node.position}>
      <mesh
        ref={meshRef}
        onClick={handleClick}
        onPointerOver={(e) => {
          e.stopPropagation()
          setHovered(true)
          document.body.style.cursor = 'pointer'
        }}
        onPointerOut={() => {
          setHovered(false)
          document.body.style.cursor = 'auto'
        }}
      >
        <icosahedronGeometry args={[radius, 1]} />
        <meshStandardMaterial
          color={node.color}
          emissive={node.color}
          emissiveIntensity={hovered ? 1.4 : 0.5}
          roughness={0.35}
          metalness={0.15}
        />
      </mesh>

      {hovered && (
        <Billboard position={[0, radius + 0.42, 0]}>
          <Text
            fontSize={0.24}
            color="#e6edf6"
            anchorX="center"
            anchorY="middle"
            outlineWidth={0.02}
            outlineColor="#05080f"
            maxWidth={4}
          >
            {node.app.application_name ?? 'Unnamed'}
          </Text>
        </Billboard>
      )}
    </group>
  )
}

function Scene({
  apps,
  onSelect,
  reducedMotion,
}: {
  apps: Application[]
  onSelect: (app: Application) => void
  reducedMotion: boolean
}) {
  const groupRef = useRef<THREE.Group>(null)

  const { nodes, rings } = useMemo(() => {
    const byProvider = new Map<Provider, Application[]>()
    for (const app of apps) {
      const raw = normalizeEnum(app.cloud_provider)
      const provider = (PROVIDER_ORDER.includes(raw as Provider) ? raw : 'unknown') as Provider
      const list = byProvider.get(provider) ?? []
      list.push(app)
      byProvider.set(provider, list)
    }

    const built: NodeDatum[] = []
    const ringSpecs: { radius: number; tilt: number; color: string }[] = []

    const present = PROVIDER_ORDER.filter((p) => (byProvider.get(p)?.length ?? 0) > 0)

    present.forEach((provider, ringIndex) => {
      const list = byProvider.get(provider) ?? []
      const ringRadius = 2.1 + ringIndex * 1.25
      const tilt = ringIndex * 0.28 - 0.2
      ringSpecs.push({ radius: ringRadius, tilt, color: PROVIDER_COLOR[provider] })

      list.forEach((app, i) => {
        const angle = (i / Math.max(list.length, 1)) * Math.PI * 2
        const x = Math.cos(angle) * ringRadius
        const z = Math.sin(angle) * ringRadius
        const y = Math.sin(angle) * Math.sin(tilt) * ringRadius * 0.4
        built.push({
          app,
          provider,
          position: new THREE.Vector3(x, y, z),
          color: PROVIDER_COLOR[provider],
          completeness: completenessOf(app),
          ringIndex,
        })
      })
    })

    return { nodes: built, rings: ringSpecs }
  }, [apps])

  useFrame((_, delta) => {
    if (groupRef.current && !reducedMotion) {
      groupRef.current.rotation.y += delta * 0.055
    }
  })

  return (
    <>
      <ambientLight intensity={0.5} />
      <pointLight position={[6, 8, 6]} intensity={45} color="#22d3ee" distance={40} />
      <pointLight position={[-8, -4, -6]} intensity={30} color="#8b5cf6" distance={40} />

      <group ref={groupRef}>
        {/* Orbit guides — one faint circle per provider ring. */}
        {rings.map((ring, i) => {
          const points: [number, number, number][] = []
          for (let a = 0; a <= 64; a += 1) {
            const angle = (a / 64) * Math.PI * 2
            points.push([
              Math.cos(angle) * ring.radius,
              Math.sin(angle) * Math.sin(ring.tilt) * ring.radius * 0.4,
              Math.sin(angle) * ring.radius,
            ])
          }
          return (
            <Line
              key={i}
              points={points}
              color={ring.color}
              lineWidth={1}
              transparent
              opacity={0.18}
            />
          )
        })}

        {/* Core */}
        <mesh>
          <icosahedronGeometry args={[0.55, 2]} />
          <meshStandardMaterial
            color="#0b1220"
            emissive="#22d3ee"
            emissiveIntensity={0.6}
            roughness={0.2}
            metalness={0.6}
            wireframe
          />
        </mesh>

        {nodes.map((node) => (
          <ServiceNode
            key={node.app.id}
            node={node}
            onSelect={onSelect}
            reducedMotion={reducedMotion}
          />
        ))}
      </group>

      <OrbitControls
        enablePan={false}
        enableZoom
        minDistance={5}
        maxDistance={18}
        autoRotate={false}
        // Keep the camera above the equator so labels stay readable.
        minPolarAngle={Math.PI / 5}
        maxPolarAngle={Math.PI / 1.7}
      />
    </>
  )
}

export default function ServiceTopology({
  apps,
  onSelect,
  className,
}: {
  apps: Application[]
  onSelect: (app: Application) => void
  className?: string
}) {
  const reducedMotion = usePrefersReducedMotion()

  return (
    <div className={className}>
      <Canvas camera={{ position: [0, 5.5, 10], fov: 50 }} dpr={[1, 1.75]} gl={{ antialias: true }}>
        <Scene apps={apps} onSelect={onSelect} reducedMotion={reducedMotion} />
      </Canvas>
    </div>
  )
}
