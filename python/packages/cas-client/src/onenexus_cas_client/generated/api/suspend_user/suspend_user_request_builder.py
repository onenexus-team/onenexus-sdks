from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass, field
from kiota_abstractions.base_request_builder import BaseRequestBuilder
from kiota_abstractions.base_request_configuration import RequestConfiguration
from kiota_abstractions.default_query_parameters import QueryParameters
from kiota_abstractions.get_path_parameters import get_path_parameters
from kiota_abstractions.method import Method
from kiota_abstractions.request_adapter import RequestAdapter
from kiota_abstractions.request_information import RequestInformation
from kiota_abstractions.request_option import RequestOption
from kiota_abstractions.serialization import Parsable, ParsableFactory
from typing import Any, Optional, TYPE_CHECKING, Union
from warnings import warn

if TYPE_CHECKING:
    from ...models.problem_details import ProblemDetails
    from ...models.suspend_user_request import SuspendUserRequest
    from ...models.suspend_user_response import SuspendUserResponse
    from ...models.validation_problem_details import ValidationProblemDetails

class SuspendUserRequestBuilder(BaseRequestBuilder):
    """
    Builds and executes requests for operations under /api/SuspendUser
    """
    def __init__(self,request_adapter: RequestAdapter, path_parameters: Union[str, dict[str, Any]]) -> None:
        """
        Instantiates a new SuspendUserRequestBuilder and sets the default values.
        param path_parameters: The raw url or the url-template parameters for the request.
        param request_adapter: The request adapter to use to execute the requests.
        Returns: None
        """
        super().__init__(request_adapter, "{+baseurl}/api/SuspendUser", path_parameters)
    
    async def post(self,body: SuspendUserRequest, request_configuration: Optional[RequestConfiguration[QueryParameters]] = None) -> Optional[SuspendUserResponse]:
        """
        Requires `CAS::SuspendUser` on the target user's canonical URI.The tenant is derived from the caller; root, deleted and cross-tenantusers return 404. The tenant root cannot be suspended through this API.Self-suspension is refused. Role assignments are retained. Suspension rotatesthe security stamp atomically with the lifecycle change; sessions end attheir next validation, and regional authorization observes the change afterCDC projection. Already issued access tokens retain valid signatures until expiry.Repeating the operation on a suspended member succeeds without changing stamps.
        param body: Request body for `POST /api/SuspendUser`.
        param request_configuration: Configuration for the request such as headers, query parameters, and middleware options.
        Returns: Optional[SuspendUserResponse]
        """
        if body is None:
            raise TypeError("body cannot be null.")
        request_info = self.to_post_request_information(
            body, request_configuration
        )
        from ...models.problem_details import ProblemDetails
        from ...models.validation_problem_details import ValidationProblemDetails

        error_mapping: dict[str, type[ParsableFactory]] = {
            "400": ValidationProblemDetails,
            "401": ProblemDetails,
            "403": ProblemDetails,
            "404": ProblemDetails,
            "409": ProblemDetails,
            "503": ProblemDetails,
        }
        if not self.request_adapter:
            raise Exception("Http core is null") 
        from ...models.suspend_user_response import SuspendUserResponse

        return await self.request_adapter.send_async(request_info, SuspendUserResponse, error_mapping)
    
    def to_post_request_information(self,body: SuspendUserRequest, request_configuration: Optional[RequestConfiguration[QueryParameters]] = None) -> RequestInformation:
        """
        Requires `CAS::SuspendUser` on the target user's canonical URI.The tenant is derived from the caller; root, deleted and cross-tenantusers return 404. The tenant root cannot be suspended through this API.Self-suspension is refused. Role assignments are retained. Suspension rotatesthe security stamp atomically with the lifecycle change; sessions end attheir next validation, and regional authorization observes the change afterCDC projection. Already issued access tokens retain valid signatures until expiry.Repeating the operation on a suspended member succeeds without changing stamps.
        param body: Request body for `POST /api/SuspendUser`.
        param request_configuration: Configuration for the request such as headers, query parameters, and middleware options.
        Returns: RequestInformation
        """
        if body is None:
            raise TypeError("body cannot be null.")
        request_info = RequestInformation(Method.POST, self.url_template, self.path_parameters)
        request_info.configure(request_configuration)
        request_info.headers.try_add("Accept", "application/json")
        request_info.set_content_from_parsable(self.request_adapter, "application/json", body)
        return request_info
    
    def with_url(self,raw_url: str) -> SuspendUserRequestBuilder:
        """
        Returns a request builder with the provided arbitrary URL. Using this method means any other path or query parameters are ignored.
        param raw_url: The raw URL to use for the request builder.
        Returns: SuspendUserRequestBuilder
        """
        if raw_url is None:
            raise TypeError("raw_url cannot be null.")
        return SuspendUserRequestBuilder(self.request_adapter, raw_url)
    
    @dataclass
    class SuspendUserRequestBuilderPostRequestConfiguration(RequestConfiguration[QueryParameters]):
        """
        Configuration for the request such as headers, query parameters, and middleware options.
        """
        warn("This class is deprecated. Please use the generic RequestConfiguration class generated by the generator.", DeprecationWarning)
    

