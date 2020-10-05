# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
import logging
import re
from typing import Any, Callable,  List, Optional, Set, Tuple, TYPE_CHECKING, Union
from flask import g
from superset import security_manager
from superset.constants import Security as SecurityConsts
import superset.models.dashboard as dashboard_module
from superset.errors import ErrorLevel, SupersetError, SupersetErrorType
from superset.exceptions import SupersetSecurityException
from superset import conf as config


if TYPE_CHECKING:
    from superset.models.dashboard import Dashboard

logger = logging.getLogger(__name__)

dashboard_level_access_enabled = None
is_user_admin = None


def get_is_user_admin_func() -> Callable:
    global is_user_admin
    if is_user_admin is None:
        from superset.views.base import is_user_admin as to_return
        is_user_admin = to_return
    return is_user_admin


def is_dashboard_level_access_enabled() -> bool:  # pylint:disable=invalid-name
    global dashboard_level_access_enabled  # pylint:disable=global-statement
    if dashboard_level_access_enabled is None:
        from superset import is_feature_enabled

        dashboard_level_access_enabled = is_feature_enabled(
            SecurityConsts.DASHBOARD_LEVEL_ACCESS_FEATURE
        )
        logger.info(
            "dashboard level access is: " + "on"
            if dashboard_level_access_enabled
            else "off"
        )
    return dashboard_level_access_enabled


class DashboardSecurityMixin:
    previous_title: Optional[str] = None

    @property
    def view_name(self) -> str:
        return SecurityConsts.Dashboard.VIEW_NAME_FORMAT.format(obj=self)

    @property
    def permission_view_pairs(self) -> List[Tuple[str, str]]:
        return [(SecurityConsts.Dashboard.ACCESS_PERMISSION_NAME, self.view_name)]

    def add_permissions_views(self) -> None:
        for permission_name, view_menu_name in self.permission_view_pairs:
            security_manager.add_permission_view_menu(permission_name, view_menu_name)

    def update_dashboard_view(self) -> None:
        new_perm = self.view_name
        views = security_manager.find_view_menu_by_pattern(
            f"dashboard.[%](id:{self.id})"  # type: ignore
        )
        if len(views) == 0:
            security_manager.add_view_menu(new_perm)
        elif new_perm != views[0].name:
            current_view = views[0]
            current_view.name = new_perm
            security_manager.update_view_menu(current_view)

    def del_permissions_views(self) -> None:
        for permission_name, view_menu_name in self.permission_view_pairs:
            permission_view_menu = security_manager.find_permission_view_menu(
                permission_name, view_menu_name
            )
            security_manager.del_all_roles_associations(permission_view_menu)
            security_manager.del_permission_view_menu(
                permission_name, view_menu_name, cascade=False
            )
            security_manager.del_view_menu(view_menu_name)

    def is_owner(self):
        return not g.user.is_anonymous and g.user in self.owners

ID_REGEX_PATTERN = r"\(id:(?P<id>\d+)\)$"
id_finder = re.compile(ID_REGEX_PATTERN)


class DashboardSecurityManager:
    @staticmethod
    def can_access_all() -> bool:
        return security_manager.can_access(
            SecurityConsts.AllDashboard.ACCESS_PERMISSION_NAME,
            SecurityConsts.AllDashboard.VIEW_NAME,
        )

    @classmethod
    def get_access_list(cls) -> Set[str]:
        view_names = security_manager.user_view_menu_names(
            SecurityConsts.Dashboard.ACCESS_PERMISSION_NAME
        )
        return set(map(cls.parse_id_from_view_name, view_names))

    @staticmethod
    def parse_id_from_view_name(view_name: str) -> str:
        matched = id_finder.search(view_name)
        if matched:
            return matched.group("id")
        raise ValueError(f"the view name {view_name} does not contains an id segment")

    @staticmethod
    def can_access_by_id(_self: Any, dashboard_id_or_slug: Union[str, int]):
        is_admin = get_is_user_admin_func()()
        if not is_admin:
            dashboard = DashboardSecurityManager.get_dashboard(str(dashboard_id_or_slug))
            return DashboardSecurityManager.can_access_by_dashboard(dashboard, False)

    @classmethod
    def can_access_by_dashboard(cls, dashboard: "Dashboard", is_admin: Optional[bool] = None) -> None:
        is_admin = get_is_user_admin_func()() if is_admin is None else is_admin
        if not (is_admin or dashboard.is_owner() or (dashboard.published and cls.__can_access_by_dashboard(dashboard))):
            raise SupersetSecurityException(cls.get_access_error_object(dashboard))

    @classmethod
    def __can_access_by_dashboard(cls, dashboard: "Dashboard") -> bool:
        return cls.can_access_all() or \
               security_manager.can_access(SecurityConsts.Dashboard.ACCESS_PERMISSION_NAME, dashboard.view_name)

    @classmethod
    def get_access_error_object(
        cls,  # pylint: disable=invalid-name
        dashboard: "Dashboard"
    ) -> SupersetError:
        """
        Return the error object for the denied Superset datasource.

        :param dashboard: The denied Superset datasource
        :returns: The error object
        """
        return SupersetError(
            error_type=SupersetErrorType.DASHBOARD_SECURITY_ACCESS_ERROR,
            message=cls.get_access_error_msg(dashboard),
            level=ErrorLevel.ERROR,
            extra={
                "link": config.get("PERMISSION_INSTRUCTIONS_LINK"),
                "dashboard": dashboard.view_name,
            },
        )

    @staticmethod
    def get_access_error_msg(dashboard: "Dashboard") -> str:
        """
        Return the error message for the denied Superset dashboard.

        :param dashboard: The denied Superset dashboard
        :returns: The error message
        """

        return f"""This endpoint requires `{SecurityConsts.Dashboard.ACCESS_PERMISSION_NAME} on {dashboard.view_name}` or `{SecurityConsts.AllDashboard.ACCESS_PERMISSION_NAME} on {SecurityConsts.AllDashboard.VIEW_NAME}` permission"""

    @classmethod
    def get_dashboard(cls, dashboard_id_or_slug: str):
        return dashboard_module.get_dashboard(dashboard_id_or_slug)

