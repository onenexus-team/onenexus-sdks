import type { ClientContext } from '../../src/credentials/credentials.js';
import { SystemClock } from '../../src/credentials/credentials.js';

export function testContext(): ClientContext {
    return { clock: new SystemClock(), refreshLeewayMs: 30_000 };
}

export function advanceServerClock(context: ClientContext, byMs: number): void {
    context.clock.observeServerTime(new Date(Date.now() + byMs));
}