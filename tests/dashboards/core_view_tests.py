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
import json
from tests.dashboards import dashboard_test_utils as dashboard_utils
from tests.dashboards.base_case import DashboardTestCase
from tests.dashboards.consts import *
from tests.dashboards.dashboard_test_utils import *
from pytest import mark

@mark.ofek
class TestDashboardInSupersetCoreView(DashboardTestCase):
    def tearDown(self) -> None:
        self.logout()

    def test_save_dash(self, username=ADMIN_USERNAME):
        self.save_dash_basic_case(username)

    def test_save_dash_with_filter(self, username=ADMIN_USERNAME):
        # arrange
        self.login(username=username)
        dashboard_to_save, data_before_change, data_after_change = build_save_dash_parts()
        dashboard_id = dashboard_to_save.id
        default_filters_before_change = dashboard_to_save.params_dict.get(
            "default_filters", "{}"
        )
        data_before_change["default_filters"] = default_filters_before_change

        filters = {str(dashboard_to_save.slices[0].id): {"region": ["North America"]}}
        default_filters = json.dumps(filters)
        data_after_change["default_filters"] = default_filters

        # act
        save_dash_response = self.save_dashboard_via_view(dashboard_id, data_after_change)

        # assert
        self.assertIn("SUCCESS", save_dash_response)
        updatedDash = get_dashboard_by_id(dashboard_id)
        new_url = updatedDash.url
        self.assertIn("region", new_url)
        get_dash_response = self.get_resp(new_url)
        self.assertIn("North America", get_dash_response)

        # post test - revert changes
        self.save_dashboard(dashboard_id, data_before_change)

    def test_save_dash_with_invalid_filters(self, username=ADMIN_USERNAME):
        # arrange
        self.login(username=username)
        dashboard_to_save, data_before_change, data_after_change = build_save_dash_parts(WORLD_HEALTH_SLUG)
        dashboard_id = dashboard_to_save.id
        default_filters_before_change = dashboard_to_save.params_dict.get("default_filters", "{}")
        data_before_change["default_filters"] = default_filters_before_change

        invalid_filter_slice = {str(99999): {"region": ["North America"]}}
        default_filters = json.dumps(invalid_filter_slice)
        data_after_change["default_filters"] = default_filters

        # act
        save_dash_response = self.save_dashboard_via_view(dashboard_id, data_after_change)

        # assert
        self.assertIn("SUCCESS", save_dash_response)

        updatedDash = get_dashboard_by_id(dashboard_id)
        new_url = updatedDash.url
        self.assertNotIn("region", new_url)

        # post test
        self.save_dashboard(dashboard_id, data_before_change)

    def test_save_dash_with_dashboard_title(self, username=ADMIN_USERNAME):
        # arrange
        new_title = "new title"
        dashboard_level_access_enabled = (
            dashboard_utils.is_dashboard_level_access_enabled()
        )
        self.login(username=username)
        dashboard_to_save, data_before_change, data_after_change = build_save_dash_parts(DEFAULT_DASHBOARD_SLUG_TO_TEST)
        dashboard_id = dashboard_to_save.id
        data_after_change["dashboard_title"] = new_title

        if dashboard_level_access_enabled:
            view_menu_id = security_manager.find_view_menu(
                dashboard_to_save.view_name
            ).id

        # act
        self.save_dashboard_via_view(dashboard_id, data_after_change)

        # assert
        updatedDash = get_dashboard_by_id(dashboard_id)
        self.assertEqual(updatedDash.dashboard_title, new_title)
        if dashboard_level_access_enabled:
            self.assert_permission_kept_and_changed(updatedDash, view_menu_id)

        # post test - bring back dashboard original title
        self.save_dashboard(dashboard_id, data_before_change)

    def test_save_dash_with_colors(self, username=ADMIN_USERNAME):
        # arrange
        self.login(username=username)
        dashboard_to_save, data_before_change, data_after_change = build_save_dash_parts(
            DEFAULT_DASHBOARD_SLUG_TO_TEST)
        dashboard_id = dashboard_to_save.id
        data_after_change["color_namespace"] = "Color Namespace Test"
        data_after_change["color_scheme"] = "Color Scheme Test"
        data_after_change["label_colors"] = {"data value": "random color"}

        # act
        self.save_dashboard_via_view(dashboard_id, data_after_change)

        # assert
        updatedDash = get_dashboard_by_id(dashboard_id)
        self.assertIn("color_namespace", updatedDash.json_metadata)
        self.assertIn("color_scheme", updatedDash.json_metadata)
        self.assertIn("label_colors", updatedDash.json_metadata)

        # post test - bring back original dashboard

        self.save_dashboard(dashboard_id, data_before_change)

    def test_save_dash_remove_slices(self, username=ADMIN_USERNAME):
        # arrange
        self.login(username=username)

        dash_to_copy = get_dashboard_by_slug(DEFAULT_DASHBOARD_SLUG_TO_TEST)

        copy_dash_url = COPY_DASHBOARD_URL_FORMAT.format(dash_to_copy.id)

        data_for_copy = {
            "dashboard_title": "copy of " + dash_to_copy.dashboard_title,
            "duplicate_slices": False,
            "positions": dash_to_copy.position,
        }

        copied_dash_id = self.get_json_resp(
            copy_dash_url, data=dict(data=json.dumps(data_for_copy))
        ).get("id")

        copied_dash_before_removing = get_dashboard_by_id(copied_dash_id)
        origin_slices_length = len(copied_dash_before_removing.slices)

        positions = get_mock_positions(copied_dash_before_removing)
        # remove one chart
        chart_keys = []
        for key in positions.keys():
            if key.startswith("DASHBOARD_CHART_TYPE"):
                chart_keys.append(key)
        positions.pop(chart_keys[0])

        data = {
            "css": "",
            "expanded_slices": {},
            "positions": positions,
            "dashboard_title": copied_dash_before_removing.dashboard_title,
        }

        # act
        self.save_dashboard_via_view(copied_dash_id, data)

        # assert - verify slices data
        copied_dash_after_removing = get_dashboard_by_id(copied_dash_id)
        data = copied_dash_after_removing.data
        self.assertEqual(len(data["slices"]), origin_slices_length - 1)

        # post test - delete the copied dashboard
        self.delete_dashboard(copied_dash_id)

    def test_copy_dash(self, username=ADMIN_USERNAME):
        # arrange
        title_of_copied_dash = "Copy Of Births"
        self.login(username=username)
        original_dashboard, original_data, data_after_change = build_save_dash_parts(
            DEFAULT_DASHBOARD_SLUG_TO_TEST)

        original_data["label_colors"] = original_dashboard.params_dict.get("label_colors")

        new_label_colors = {"data value": "random color"}
        data_after_change["duplicate_slices"] = False
        data_after_change["dashboard_title"] = title_of_copied_dash
        data_after_change["color_namespace"] = "Color Namespace Test"
        data_after_change["color_scheme"] = "Color Scheme Test"
        data_after_change["label_colors"] = new_label_colors

        # Save changes to Births dashboard and retrieve updated dash
        original_dashboard_id = original_dashboard.id
        self.save_dashboard(original_dashboard_id, data_after_change)
        after_save_dashboard_to_copy_from = get_dashboard_by_id(original_dashboard_id)
        orig_json_data = after_save_dashboard_to_copy_from.data
        copy_dash_url = COPY_DASHBOARD_URL_FORMAT.format(original_dashboard_id)

        # act
        copied_response = self.get_json_resp(
            copy_dash_url, data=dict(data=json.dumps(data_after_change))
        )

        # assert - Verify that copy matches original
        self.assertEqual(copied_response["dashboard_title"], "Copy Of Births")
        self.assertEqual(
            copied_response["position_json"], orig_json_data["position_json"]
        )
        self.assertEqual(copied_response["metadata"], orig_json_data["metadata"])
        # check every attribute in each dashboard's slices list,
        # exclude modified and changed_on attribute
        for index, slc in enumerate(orig_json_data["slices"]):
            for key in slc:
                if key not in ["modified", "changed_on", "changed_on_humanized"]:
                    self.assertEqual(slc[key], copied_response["slices"][index][key])

        # post test - bring the original dash and delete the copied one
        self.save_dashboard(original_dashboard_id, original_data)
        copy_dashboard_id = copied_response.get("id")
        self.delete_dashboard(copy_dashboard_id)

    def test_add_slices(self, username=ADMIN_USERNAME):
        # arrange
        self.login(username=username)
        new_slice = get_slice_by_name("Energy Force Layout")
        existing_slice = get_slice_by_name("Girl Name Cloud")

        add_slices_data = {
            "slice_ids": [new_slice.data["slice_id"], existing_slice.data["slice_id"]]
        }
        add_slices_url = ADD_SLICES_URL_FORMAT.format(get_dashboard_by_slug("births").id)

        # act
        add_slices_response = self.client.post(
            add_slices_url, data=dict(data=json.dumps(add_slices_data))
        )

        # assert
        assert "SLICES ADDED" in add_slices_response.data.decode("utf-8")

        dashboard_after_added_slices = get_dashboard_by_slug("births")
        new_slice = get_slice_by_name("Energy Force Layout")
        assert new_slice in dashboard_after_added_slices.slices
        assert len(set(dashboard_after_added_slices.slices)) == len(dashboard_after_added_slices.slices)

        # post test - cleaning up
        dashboard_after_added_slices.slices = [o for o in dashboard_after_added_slices.slices if o.slice_name != "Energy Force Layout"]
        db.session.merge(dashboard_after_added_slices)
        db.session.commit()
