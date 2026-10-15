import { type ChildProcess, spawn, spawnSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const backendDir = resolve(here, '../../backend');
const ctl = join(here, 'backend_ctl.py');
const python = [join(backendDir, '.venv/Scripts/python.exe'), join(backendDir, '.venv/bin/python')].find(
	existsSync
);

/** TEST_DATABASE_URL from the environment, else from backend/.env.test. Never logged. */
function databaseUrl(): string {
	const fromEnv = process.env.TEST_DATABASE_URL;
	if (fromEnv) return fromEnv;
	const file = join(backendDir, '.env.test');
	if (existsSync(file)) {
		for (const line of readFileSync(file, 'utf8').replace(/^﻿/, '').split(/\r?\n/)) {
			const m = /^\s*(?:export\s+)?TEST_DATABASE_URL\s*=\s*(.*?)\s*$/.exec(line);
			if (m?.[1]) return m[1].replace(/^(['"])(.*)\1$/, '$2');
		}
	}
	throw new Error('TEST_DATABASE_URL is not set and backend/.env.test has none');
}

function run(action: string, schema: string, env: NodeJS.ProcessEnv) {
	const result = spawnSync(python as string, [ctl, action, schema], { env, stdio: 'pipe' });
	if (result.status !== 0) {
		throw new Error(`backend_ctl ${action} failed: ${String(result.stderr).slice(-500)}`);
	}
}

async function waitForHealth(timeoutMs: number): Promise<void> {
	const deadline = Date.now() + timeoutMs;
	while (Date.now() < deadline) {
		try {
			if ((await fetch('http://127.0.0.1:8000/api/health')).ok) return;
		} catch {
			// not up yet
		}
		await new Promise((r) => setTimeout(r, 300));
	}
	throw new Error('backend did not become healthy on 127.0.0.1:8000');
}

function stop(child: ChildProcess) {
	if (child.pid === undefined) return;
	if (process.platform === 'win32') {
		spawnSync('taskkill', ['/pid', String(child.pid), '/T', '/F']);
	} else {
		child.kill('SIGTERM');
	}
}

export default async function globalSetup() {
	if (!python) throw new Error('backend virtualenv not found (run uv sync in backend/)');
	try {
		await fetch('http://127.0.0.1:8000/api/health');
		throw new Error('port 8000 is already in use; stop that server before running e2e');
	} catch (err) {
		if (err instanceof Error && err.message.startsWith('port 8000')) throw err;
	}

	const schema = `e2e_${randomBytes(6).toString('hex')}`;
	const dir = mkdtempSync(join(tmpdir(), 'mq-e2e-'));
	const wordFile = join(dir, 'signup_word');
	const signupWord = `e2e${randomBytes(4).toString('hex')}`;
	writeFileSync(wordFile, signupWord, 'utf8');
	process.env.E2E_SIGNUP_WORD = signupWord;
	const adminFile = join(dir, 'admin_password');
	const adminPassword = `e2e-admin-${randomBytes(12).toString('hex')}`;
	writeFileSync(adminFile, adminPassword, 'utf8');
	process.env.E2E_ADMIN_PASSWORD = adminPassword;

	const env = {
		...process.env,
		TEST_DATABASE_URL: databaseUrl(),
		E2E_WORD_FILE: wordFile,
		E2E_ADMIN_FILE: adminFile
	};
	let server: ChildProcess | undefined;
	let tail = '';

	const cleanup = () => {
		try {
			if (server) stop(server);
		} finally {
			try {
				run('drop', schema, env);
			} finally {
				rmSync(dir, { recursive: true, force: true });
			}
		}
	};

	try {
		run('prepare', schema, env);
		const child = spawn(python, [ctl, 'serve', schema], { env, stdio: 'pipe' });
		server = child;
		child.stderr?.on('data', (d: Buffer) => (tail = (tail + String(d)).slice(-1500)));
		const spawnFailed = new Promise<never>((_, reject) => {
			child.on('error', (e) => reject(new Error(`backend failed to start: ${e.message}`)));
			child.on('exit', (code) => reject(new Error(`backend exited early (code ${code})`)));
		});
		// Marks the rejection handled so a crash after startup is not an unhandled rejection.
		spawnFailed.catch(() => undefined);
		await Promise.race([waitForHealth(60_000), spawnFailed]);
	} catch (err) {
		cleanup();
		throw new Error(`${(err as Error).message}\n${tail}`);
	}
	return cleanup;
}
