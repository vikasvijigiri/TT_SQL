import fastify from 'fastify';
import cors from '@fastify/cors';
import axios from 'axios';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = fastify({ logger: true });

const PYTHON_API_URL = process.env.PYTHON_API_URL || 'http://localhost:8001';

app.register(cors, {
  origin: '*',
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
});

app.get('/api/health', async (request, reply) => {
  return { status: 'ok', service: 'fastify-api-gateway' };
});

// Proxy all other /api/* requests to the Python AI Microservice
app.all('/api/*', async (request, reply) => {
  const targetUrl = `${PYTHON_API_URL}${request.raw.url}`;
  try {
    // For Server-Sent Events (SSE) / streaming
    const isSSE = request.raw.url?.includes('/stream');
    
    const response = await axios({
      method: request.method as string,
      url: targetUrl,
      data: request.body,
      // Pass along query parameters if not already in URL, though request.raw.url includes them
      headers: { 
        ...request.headers,
        host: new URL(PYTHON_API_URL).host 
      },
      responseType: isSSE ? 'stream' : 'json',
      validateStatus: () => true // Resolve all HTTP statuses
    });

    // Copy headers from Python response
    Object.entries(response.headers).forEach(([key, value]) => {
      if (value !== undefined) {
        reply.header(key, value as string);
      }
    });

    reply.status(response.status);
    return reply.send(response.data);
  } catch (error: any) {
    app.log.error(`Proxy error to ${targetUrl}:`, error.message);
    return reply.code(502).send({ error: 'Bad Gateway - Python AI Microservice unreachable' });
  }
});

const start = async () => {
  try {
    const port = 3030;
    await app.listen({ port, host: '0.0.0.0' });
    app.log.info(`API Gateway listening on http://localhost:${port}`);
  } catch (err) {
    app.log.error(err);
    process.exit(1);
  }
};

start();
