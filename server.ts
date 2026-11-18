import { spawn, type ChildProcess } from 'child_process';
import fs from 'fs';
import http from 'http';
import path from 'path';
import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';

function resolveBackendPort(): number {
  const raw = process.env.BLACKSWAN_BACKEND_PORT;
  const parsed = raw ? Number(raw) : NaN;
  if (Number.isInteger(parsed) && parsed >= 1025 && parsed <= 65535 && parsed !== 8000) {
    return parsed;
  }
  return 8787;
}

const PORT = Number(process.env.PORT || 3000);
// Use 8787 locally so we never collide with AI Studio's internal control-plane-api on 8000
const BACKEND_PORT = resolveBackendPort();
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;
const IS_PROD = process.env.NODE_ENV === 'production';

let backendReady = false;
let backendProcess: ChildProcess | null = null;
let startingPromise: Promise<void> | null = null;

function resolvePythonBin(): string {
  const candidates = [
    path.resolve(process.cwd(), '.venv/bin/python'),
    '/app/applet/.venv/bin/python',
  ];
  for (const cand of candidates) {
    if (fs.existsSync(cand)) {
      return cand;
    }
  }
  return 'python3';
}

function checkBackendAlive(): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get(`${BACKEND_URL}/api/health`, (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on('error', () => resolve(false));
    req.setTimeout(1000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

function runCommandAsync(cmd: string, args: string[]): Promise<number> {
  return new Promise((resolve) => {
    const p = spawn(cmd, args, { cwd: process.cwd(), stdio: 'inherit' });
    p.on('close', (code) => resolve(code ?? 1));
    p.on('error', () => resolve(1));
  });
}

async function bootstrapVenvIfNeeded(): Promise<void> {
  const pyBin = resolvePythonBin();
  if (pyBin !== 'python3') {
    return;
  }
  // Check if system python3 already has fastapi/uvicorn
  const hasUvicorn = await runCommandAsync('python3', ['-c', 'import fastapi, uvicorn, arch, hmmlearn']);
  if (hasUvicorn === 0) {
    return;
  }

  const venvDir = path.resolve(process.cwd(), '.venv');
  const venvPython = path.join(venvDir, 'bin/python');
  console.log('[BLACKSWAN] .venv missing — bootstrapping Python environment from requirements.txt...');
  await runCommandAsync('python3', ['-m', 'venv', '--without-pip', venvDir]);
  await runCommandAsync('curl', ['-sSL', 'https://bootstrap.pypa.io/get-pip.py', '-o', '/tmp/get-pip.py']);
  await runCommandAsync(venvPython, ['/tmp/get-pip.py', '--quiet']);
  await runCommandAsync(path.join(venvDir, 'bin/pip'), ['install', '--quiet', '-r', 'requirements.txt']);
}

async function ensurePythonBackend(): Promise<void> {
  if (await checkBackendAlive()) {
    backendReady = true;
    return;
  }
  if (startingPromise) {
    return startingPromise;
  }

  startingPromise = (async () => {
    try {
      await bootstrapVenvIfNeeded();
      if (await checkBackendAlive()) {
        backendReady = true;
        return;
      }

      const pyBin = resolvePythonBin();
      console.log(`[BLACKSWAN] Starting FastAPI backend via ${pyBin} on port ${BACKEND_PORT}...`);
      const logStream = fs.createWriteStream('/tmp/blackswan-backend.log', { flags: 'a' });

      const cleanEnv: NodeJS.ProcessEnv = { ...process.env, PYTHONUNBUFFERED: '1' };
      if (!cleanEnv.DATABASE_URL || !cleanEnv.DATABASE_URL.includes('://')) {
        cleanEnv.DATABASE_URL = 'sqlite:///./data/blackswan.db';
      }
      cleanEnv.BLACKSWAN_BACKEND_PORT = String(BACKEND_PORT);

      const child = spawn(
        pyBin,
        ['-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)],
        {
          cwd: process.cwd(),
          stdio: ['ignore', 'pipe', 'pipe'],
          env: cleanEnv,
        }
      );
      backendProcess = child;

      child.stdout?.on('data', (chunk) => {
        process.stdout.write(chunk);
        logStream.write(chunk);
      });
      child.stderr?.on('data', (chunk) => {
        process.stderr.write(chunk);
        logStream.write(chunk);
      });

      child.on('exit', (code, signal) => {
        backendReady = false;
        backendProcess = null;
        console.warn(`[BLACKSWAN] FastAPI process exited (code=${code}, signal=${signal})`);
      });

      for (let i = 0; i < 60; i++) {
        if (await checkBackendAlive()) {
          backendReady = true;
          console.log(`[BLACKSWAN] FastAPI backend ready on ${BACKEND_URL}`);
          return;
        }
        if (!backendProcess) {
          break;
        }
        await new Promise((r) => setTimeout(r, 400));
      }
    } finally {
      startingPromise = null;
    }
  })();

  return startingPromise;
}

async function startServer() {
  const cleanup = () => {
    if (backendProcess && !backendProcess.killed) {
      backendProcess.kill('SIGTERM');
    }
  };
  process.on('SIGINT', () => {
    cleanup();
    process.exit(0);
  });
  process.on('SIGTERM', () => {
    cleanup();
    process.exit(0);
  });

  const app = express();

  // Guard /api/* while FastAPI is still booting so frontend never receives HTML
  app.use('/api', async (_req, res, next) => {
    if (backendReady) {
      return next();
    }
    if (await checkBackendAlive()) {
      backendReady = true;
      return next();
    }
    void ensurePythonBackend();
    res.status(503).json({
      detail: 'BLACKSWAN FastAPI quantitative engine is initializing. Please retry in a moment.',
    });
  });

  // Proxy all /api/* requests directly to Python FastAPI backend
  app.use(
    createProxyMiddleware({
      target: BACKEND_URL,
      changeOrigin: true,
      pathFilter: '/api',
      proxyTimeout: 120_000,
      timeout: 120_000,
      on: {
        error: (_err, _req, res) => {
          backendReady = false;
          if ('writeHead' in res && typeof res.writeHead === 'function') {
            res.writeHead(502, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ detail: 'Quantitative backend temporarily unavailable.' }));
          }
        },
      },
    })
  );

  if (!IS_PROD) {
    const { createServer: createViteServer } = await import('vite');
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distDir = path.resolve(process.cwd(), 'dist');
    app.use(express.static(distDir));
    app.get('*', (_req, res) => {
      res.sendFile(path.join(distDir, 'index.html'));
    });
  }

  // Bind port 3000 immediately and spawn FastAPI in background
  app.listen(PORT, '0.0.0.0', () => {
    console.log(`[BLACKSWAN] Quant Terminal listening on http://0.0.0.0:${PORT}`);
    void ensurePythonBackend();
  });
}

startServer().catch((err) => {
  console.error('[BLACKSWAN] Fatal server error:', err);
  process.exit(1);
});
