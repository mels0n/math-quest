import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test } from 'vitest';

const EM_DASH = '—';
const SRC = fileURLToPath(new URL('..', import.meta.url));

function sources(dir: string): string[] {
	return readdirSync(dir).flatMap((name) => {
		const path = join(dir, name);
		if (statSync(path).isDirectory()) return sources(path);
		const shown = name.endsWith('.svelte') || (name.endsWith('.ts') && !name.endsWith('.test.ts'));
		return shown ? [path] : [];
	});
}

test('rendered source files contain no em dash', () => {
	const files = sources(SRC);
	expect(files.length).toBeGreaterThan(0);
	const offenders = files.filter((file) => readFileSync(file, 'utf8').includes(EM_DASH));
	expect(offenders).toEqual([]);
});
