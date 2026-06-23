/**
 * Local wrapper around `@onenexus-team/sdk-core`'s `platformMutator`.
 *
 * The wrapper exists so orval's `mutator.path` parser can detect the export.
 * orval's parser only recognises a locally-declared `function platformMutator`
 * — a bare `export { x } from 'pkg'` re-export or a `const` alias is silently
 * dropped, which produces the misleading error
 *   "Your mutator file doesn't have the platformMutator exported function".
 *
 * Behaviour-wise this is a pure pass-through; the actual implementation
 * (auth header injection, RFC 9457 error parsing, Ky transport) lives in
 * `@onenexus-team/sdk-core`.
 *
 * `CasSupportClient` receives mutator options from `ClientBase`; generated
 * operations receive those options through their second argument.
 */
import {
    platformMutator as _platformMutator,
    type PlatformMutatorOptions as CorePlatformMutatorOptions,
    type PlatformMutatorRequestConfig,
} from '@onenexus-team/sdk-core';

export type PlatformMutatorOptions = CorePlatformMutatorOptions;

export async function platformMutator<T>(
    config: PlatformMutatorRequestConfig,
    options?: PlatformMutatorOptions,
): Promise<T> {
    return _platformMutator<T>(config, options);
}
