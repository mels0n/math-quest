import { describe, expect, it } from 'vitest';
import { waitText } from './messages';

describe('waitText', () => {
	it('uses seconds under a minute', () => {
		expect(waitText(30)).toBe('30 seconds');
	});
	it('says a minute or two under 120 seconds', () => {
		expect(waitText(90)).toBe('a minute or two');
	});
	it('counts minutes under an hour', () => {
		expect(waitText(1800)).toBe('30 minutes');
	});
	it('says an hour, not 1 hours', () => {
		expect(waitText(3600)).toBe('about an hour');
		expect(waitText(5399)).toBe('about an hour');
	});
	it('rounds 90 minutes up to 2 hours', () => {
		expect(waitText(5400)).toBe('about 2 hours');
	});
	it('counts hours under six hours', () => {
		expect(waitText(7200)).toBe('about 2 hours');
	});
	it('says until tomorrow beyond that', () => {
		expect(waitText(86400)).toBe('until tomorrow');
	});
});
