import { useEffect, useRef } from "react";
import * as THREE from "three";

const EARTH_TEXTURE = "https://threejs.org/examples/textures/planets/earth_atmos_2048.jpg";
const EARTH_NORMAL = "https://threejs.org/examples/textures/planets/earth_normal_2048.jpg";

export default function EarthGlobe() {
  const mountRef = useRef(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return undefined;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);
    camera.position.z = 3.2;

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    mount.appendChild(renderer.domElement);

    const ambient = new THREE.AmbientLight(0x6fdcff, 1.6);
    scene.add(ambient);
    const keyLight = new THREE.DirectionalLight(0xffffff, 2.4);
    keyLight.position.set(-3, 2, 4);
    scene.add(keyLight);
    const rimLight = new THREE.PointLight(0x19d9ff, 4, 8);
    rimLight.position.set(2, 0, 3);
    scene.add(rimLight);

    const loader = new THREE.TextureLoader();
    const earthTexture = loader.load(EARTH_TEXTURE);
    const normalTexture = loader.load(EARTH_NORMAL);
    const earth = new THREE.Mesh(
      new THREE.SphereGeometry(1, 96, 96),
      new THREE.MeshPhongMaterial({ map: earthTexture, normalMap: normalTexture, normalScale: new THREE.Vector2(0.35, 0.35), shininess: 18, specular: new THREE.Color(0x54dfff) }),
    );
    earth.rotation.y = -0.55;
    scene.add(earth);

    const gridGeometry = new THREE.WireframeGeometry(new THREE.SphereGeometry(1.012, 32, 16));
    const grid = new THREE.LineSegments(gridGeometry, new THREE.LineBasicMaterial({ color: 0x5be7ff, transparent: true, opacity: 0.22 }));
    scene.add(grid);

    const atmosphere = new THREE.Mesh(
      new THREE.SphereGeometry(1.045, 64, 64),
      new THREE.MeshBasicMaterial({ color: 0x28cfff, transparent: true, opacity: 0.13, side: THREE.BackSide }),
    );
    scene.add(atmosphere);

    const starPositions = new Float32Array(900);
    for (let index = 0; index < starPositions.length; index += 3) {
      const radius = 3.8 + Math.random() * 2.5;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      starPositions[index] = radius * Math.sin(phi) * Math.cos(theta);
      starPositions[index + 1] = radius * Math.sin(phi) * Math.sin(theta);
      starPositions[index + 2] = radius * Math.cos(phi);
    }
    const starsGeometry = new THREE.BufferGeometry();
    starsGeometry.setAttribute("position", new THREE.BufferAttribute(starPositions, 3));
    const stars = new THREE.Points(starsGeometry, new THREE.PointsMaterial({ color: 0x8beaff, size: 0.018, transparent: true, opacity: 0.7 }));
    scene.add(stars);

    const resize = () => {
      const width = mount.clientWidth || 640;
      const height = mount.clientHeight || 640;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(mount);

    let animationFrame;
    const animate = () => {
      earth.rotation.y += 0.0024;
      stars.rotation.y -= 0.00012;
      renderer.render(scene, camera);
      animationFrame = requestAnimationFrame(animate);
    };
    animate();

    return () => {
      cancelAnimationFrame(animationFrame);
      observer.disconnect();
      earthTexture.dispose();
      normalTexture.dispose();
      earth.geometry.dispose();
      earth.material.dispose();
      gridGeometry.dispose();
      grid.material.dispose();
      atmosphere.geometry.dispose();
      atmosphere.material.dispose();
      starsGeometry.dispose();
      stars.material.dispose();
      renderer.dispose();
      mount.removeChild(renderer.domElement);
    };
  }, []);

  return <div ref={mountRef} className="earth-globe" aria-hidden="true" />;
}
