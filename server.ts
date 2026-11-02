import express from 'express';
import { createServer as createViteServer } from 'vite';
import { createProxyMiddleware } from 'http-proxy-middleware';
import { spawn, ChildProcess } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = parseInt(process.env.PORT || '3000', 10);
const FASTAPI_PORT = 8000;
let fastapiProcess: ChildProcess | null = null;

// Start Python FastAPI daemon
function startFastApiBackend() {
  console.log('[Server] Spawning Python FastAPI backend on port 8000...');
  fastapiProcess = spawn(process.env.PYTHON_BIN || 'python3', [
    '-m', 'uvicorn',
    'backend.app.main:app',
    '--host', '127.0.0.1',
    '--port', String(FASTAPI_PORT)
  ], {
    stdio: 'inherit',
    env: { ...process.env, PYTHONPATH: '.' }
  });

  fastapiProcess.on('error', (err) => {
    console.error('[FastAPI] Process failed to start:', err);
  });

  fastapiProcess.on('exit', (code, signal) => {
    console.log(`[FastAPI] Exited with code ${code} and signal ${signal}`);
  });

  process.on('exit', () => {
    if (fastapiProcess) fastapiProcess.kill();
  });
  process.on('SIGINT', () => {
    if (fastapiProcess) fastapiProcess.kill();
    process.exit();
  });
  process.on('SIGTERM', () => {
    if (fastapiProcess) fastapiProcess.kill();
    process.exit();
  });
}

async function startServer() {
  // Spawn FastAPI backend
  startFastApiBackend();

  const app = express();

  // Proxy API and OpenAPI / Swagger docs requests to FastAPI on port 8000
  const apiProxy = createProxyMiddleware({
    target: `http://127.0.0.1:${FASTAPI_PORT}`,
    // Mounted without a path so Express does not strip '/api'; the filter picks what to forward.
    pathFilter: ['/api', '/docs', '/redoc', '/openapi.json'],
    changeOrigin: true,
    ws: true,
    on: {
      error: (err: any, req: any, res: any) => {
        console.error('[Proxy Error]:', err.message);
        if (!res.headersSent && typeof res.status === 'function') {
          res.status(502).json({
            error: 'FastAPI Backend is starting up. Please retry in a few seconds.',
            detail: err.message
          });
        }
      }
    }
  });

  app.use(apiProxy);

  const isProduction = process.env.NODE_ENV === 'production';

  if (!isProduction) {
    // Mount Vite middlewares for hot frontend development
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    // Serve static frontend build
    app.use(express.static(path.resolve(__dirname, 'dist')));
    app.get('*', (req, res) => {
      res.sendFile(path.resolve(__dirname, 'dist', 'index.html'));
    });
  }

  const HOST = process.env.HOST || '127.0.0.1';
  app.listen(PORT, HOST, () => {
    console.log(`[Server] AICTE FDR Management Portal running on http://${HOST}:${PORT}`);
    console.log(`[Server] FastAPI Backend proxied via http://${HOST}:${PORT}/api`);
    console.log(`[Server] Swagger Docs accessible at http://${HOST}:${PORT}/docs`);
  });
}

startServer().catch((err) => {
  console.error('[Server] Fatal startup error:', err);
  process.exit(1);
});
