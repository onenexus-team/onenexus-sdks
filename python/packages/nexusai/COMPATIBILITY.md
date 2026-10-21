# Compatibility Policy

NexusAI follows semantic versioning.

- Patch releases contain compatible bug fixes and documentation updates.
- Minor releases add compatible public APIs. During beta, a minor release may
  also remove a previously deprecated API when the changelog calls it out.
- Major releases may contain breaking public API or wire-contract changes.

The supported Python versions are declared by `requires-python` and package
classifiers. NexusAI `0.1.x` requires Python 3.11 or newer.

Only names exported from `nexusai.__all__` and documented in the package README
are public. Modules below `nexusai._internal` are implementation details and may
change without a public deprecation cycle.

Deprecations are documented in release notes and remain available for at least
one compatible release unless they create a security or data-integrity risk.
