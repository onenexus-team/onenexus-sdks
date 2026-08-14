from __future__ import annotations
from collections.abc import Callable
from kiota_abstractions.base_request_builder import BaseRequestBuilder
from kiota_abstractions.get_path_parameters import get_path_parameters
from kiota_abstractions.request_adapter import RequestAdapter
from typing import Any, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .profile.profile_request_builder import ProfileRequestBuilder

class AccountRequestBuilder(BaseRequestBuilder):
    """
    Builds and executes requests for operations under /account
    """
    def __init__(self,request_adapter: RequestAdapter, path_parameters: Union[str, dict[str, Any]]) -> None:
        """
        Instantiates a new AccountRequestBuilder and sets the default values.
        param path_parameters: The raw url or the url-template parameters for the request.
        param request_adapter: The request adapter to use to execute the requests.
        Returns: None
        """
        super().__init__(request_adapter, "{+baseurl}/account", path_parameters)
    
    @property
    def profile(self) -> ProfileRequestBuilder:
        """
        The profile property
        """
        from .profile.profile_request_builder import ProfileRequestBuilder

        return ProfileRequestBuilder(self.request_adapter, self.path_parameters)
    

