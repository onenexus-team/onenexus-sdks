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
    from ...models.remove_user_request import RemoveUserRequest
    from ...models.validation_problem_details import ValidationProblemDetails

class RemoveUserRequestBuilder(BaseRequestBuilder):
    """
    Builds and executes requests for operations under /api/RemoveUser
    """
    def __init__(self,request_adapter: RequestAdapter, path_parameters: Union[str, dict[str, Any]]) -> None:
        """
        Instantiates a new RemoveUserRequestBuilder and sets the default values.
        param path_parameters: The raw url or the url-template parameters for the request.
        param request_adapter: The request adapter to use to execute the requests.
        Returns: None
        """
        super().__init__(request_adapter, "{+baseurl}/api/RemoveUser", path_parameters)
    
    async def post(self,body: RemoveUserRequest, request_configuration: Optional[RequestConfiguration[QueryParameters]] = None) -> None:
        """
        Requires `CAS::RemoveUser` on the target user's canonical URI.The tenant is derived from the caller and must be active. The member,invited, active or suspended, becomes `Deleted` and loses its roleassignments in one transaction. Nothing undoes it: the person is invitedagain as a new user. Removing an invited member withdraws theinvitation. An owner is refused (409) until the tenant's owner pagemakes them a member, and so is the caller's own user. The person'saccount, session and users in other tenants are untouched. Repeating thecall on a removed member returns 204. CAS refuses the member's tokensfrom the commit; regional authorization observes the change after CDCprojection, and access tokens already issued stay valid until they expire.
        param body: Request body for `POST /api/RemoveUser`.
        param request_configuration: Configuration for the request such as headers, query parameters, and middleware options.
        Returns: None
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
        return await self.request_adapter.send_no_response_content_async(request_info, error_mapping)
    
    def to_post_request_information(self,body: RemoveUserRequest, request_configuration: Optional[RequestConfiguration[QueryParameters]] = None) -> RequestInformation:
        """
        Requires `CAS::RemoveUser` on the target user's canonical URI.The tenant is derived from the caller and must be active. The member,invited, active or suspended, becomes `Deleted` and loses its roleassignments in one transaction. Nothing undoes it: the person is invitedagain as a new user. Removing an invited member withdraws theinvitation. An owner is refused (409) until the tenant's owner pagemakes them a member, and so is the caller's own user. The person'saccount, session and users in other tenants are untouched. Repeating thecall on a removed member returns 204. CAS refuses the member's tokensfrom the commit; regional authorization observes the change after CDCprojection, and access tokens already issued stay valid until they expire.
        param body: Request body for `POST /api/RemoveUser`.
        param request_configuration: Configuration for the request such as headers, query parameters, and middleware options.
        Returns: RequestInformation
        """
        if body is None:
            raise TypeError("body cannot be null.")
        request_info = RequestInformation(Method.POST, self.url_template, self.path_parameters)
        request_info.configure(request_configuration)
        request_info.headers.try_add("Accept", "application/json, application/problem+json")
        request_info.set_content_from_parsable(self.request_adapter, "application/json", body)
        return request_info
    
    def with_url(self,raw_url: str) -> RemoveUserRequestBuilder:
        """
        Returns a request builder with the provided arbitrary URL. Using this method means any other path or query parameters are ignored.
        param raw_url: The raw URL to use for the request builder.
        Returns: RemoveUserRequestBuilder
        """
        if raw_url is None:
            raise TypeError("raw_url cannot be null.")
        return RemoveUserRequestBuilder(self.request_adapter, raw_url)
    
    @dataclass
    class RemoveUserRequestBuilderPostRequestConfiguration(RequestConfiguration[QueryParameters]):
        """
        Configuration for the request such as headers, query parameters, and middleware options.
        """
        warn("This class is deprecated. Please use the generic RequestConfiguration class generated by the generator.", DeprecationWarning)
    

