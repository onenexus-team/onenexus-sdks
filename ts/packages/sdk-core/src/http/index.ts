export {
    AlreadyExistsError,
    FailedPreconditionError,
    ForbiddenError,
    InternalError,
    InvalidArgumentError,
    NotFoundError,
    parseHttpError,
    PlatformError,
    type PlatformErrorInit,
    ResourceExhaustedError,
    UnauthenticatedError,
    UnavailableError,
} from './errors.js';
export {
    createRequestAdapter,
    type CreateRequestAdapterOptions,
    type KiotaRetryConfig,
    OneNexusAuthenticationProvider,
} from './request-adapter.js';
