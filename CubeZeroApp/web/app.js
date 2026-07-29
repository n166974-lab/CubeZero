import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";


const STRINGS = {
  en: {
    settings: "Settings",
    settingsTitle: "Settings",
    settingsDescription: "Customize CubeZero",
    language: "Interface language",
    apply: "Apply",
    cancel: "Cancel",
    scramble: "SCRAMBLE",
    solve: "SOLVE",
    reset: "RESET CUBE",
    solverStatus: "SOLVER STATUS",
    command: "COMMAND",
    alphaSubtitle: "3×3 beam + depth-5 database",
    betaSubtitle: "2×2 experimental solver",
    alphaDetail: "Automatic 40-move scramble · Beam width 20,000 · Depth 100",
    betaDetail: "Automatic 20-move scramble · Color-value beam search",
    ready: "Ready to play",
    readyPrompt: "Press SCRAMBLE to create a new automatic scramble.",
    orbit: "Drag to orbit · Scroll to zoom",
    scrambling: "Scrambling…",
    scrambleProgress: "Animating {count} automatic moves.",
    scrambleReady: "Scramble ready",
    solvePrompt: "Press SOLVE to start the solver and live thinking timer.",
    alreadySolved: "Already solved",
    newGame: "Press SCRAMBLE to begin a new game.",
    solverRunning: "The Python solver is running in the background.",
    thinking: "Thinking for {seconds} seconds…",
    noSolution: "No solution after {seconds} seconds",
    solvedIn: "Solved in {seconds} seconds",
    foundSolution: "Found {count} moves. Animating the solution now.",
    cubeSolved: "Cube solved",
    verified: "Verified solved. Press SCRAMBLE to play again.",
    resetDone: "Cube reset to solved.",
    bridgeError: "Could not communicate with the Python solver.",
  },
  zh: {
    settings: "设置",
    settingsTitle: "设置",
    settingsDescription: "自定义 CubeZero",
    language: "界面语言",
    apply: "应用",
    cancel: "取消",
    scramble: "打乱",
    solve: "求解",
    reset: "重置魔方",
    solverStatus: "求解器状态",
    command: "运行命令",
    alphaSubtitle: "3×3 束搜索与五步数据库求解器",
    betaSubtitle: "2×2 实验性求解器",
    alphaDetail: "自动打乱 40 步 · 束宽 20,000 · 深度 100",
    betaDetail: "自动打乱 20 步 · 颜色评分束搜索",
    ready: "可以开始",
    readyPrompt: "点击“打乱”生成新的自动打乱。",
    orbit: "拖动旋转视角 · 滚轮缩放",
    scrambling: "正在打乱…",
    scrambleProgress: "正在播放 {count} 步自动打乱。",
    scrambleReady: "打乱完成",
    solvePrompt: "点击“求解”启动求解器和实时计时。",
    alreadySolved: "魔方已经复原",
    newGame: "点击“打乱”开始新游戏。",
    solverRunning: "Python 求解器正在后台运行。",
    thinking: "已思考 {seconds} 秒…",
    noSolution: "思考 {seconds} 秒后仍未找到解法",
    solvedIn: "用时 {seconds} 秒找到解法",
    foundSolution: "找到 {count} 步解法，正在播放。",
    cubeSolved: "魔方已复原",
    verified: "已验证复原。点击“打乱”再次开始。",
    resetDone: "魔方已重置为复原状态。",
    bridgeError: "无法与 Python 求解器通信。",
  },
};

const DEFAULT_CONFIG = {
  alpha_scramble_length: 40,
  beta_scramble_length: 20,
  alpha_command:
    "python3 AlphaCube/tools/beam_database_solver.py --beam-width 20000 --depth 100",
  beta_command:
    "python3 BetaCube/Solver/color_evaluation_solver.py --no-fallback",
};

const COLOR_BY_FACE = {
  F: 0xf8fafc,
  R: 0x8dcc35,
  B: 0xfacc15,
  L: 0x3d5cab,
  U: 0xef4444,
  D: 0xff541e,
};

const ALPHA_MOVES = [
  "U", "U'", "U2", "R", "R'", "R2", "F", "F'", "F2",
  "D", "D'", "D2", "L", "L'", "L2", "B", "B'", "B2",
];
const BETA_MOVES = ["m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8"];
const ALPHA_INVERSES = Object.fromEntries(
  ALPHA_MOVES.map((move) => [
    move,
    move.endsWith("2") ? move : move.endsWith("'") ? move[0] : `${move}'`,
  ]),
);
const BETA_INVERSES = {
  m1: "m2", m2: "m1", m3: "m4", m4: "m3",
  m5: "m6", m6: "m5", m7: "m8", m8: "m7",
};


function sleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function format(key, values = {}) {
  let result = STRINGS[state.language][key];
  for (const [name, value] of Object.entries(values)) {
    result = result.replaceAll(`{${name}}`, String(value));
  }
  return result;
}

function randomItem(items) {
  return items[Math.floor(Math.random() * items.length)];
}

const mockState = {
  alpha: [],
  beta: [],
};

const MOCK_API = {
  async get_config() {
    return DEFAULT_CONFIG;
  },
  async reset(mode) {
    mockState[mode] = [];
    return { ok: true, mode };
  },
  async scramble(mode) {
    const length = mode === "alpha" ? 40 : 20;
    const moves = [];
    for (let index = 0; index < length; index += 1) {
      let choices = mode === "alpha" ? ALPHA_MOVES : BETA_MOVES;
      if (mode === "alpha" && moves.length) {
        choices = choices.filter((move) => move[0] !== moves.at(-1)[0]);
      } else if (mode === "beta" && moves.length) {
        choices = choices.filter((move) => move !== BETA_INVERSES[moves.at(-1)]);
      }
      moves.push(randomItem(choices));
    }
    mockState[mode] = moves;
    return { ok: true, mode, seed: Date.now(), moves };
  },
  async solve(mode) {
    await sleep(450);
    const inverseMap = mode === "alpha" ? ALPHA_INVERSES : BETA_INVERSES;
    const moves = [...mockState[mode]].reverse().map((move) => inverseMap[move]);
    mockState[mode] = [];
    return { ok: true, mode, moves, elapsed: 0.45, already_solved: moves.length === 0 };
  },
};

async function callApi(method, ...arguments_) {
  if (window.pywebview?.api?.[method]) {
    return window.pywebview.api[method](...arguments_);
  }
  return MOCK_API[method](...arguments_);
}


function roundedStickerGeometry(size, radius) {
  const half = size / 2;
  const shape = new THREE.Shape();
  shape.moveTo(-half + radius, -half);
  shape.lineTo(half - radius, -half);
  shape.quadraticCurveTo(half, -half, half, -half + radius);
  shape.lineTo(half, half - radius);
  shape.quadraticCurveTo(half, half, half - radius, half);
  shape.lineTo(-half + radius, half);
  shape.quadraticCurveTo(-half, half, -half, half - radius);
  shape.lineTo(-half, -half + radius);
  shape.quadraticCurveTo(-half, -half, -half + radius, -half);
  return new THREE.ShapeGeometry(shape);
}

function disposeTree(root) {
  root.traverse((object) => {
    object.geometry?.dispose?.();
    if (Array.isArray(object.material)) {
      object.material.forEach((material) => material.dispose());
    } else {
      object.material?.dispose?.();
    }
  });
}

class PhysicalCube {
  constructor(size, scene) {
    this.size = size;
    this.scene = scene;
    this.boundary = (size - 1) / 2;
    this.spacing = size === 3 ? 1.035 : 1.055;
    this.cubieSize = 0.94;
    this.root = null;
    this.cubies = [];
    this.visible = false;
    this.animating = false;
    this.reset();
  }

  coordinates() {
    if (this.size === 3) {
      return [-1, 0, 1];
    }
    return [-0.5, 0.5];
  }

  reset() {
    if (this.root) {
      this.scene.remove(this.root);
      disposeTree(this.root);
    }
    this.root = new THREE.Group();
    this.root.name = `${this.size}x${this.size}-cube`;
    this.root.visible = this.visible;
    this.root.position.y = 0.08;
    if (this.size === 2) {
      this.root.scale.setScalar(1.36);
    }
    this.scene.add(this.root);
    this.cubies = [];

    const plasticGeometry = new RoundedBoxGeometry(
      this.cubieSize,
      this.cubieSize,
      this.cubieSize,
      5,
      0.09,
    );
    const plasticMaterial = new THREE.MeshStandardMaterial({
      color: 0x090b10,
      roughness: 0.28,
      metalness: 0.08,
    });
    const stickerGeometry = roundedStickerGeometry(0.74, 0.095);
    const values = this.coordinates();

    for (const x of values) {
      for (const y of values) {
        for (const z of values) {
          if (this.size === 3 && x === 0 && y === 0 && z === 0) {
            continue;
          }
          const cubie = new THREE.Group();
          cubie.userData.coord = new THREE.Vector3(x, y, z);
          cubie.position.set(
            x * this.spacing,
            y * this.spacing,
            z * this.spacing,
          );

          const plastic = new THREE.Mesh(plasticGeometry, plasticMaterial);
          plastic.castShadow = true;
          plastic.receiveShadow = true;
          cubie.add(plastic);

          if (z === this.boundary) {
            this.addSticker(cubie, stickerGeometry, "F");
          }
          if (z === -this.boundary) {
            this.addSticker(cubie, stickerGeometry, "B");
          }
          if (x === this.boundary) {
            this.addSticker(cubie, stickerGeometry, "R");
          }
          if (x === -this.boundary) {
            this.addSticker(cubie, stickerGeometry, "L");
          }
          if (y === this.boundary) {
            this.addSticker(cubie, stickerGeometry, "U");
          }
          if (y === -this.boundary) {
            this.addSticker(cubie, stickerGeometry, "D");
          }

          this.root.add(cubie);
          this.cubies.push(cubie);
        }
      }
    }
  }

  addSticker(cubie, geometry, face) {
    const material = new THREE.MeshStandardMaterial({
      color: COLOR_BY_FACE[face],
      roughness: 0.42,
      metalness: 0.0,
      side: THREE.DoubleSide,
      polygonOffset: true,
      polygonOffsetFactor: -2,
    });
    const sticker = new THREE.Mesh(geometry, material);
    const offset = this.cubieSize / 2 + 0.006;

    if (face === "F") {
      sticker.position.z = offset;
    } else if (face === "B") {
      sticker.position.z = -offset;
      sticker.rotation.y = Math.PI;
    } else if (face === "R") {
      sticker.position.x = offset;
      sticker.rotation.y = Math.PI / 2;
    } else if (face === "L") {
      sticker.position.x = -offset;
      sticker.rotation.y = -Math.PI / 2;
    } else if (face === "U") {
      sticker.position.y = offset;
      sticker.rotation.x = -Math.PI / 2;
    } else if (face === "D") {
      sticker.position.y = -offset;
      sticker.rotation.x = Math.PI / 2;
    }
    sticker.castShadow = true;
    sticker.receiveShadow = true;
    cubie.add(sticker);
  }

  setVisible(visible) {
    this.visible = visible;
    this.root.visible = visible;
  }

  moveDefinition(move) {
    if (this.size === 3) {
      const face = move[0];
      const definitions = {
        U: { axis: new THREE.Vector3(0, 1, 0), component: "y", layer: this.boundary },
        D: { axis: new THREE.Vector3(0, -1, 0), component: "y", layer: -this.boundary },
        R: { axis: new THREE.Vector3(1, 0, 0), component: "x", layer: this.boundary },
        L: { axis: new THREE.Vector3(-1, 0, 0), component: "x", layer: -this.boundary },
        F: { axis: new THREE.Vector3(0, 0, 1), component: "z", layer: this.boundary },
        B: { axis: new THREE.Vector3(0, 0, -1), component: "z", layer: -this.boundary },
      };
      const definition = definitions[face];
      const angle = move.endsWith("2")
        ? -Math.PI
        : move.endsWith("'")
          ? Math.PI / 2
          : -Math.PI / 2;
      return { ...definition, angle };
    }

    const definitions = {
      m1: { axis: new THREE.Vector3(0, 1, 0), component: "y", layer: this.boundary, angle: Math.PI / 2 },
      m2: { axis: new THREE.Vector3(0, 1, 0), component: "y", layer: this.boundary, angle: -Math.PI / 2 },
      m3: { axis: new THREE.Vector3(0, 1, 0), component: "y", layer: -this.boundary, angle: Math.PI / 2 },
      m4: { axis: new THREE.Vector3(0, 1, 0), component: "y", layer: -this.boundary, angle: -Math.PI / 2 },
      m5: { axis: new THREE.Vector3(1, 0, 0), component: "x", layer: -this.boundary, angle: -Math.PI / 2 },
      m6: { axis: new THREE.Vector3(1, 0, 0), component: "x", layer: -this.boundary, angle: Math.PI / 2 },
      m7: { axis: new THREE.Vector3(1, 0, 0), component: "x", layer: this.boundary, angle: -Math.PI / 2 },
      m8: { axis: new THREE.Vector3(1, 0, 0), component: "x", layer: this.boundary, angle: Math.PI / 2 },
    };
    return definitions[move];
  }

  async animateMove(move, duration = 240) {
    if (this.animating) {
      throw new Error("A cube move is already in progress.");
    }
    const definition = this.moveDefinition(move);
    if (!definition) {
      throw new Error(`Unknown move: ${move}`);
    }
    this.animating = true;
    const affected = this.cubies.filter(
      (cubie) =>
        Math.abs(cubie.userData.coord[definition.component] - definition.layer) <
        0.01,
    );

    const pivot = new THREE.Group();
    this.root.add(pivot);
    this.root.updateMatrixWorld(true);
    affected.forEach((cubie) => pivot.attach(cubie));

    const startedAt = performance.now();
    await new Promise((resolve) => {
      const frame = (now) => {
        const linear = Math.min(1, (now - startedAt) / duration);
        const eased = linear * linear * (3 - 2 * linear);
        pivot.quaternion.setFromAxisAngle(
          definition.axis,
          definition.angle * eased,
        );
        if (linear < 1) {
          requestAnimationFrame(frame);
        } else {
          resolve();
        }
      };
      requestAnimationFrame(frame);
    });

    pivot.quaternion.setFromAxisAngle(definition.axis, definition.angle);
    pivot.updateMatrixWorld(true);
    const exactRotation = new THREE.Quaternion().setFromAxisAngle(
      definition.axis,
      definition.angle,
    );
    affected.forEach((cubie) => {
      this.root.attach(cubie);
      cubie.userData.coord.applyQuaternion(exactRotation);
      for (const component of ["x", "y", "z"]) {
        const value = cubie.userData.coord[component];
        cubie.userData.coord[component] = Math.round(value * 2) / 2;
      }
      cubie.position.copy(cubie.userData.coord).multiplyScalar(this.spacing);
      cubie.quaternion.normalize();
      for (const component of ["x", "y", "z", "w"]) {
        if (Math.abs(cubie.quaternion[component]) < 1e-10) {
          cubie.quaternion[component] = 0;
        }
      }
    });
    this.root.remove(pivot);
    this.animating = false;
  }

  async animateSequence(moves, duration, onMove) {
    for (let index = 0; index < moves.length; index += 1) {
      onMove?.(moves[index], index + 1, moves.length);
      await this.animateMove(moves[index], duration);
      await sleep(18);
    }
    onMove?.(null, moves.length, moves.length);
  }
}


const viewport = document.querySelector("#viewport");
const renderer = new THREE.WebGLRenderer({
  antialias: true,
  alpha: true,
  powerPreference: "high-performance",
});
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setClearColor(0x000000, 0);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
viewport.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 100);
camera.position.set(5.4, 4.3, 6.6);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.07;
controls.target.set(0, 0.05, 0);
controls.minDistance = 4.1;
controls.maxDistance = 11;
controls.enablePan = false;

scene.add(new THREE.HemisphereLight(0xffffff, 0x6c7890, 2.15));
const keyLight = new THREE.DirectionalLight(0xffffff, 4.2);
keyLight.position.set(4.5, 7.5, 5.5);
keyLight.castShadow = true;
keyLight.shadow.mapSize.set(2048, 2048);
keyLight.shadow.camera.left = -5;
keyLight.shadow.camera.right = 5;
keyLight.shadow.camera.top = 5;
keyLight.shadow.camera.bottom = -5;
keyLight.shadow.bias = -0.0004;
scene.add(keyLight);

const rimLight = new THREE.DirectionalLight(0x8ba8ff, 1.7);
rimLight.position.set(-5, 3, -4);
scene.add(rimLight);

const ground = new THREE.Mesh(
  new THREE.PlaneGeometry(20, 20),
  new THREE.ShadowMaterial({ color: 0x4b5567, opacity: 0.18 }),
);
ground.rotation.x = -Math.PI / 2;
ground.position.y = -1.57;
ground.receiveShadow = true;
scene.add(ground);

const models = {
  alpha: new PhysicalCube(3, scene),
  beta: new PhysicalCube(2, scene),
};
models.alpha.setVisible(true);
models.beta.setVisible(false);

const resizeObserver = new ResizeObserver(() => {
  const width = Math.max(viewport.clientWidth, 1);
  const height = Math.max(viewport.clientHeight, 1);
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
});
resizeObserver.observe(viewport);

renderer.setAnimationLoop(() => {
  controls.update();
  renderer.render(scene, camera);
});


const elements = {
  tabAlpha: document.querySelector("#tabAlpha"),
  tabBeta: document.querySelector("#tabBeta"),
  tabSettings: document.querySelector("#tabSettings"),
  scramble: document.querySelector("#scrambleButton"),
  solve: document.querySelector("#solveButton"),
  reset: document.querySelector("#resetButton"),
  modeTitle: document.querySelector("#modeTitle"),
  modeSubtitle: document.querySelector("#modeSubtitle"),
  statusHeading: document.querySelector("#statusHeading"),
  thinking: document.querySelector("#thinkingText"),
  detail: document.querySelector("#detailText"),
  commandHeading: document.querySelector("#commandHeading"),
  command: document.querySelector("#commandText"),
  message: document.querySelector("#messageText"),
  stageMode: document.querySelector("#stageMode"),
  orbitHint: document.querySelector("#orbitHint"),
  moveBadge: document.querySelector("#moveBadge"),
  settingsDialog: document.querySelector("#settingsDialog"),
  cancelSettings: document.querySelector("#cancelSettings"),
  applySettings: document.querySelector("#applySettings"),
  intro: document.querySelector("#intro"),
  introLine: document.querySelector("#introLine"),
};

const state = {
  activeMode: "alpha",
  language: localStorage.getItem("cubezero-language") || "en",
  busy: false,
  config: DEFAULT_CONFIG,
  timer: null,
  solverStartedAt: 0,
};

function setBusy(busy) {
  state.busy = busy;
  for (const button of [
    elements.tabAlpha,
    elements.tabBeta,
    elements.tabSettings,
    elements.scramble,
    elements.solve,
    elements.reset,
  ]) {
    button.disabled = busy;
  }
}

function setMoveBadge(move, current = 0, total = 0) {
  if (!move) {
    elements.moveBadge.hidden = true;
    return;
  }
  elements.moveBadge.hidden = false;
  elements.moveBadge.textContent = `${move}  ·  ${current}/${total}`;
}

function updateModeCopy() {
  const alpha = state.activeMode === "alpha";
  elements.tabAlpha.classList.toggle("active", alpha);
  elements.tabBeta.classList.toggle("active", !alpha);
  elements.modeTitle.textContent = alpha ? "AlphaCube" : "BetaCube";
  elements.stageMode.textContent = alpha ? "ALPHACUBE · 3×3" : "BETACUBE · 2×2";
  elements.modeSubtitle.textContent = format(
    alpha ? "alphaSubtitle" : "betaSubtitle",
  );
  elements.detail.textContent = format(alpha ? "alphaDetail" : "betaDetail");
  elements.command.textContent = alpha
    ? state.config.alpha_command
    : state.config.beta_command;
}

function applyLanguage(language) {
  state.language = language in STRINGS ? language : "en";
  localStorage.setItem("cubezero-language", state.language);
  document.documentElement.lang = state.language === "zh" ? "zh-CN" : "en";

  for (const element of document.querySelectorAll("[data-i18n]")) {
    element.textContent = format(element.dataset.i18n);
  }
  elements.scramble.textContent = format("scramble");
  elements.solve.textContent = format("solve");
  elements.reset.textContent = format("reset");
  elements.statusHeading.textContent = format("solverStatus");
  elements.commandHeading.textContent = format("command");
  elements.cancelSettings.textContent = format("cancel");
  elements.applySettings.textContent = format("apply");
  elements.orbitHint.textContent = format("orbit");
  elements.thinking.textContent = format("ready");
  elements.message.textContent = format("readyPrompt");
  updateModeCopy();
}

function switchMode(mode) {
  if (state.busy || mode === state.activeMode) {
    return;
  }
  models[state.activeMode].setVisible(false);
  state.activeMode = mode;
  models[state.activeMode].setVisible(true);
  elements.thinking.textContent = format("ready");
  elements.message.textContent = format("readyPrompt");
  updateModeCopy();
}

async function scrambleActiveCube() {
  if (state.busy) return;
  setBusy(true);
  elements.thinking.textContent = format("scrambling");
  elements.message.textContent = "";
  try {
    const result = await callApi("scramble", state.activeMode);
    const model = models[state.activeMode];
    model.reset();
    model.setVisible(true);
    elements.message.textContent = format("scrambleProgress", {
      count: result.moves.length,
    });
    await model.animateSequence(result.moves, 112, setMoveBadge);
    elements.thinking.textContent = format("scrambleReady");
    elements.message.textContent = format("solvePrompt");
  } catch (error) {
    elements.thinking.textContent = format("bridgeError");
    elements.message.textContent = String(error);
  } finally {
    setMoveBadge(null);
    setBusy(false);
  }
}

function startThinkingTimer() {
  state.solverStartedAt = performance.now();
  clearInterval(state.timer);
  state.timer = setInterval(() => {
    const seconds = (performance.now() - state.solverStartedAt) / 1000;
    elements.thinking.textContent = format("thinking", {
      seconds: seconds.toFixed(1),
    });
  }, 100);
}

function stopThinkingTimer() {
  clearInterval(state.timer);
  state.timer = null;
}

async function solveActiveCube() {
  if (state.busy) return;
  setBusy(true);
  startThinkingTimer();
  elements.message.textContent = format("solverRunning");
  try {
    const result = await callApi("solve", state.activeMode);
    stopThinkingTimer();
    const seconds = Number(result.elapsed || 0).toFixed(1);
    if (!result.ok) {
      elements.thinking.textContent = format("noSolution", { seconds });
      elements.message.textContent = result.error || format("bridgeError");
      return;
    }
    if (result.already_solved) {
      elements.thinking.textContent = format("alreadySolved");
      elements.message.textContent = format("newGame");
      return;
    }
    elements.thinking.textContent = format("solvedIn", { seconds });
    elements.message.textContent = format("foundSolution", {
      count: result.moves.length,
    });
    await models[state.activeMode].animateSequence(
      result.moves,
      245,
      setMoveBadge,
    );
    elements.thinking.textContent = format("cubeSolved");
    elements.message.textContent = format("verified");
  } catch (error) {
    stopThinkingTimer();
    elements.thinking.textContent = format("bridgeError");
    elements.message.textContent = String(error);
  } finally {
    setMoveBadge(null);
    setBusy(false);
  }
}

async function resetActiveCube() {
  if (state.busy) return;
  setBusy(true);
  try {
    await callApi("reset", state.activeMode);
    models[state.activeMode].reset();
    models[state.activeMode].setVisible(true);
    elements.thinking.textContent = format("ready");
    elements.message.textContent = format("resetDone");
  } catch (error) {
    elements.thinking.textContent = format("bridgeError");
    elements.message.textContent = String(error);
  } finally {
    setBusy(false);
  }
}

elements.tabAlpha.addEventListener("click", () => switchMode("alpha"));
elements.tabBeta.addEventListener("click", () => switchMode("beta"));
elements.scramble.addEventListener("click", scrambleActiveCube);
elements.solve.addEventListener("click", solveActiveCube);
elements.reset.addEventListener("click", resetActiveCube);
elements.tabSettings.addEventListener("click", () => {
  const selected = elements.settingsDialog.querySelector(
    `input[name="language"][value="${state.language}"]`,
  );
  if (selected) selected.checked = true;
  elements.settingsDialog.showModal();
});
elements.cancelSettings.addEventListener("click", () => {
  elements.settingsDialog.close();
});
elements.applySettings.addEventListener("click", () => {
  const selected = elements.settingsDialog.querySelector(
    'input[name="language"]:checked',
  );
  applyLanguage(selected?.value || "en");
  elements.settingsDialog.close();
});

async function initializeBridge() {
  try {
    state.config = await callApi("get_config");
  } catch {
    state.config = DEFAULT_CONFIG;
  }
  updateModeCopy();
}

async function runIntro() {
  const phrase = "Think big, start small.";
  for (let index = 0; index <= phrase.length; index += 1) {
    const cursor = index < phrase.length ? '<span class="cursor">│</span>' : "";
    elements.introLine.innerHTML = `${phrase.slice(0, index)}${cursor}`;
    const previousCharacter = phrase[index - 1];
    await sleep(previousCharacter === "," || previousCharacter === "." ? 125 : 70);
  }
  await sleep(850);
  elements.intro.classList.add("turning");
  elements.intro.addEventListener(
    "animationend",
    () => elements.intro.remove(),
    { once: true },
  );
}

applyLanguage(state.language);
initializeBridge();
runIntro();
