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
"""Unit tests for Superset"""
from flask import url_for
import pytest
import re
from tests.dashboards.base_case import DashboardTestCase
from tests.dashboards.consts import ADMIN_USERNAME, GET_DASHBOARD_VIEW_URL_FORMAT, NEW_DASHBOARD_URL
from tests.dashboards.dashboard_test_utils import *
import unittest

@pytest.mark.ofek
class TestDashboard(DashboardTestCase):
    def tearDown(self) -> None:
        self.logout()

    def test_dashboard_url_generation_by_id(self):
        # arrange
        _id = 1
        excepted_url = GET_DASHBOARD_VIEW_URL_FORMAT.format(_id)

        # act
        generated_url = url_for("Superset.dashboard", dashboard_id_or_slug=_id)

        # assert
        self.assertEqual(generated_url, excepted_url)

    def test_dashboard_url_generation_by_slug(self):
        # arrange
        slug = "some_slug"
        excepted_url = GET_DASHBOARD_VIEW_URL_FORMAT.format(slug)

        # act
        generated_url = url_for("Superset.dashboard", dashboard_id_or_slug=slug)

        # assert
        self.assertEqual(generated_url, excepted_url)

    def test_new_dashboard(self):
        # arrange
        dashboard_level_access_enabled = is_dashboard_level_access_enabled()

        self.login(username=ADMIN_USERNAME)
        dash_count_before_new = count_dashboards()
        current_max_id = get_max_dashboard_id()
        excepted_dashboard_title_in_response = "[ untitled dashboard ]"

        # act
        post_new_dashboard_response = self.get_resp(NEW_DASHBOARD_URL)

        # assert
        self.assertIn(excepted_dashboard_title_in_response, post_new_dashboard_response)
        dash_count_after_new = count_dashboards()
        self.assertEqual(dash_count_before_new + 1, dash_count_after_new)
        new_max_id = get_max_dashboard_id()
        self.assertTrue(new_max_id > current_max_id)
        new_dashboard_id = new_max_id
        if dashboard_level_access_enabled:
            new_dashboard = get_dashboard_by_id(new_dashboard_id)
            self.assert_permission_was_created(new_dashboard)

        # post test - delete the new dashboard
        self.delete_dashboard(new_dashboard_id)

    @pytest.mark.dashcount_id_coupling
    def test_delete_dashboard(self):
        # arrange
        new_dashboard = None
        dashboard_level_access_enabled = is_dashboard_level_access_enabled()

        self.login(username=ADMIN_USERNAME)
        dash_count_before_new = count_dashboards()
        post_new_dashboard_response = self.get_resp(
            NEW_DASHBOARD_URL, follow_redirects=False
        )
        dash_count_after_new = count_dashboards()
        self.assertEqual(dash_count_before_new + 1, dash_count_after_new)

        new_dashboard_id = self.parse_dashboard_id(post_new_dashboard_response)

        if dashboard_level_access_enabled:
            new_dashboard = get_dashboard_by_id(new_dashboard_id)
            assign_dashboard_permissions_to_multiple_roles(new_dashboard)

        # act
        self.delete_dashboard_via_view(new_dashboard_id)

        # assert
        dash_count_after_delete = count_dashboards()
        self.assertEqual(dash_count_before_new, dash_count_after_delete)
        if dashboard_level_access_enabled:
            self.assert_permissions_were_deleted(new_dashboard)
            clean_dashboard_matching_roles()

    @staticmethod
    def parse_dashboard_id(post_new_dashboard_response):
        regex = re.compile(r"<a href=\"/superset/dashboard/(\d+)/")
        findall = regex.findall(post_new_dashboard_response)
        new_dashboard_id = int(findall[0])
        return new_dashboard_id


if __name__ == "__main__":
    unittest.main()
